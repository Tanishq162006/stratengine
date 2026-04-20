"""Analyze prompt_log for per-template success rates."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from prompt_logger import all_entries


@dataclass
class TemplateStats:
    template: str
    version: str
    n_total: int
    n_success: int
    n_failure: int
    n_pending: int
    mean_metric: float | None

    @property
    def success_rate(self) -> float:
        resolved = self.n_success + self.n_failure
        return (self.n_success / resolved) if resolved else 0.0


def per_template_stats() -> list[TemplateStats]:
    buckets: dict[tuple[str, str], list] = defaultdict(list)
    for e in all_entries():
        buckets[(e.template, e.template_version)].append(e)

    out: list[TemplateStats] = []
    for (tpl, ver), rows in buckets.items():
        n_s = sum(1 for r in rows if r.outcome == "success")
        n_f = sum(1 for r in rows if r.outcome == "failure")
        n_p = sum(1 for r in rows if r.outcome == "pending")
        metrics = [r.outcome_metric for r in rows if r.outcome_metric is not None]
        mean_metric = sum(metrics) / len(metrics) if metrics else None
        out.append(
            TemplateStats(
                template=tpl,
                version=ver,
                n_total=len(rows),
                n_success=n_s,
                n_failure=n_f,
                n_pending=n_p,
                mean_metric=mean_metric,
            )
        )
    out.sort(key=lambda s: (s.template, s.version))
    return out
