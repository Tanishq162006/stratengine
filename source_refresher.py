"""Detect new content on tracked sources, run it through the pipeline, dedup."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from rich.console import Console

from config import RAW_DIR, load_settings
from crawler import HostLimiter, RobotsCache, fetch_one, url_to_id

console = Console()


@dataclass
class RefreshSummary:
    source_name: str
    discovered: list[str] = field(default_factory=list)
    new_fetched: list[str] = field(default_factory=list)
    skipped_existing: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _already_fetched(url: str) -> bool:
    return (RAW_DIR / f"{url_to_id(url)}.json").exists()


def _parse_sitemap(xml: str) -> list[str]:
    urls = re.findall(r"<loc>\s*([^<]+)\s*</loc>", xml, flags=re.IGNORECASE)
    return [u.strip() for u in urls]


def _match_patterns(url: str, patterns: list[str]) -> bool:
    return any(p in url for p in patterns) if patterns else True


async def _discover_from_sitemap(
    client: httpx.AsyncClient, source: dict
) -> list[str]:
    sm = source.get("sitemap_url")
    if not sm:
        return []
    try:
        r = await client.get(sm, timeout=30.0)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    urls = _parse_sitemap(r.text)
    return [u for u in urls if _match_patterns(u, source.get("include_patterns", []))]


def _parse_arxiv_listing(html: str) -> list[str]:
    """Pull /abs/<id> links out of an arXiv listing page."""
    ids = set(re.findall(r"/abs/([a-z0-9.\-]+)", html, flags=re.IGNORECASE))
    return [f"https://arxiv.org/abs/{i}" for i in ids]


async def _discover_from_index(
    client: httpx.AsyncClient, source: dict
) -> list[str]:
    """For sources without sitemaps: scrape their listed index pages for new links."""
    discovered: set[str] = set()
    for seed in source.get("seed_urls", []):
        # Only treat explicit list/index URLs as expansion points.
        if not any(token in seed for token in ("/articles/", "/forum/", "/list/", "/blog/")):
            continue
        try:
            r = await client.get(seed, timeout=30.0)
        except Exception:
            continue
        if r.status_code != 200:
            continue
        if "arxiv.org/list/" in seed:
            for u in _parse_arxiv_listing(r.text):
                discovered.add(u)
            continue
        for m in re.finditer(r'href=["\']([^"\']+)["\']', r.text):
            href = m.group(1)
            absolute = urljoin(seed, href)
            if urlparse(absolute).netloc != urlparse(source["base_url"]).netloc:
                continue
            if _match_patterns(absolute, source.get("include_patterns", [])):
                discovered.add(absolute.split("#")[0])
    return sorted(discovered)


async def refresh_source(
    client: httpx.AsyncClient,
    source: dict,
    *,
    rate_per_sec: float,
    user_agent: str,
    sem: asyncio.Semaphore,
    limiters: dict[str, HostLimiter],
) -> RefreshSummary:
    robots = RobotsCache(user_agent, client)
    summary = RefreshSummary(source_name=source["name"])

    discovered = await _discover_from_sitemap(client, source)
    if not discovered:
        discovered = await _discover_from_index(client, source)

    summary.discovered = list(dict.fromkeys(discovered))  # dedup, preserve order

    for url in summary.discovered:
        if _already_fetched(url):
            summary.skipped_existing.append(url)
            continue
        res = await fetch_one(
            client, robots, limiters, rate_per_sec, sem, source["name"], url
        )
        if res is None:
            continue
        if res.get("error") or res.get("skipped") or res.get("status") != 200:
            summary.errors.append(f"{url}: {res.get('error') or res.get('skipped') or res.get('status')}")
            continue
        summary.new_fetched.append(url)
    return summary


async def refresh_all(seeds_path: Path | str = "sources/seeds.json", quiet: bool = False) -> list[RefreshSummary]:
    settings = load_settings()
    with open(seeds_path) as f:
        seeds = json.load(f)
    headers = {"User-Agent": settings.user_agent, "Accept": "text/html,application/xhtml+xml"}
    summaries: list[RefreshSummary] = []
    async with httpx.AsyncClient(headers=headers) as client:
        sem = asyncio.Semaphore(settings.max_concurrency)
        limiters: dict[str, HostLimiter] = {}
        for source in seeds["sources"]:
            if not quiet:
                console.log(f"[cyan]refresh[/] {source['name']}")
            s = await refresh_source(
                client,
                source,
                rate_per_sec=settings.rate_limit_per_host,
                user_agent=settings.user_agent,
                sem=sem,
                limiters=limiters,
            )
            summaries.append(s)
            if not quiet:
                console.log(
                    f"  discovered={len(s.discovered)} "
                    f"new={len(s.new_fetched)} existing={len(s.skipped_existing)} "
                    f"errors={len(s.errors)}"
                )
    out_path = RAW_DIR / f"_refresh_{int(time.time())}.json"
    out_path.write_text(json.dumps([s.__dict__ for s in summaries], indent=2))
    return summaries
