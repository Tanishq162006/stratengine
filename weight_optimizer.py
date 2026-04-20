"""Self-improving retrieval weights. After >=10 rounds of memory, fit weights
on the logged retrieval features via logistic regression. Bound each weight to
[0.05, 0.6] so no single factor dominates.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

MIN_ROUNDS = 10
MIN_W, MAX_W = 0.05, 0.60

WEIGHTS_PATH = Path(".stratengine_weights.json")
HISTORY_PATH = Path("memory/weight_history.jsonl")

FACTORS = ("source_quality", "family_win_rate", "embedding_similarity", "constraint_match_count")


@dataclass
class FittedWeights:
    weights: dict[str, float]
    n_rounds: int
    fitted_at: str
    notes: list[str] = field(default_factory=list)


def _default_weights() -> dict[str, float]:
    # equal weights, normalized
    return {f: 1.0 / len(FACTORS) for f in FACTORS}


def load_weights() -> dict[str, float]:
    if WEIGHTS_PATH.exists():
        data = json.loads(WEIGHTS_PATH.read_text())
        return {k: float(v) for k, v in data.items() if k in FACTORS}
    return _default_weights()


def _bound(weights: dict[str, float]) -> dict[str, float]:
    """Clip to [MIN_W, MAX_W], normalize to sum=1, then re-clip; iterate until
    stable. Preserves the invariant: every weight lies in [MIN_W, MAX_W] AND
    the set sums to 1.0 (exactly, modulo float epsilon).
    """
    total = sum(max(0.0, float(v)) for v in weights.values())
    if total <= 0:
        return _default_weights()
    w = {k: max(0.0, float(v)) / total for k, v in weights.items()}

    for _ in range(12):
        clipped = {k: max(MIN_W, min(MAX_W, v)) for k, v in w.items()}
        s = sum(clipped.values())
        if s <= 0:
            return _default_weights()
        normalized = {k: v / s for k, v in clipped.items()}
        if all(MIN_W - 1e-12 <= v <= MAX_W + 1e-12 for v in normalized.values()):
            return normalized
        w = normalized
    # Fallback: force equal weights.
    return _default_weights()


def _append_history(entry: dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def fit(retrieval_rows: list[dict]) -> FittedWeights:
    """retrieval_rows: list of {
        source_quality, family_win_rate, embedding_similarity, constraint_match_count,
        success (0|1)
    }
    """
    if len(retrieval_rows) < MIN_ROUNDS:
        raise RuntimeError(
            f"Need at least {MIN_ROUNDS} rounds of data to optimize weights "
            f"(have {len(retrieval_rows)}). Run more rounds first."
        )

    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
    except ImportError as e:
        raise RuntimeError(
            "weight_optimizer requires numpy + scikit-learn. "
            "pip install scikit-learn to use this feature."
        ) from e

    X = np.array([[r.get(f, 0.0) for f in FACTORS] for r in retrieval_rows], dtype=float)
    y = np.array([int(r.get("success", 0)) for r in retrieval_rows], dtype=int)

    # Guard against degenerate label set (all 0 or all 1).
    if len(set(y.tolist())) < 2:
        raise RuntimeError(
            "All retrievals have identical outcome labels — cannot fit. "
            "Need both successes and failures in the data."
        )

    model = LogisticRegression(max_iter=500)
    model.fit(X, y)
    coef = model.coef_[0]
    # Convert to non-negative weights via |coef|, then normalize & clip.
    abs_coef = [abs(float(c)) for c in coef]
    raw = {f: c for f, c in zip(FACTORS, abs_coef)}
    bounded = _bound(raw)

    fitted = FittedWeights(
        weights=bounded,
        n_rounds=len(retrieval_rows),
        fitted_at=datetime.now(timezone.utc).isoformat(),
    )
    WEIGHTS_PATH.write_text(json.dumps(bounded, indent=2))
    _append_history({"fitted_at": fitted.fitted_at, "n_rounds": fitted.n_rounds, "weights": bounded})
    return fitted
