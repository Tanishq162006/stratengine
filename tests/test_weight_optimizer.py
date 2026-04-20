import pytest


def _synthetic_rows(n=20, seed=0):
    import random

    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        feats = {
            "source_quality": rng.random(),
            "family_win_rate": rng.random(),
            "embedding_similarity": rng.random(),
            "constraint_match_count": rng.random(),
        }
        # Success label: driven mostly by embedding_similarity + source_quality
        score = 0.7 * feats["embedding_similarity"] + 0.5 * feats["source_quality"]
        feats["success"] = 1 if score > 0.55 else 0
        rows.append(feats)
    return rows


def test_refuses_with_too_few_rounds():
    import weight_optimizer

    with pytest.raises(RuntimeError, match="at least"):
        weight_optimizer.fit(_synthetic_rows(n=5))


def test_fit_respects_bounds(tmp_path, monkeypatch):
    import weight_optimizer

    monkeypatch.setattr(weight_optimizer, "WEIGHTS_PATH", tmp_path / "weights.json")
    monkeypatch.setattr(weight_optimizer, "HISTORY_PATH", tmp_path / "history.jsonl")

    rows = _synthetic_rows(n=20)
    fitted = weight_optimizer.fit(rows)
    eps = 1e-9
    for v in fitted.weights.values():
        assert weight_optimizer.MIN_W - eps <= v <= weight_optimizer.MAX_W + eps
    assert abs(sum(fitted.weights.values()) - 1.0) < 1e-6
    assert (tmp_path / "weights.json").exists()
