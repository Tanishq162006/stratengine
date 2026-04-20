"""Source-layer crawler. Fetches seed URLs, respects robots.txt, rate-limits
per-host, stores raw HTML + metadata in data/raw/."""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from rich.console import Console

from config import RAW_DIR, ensure_dirs, load_settings

console = Console()


@dataclass
class HostLimiter:
    rate_per_sec: float
    _last_fetch: float = 0.0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            min_gap = 1.0 / self.rate_per_sec if self.rate_per_sec > 0 else 0.0
            delta = now - self._last_fetch
            if delta < min_gap:
                await asyncio.sleep(min_gap - delta)
            self._last_fetch = time.monotonic()


class RobotsCache:
    def __init__(self, user_agent: str, client: httpx.AsyncClient):
        self.ua = user_agent
        self.client = client
        self._parsers: dict[str, RobotFileParser] = {}
        self._lock = asyncio.Lock()

    async def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        async with self._lock:
            rp = self._parsers.get(origin)
            if rp is None:
                rp = RobotFileParser()
                robots_url = f"{origin}/robots.txt"
                try:
                    r = await self.client.get(robots_url, timeout=10.0)
                    if r.status_code == 200:
                        rp.parse(r.text.splitlines())
                    else:
                        rp.parse([])  # empty → allow all
                except Exception:
                    rp.parse([])
                self._parsers[origin] = rp
        return rp.can_fetch(self.ua, url)


def url_to_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def load_seeds(seeds_path: Path) -> list[dict]:
    with seeds_path.open() as f:
        data = json.load(f)
    flat: list[dict] = []
    for source in data["sources"]:
        for url in source.get("seed_urls", []):
            flat.append({"source_name": source["name"], "url": url})
    return flat


async def fetch_one(
    client: httpx.AsyncClient,
    robots: RobotsCache,
    limiters: dict[str, HostLimiter],
    rate_per_sec: float,
    sem: asyncio.Semaphore,
    source_name: str,
    url: str,
) -> dict | None:
    host = urlparse(url).netloc
    limiter = limiters.setdefault(host, HostLimiter(rate_per_sec=rate_per_sec))

    if not await robots.allowed(url):
        console.log(f"[yellow]robots disallow[/] {url}")
        return {"source_name": source_name, "url": url, "skipped": "robots"}

    async with sem:
        await limiter.wait()
        try:
            r = await client.get(url, timeout=30.0, follow_redirects=True)
        except Exception as e:
            console.log(f"[red]error[/] {url}: {e}")
            return {"source_name": source_name, "url": url, "error": str(e)}

    if r.status_code != 200:
        console.log(f"[yellow]{r.status_code}[/] {url}")
        return {"source_name": source_name, "url": url, "status": r.status_code}

    doc_id = url_to_id(url)
    html_path = RAW_DIR / f"{doc_id}.html"
    meta_path = RAW_DIR / f"{doc_id}.json"
    html_path.write_text(r.text, encoding="utf-8")
    meta = {
        "id": doc_id,
        "url": url,
        "source_name": source_name,
        "status": r.status_code,
        "fetched_at": time.time(),
        "content_type": r.headers.get("content-type"),
        "final_url": str(r.url),
        "bytes": len(r.text),
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    console.log(f"[green]ok[/] {url} -> {doc_id}")
    return meta


async def crawl(seeds_path: Path | str = "sources/seeds.json") -> list[dict]:
    ensure_dirs()
    settings = load_settings()
    seeds = load_seeds(Path(seeds_path))

    headers = {"User-Agent": settings.user_agent, "Accept": "text/html,application/xhtml+xml"}
    results: list[dict] = []
    async with httpx.AsyncClient(headers=headers) as client:
        robots = RobotsCache(settings.user_agent, client)
        sem = asyncio.Semaphore(settings.max_concurrency)
        limiters: dict[str, HostLimiter] = {}
        tasks = [
            fetch_one(
                client,
                robots,
                limiters,
                settings.rate_limit_per_host,
                sem,
                s["source_name"],
                s["url"],
            )
            for s in seeds
        ]
        for coro in asyncio.as_completed(tasks):
            res = await coro
            if res:
                results.append(res)

    summary_path = RAW_DIR / "_crawl_summary.json"
    summary_path.write_text(json.dumps(results, indent=2))
    console.print(f"[bold green]Crawl complete:[/] {len(results)} results → {summary_path}")
    return results


if __name__ == "__main__":
    asyncio.run(crawl())
