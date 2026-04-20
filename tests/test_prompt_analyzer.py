import tempfile
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_db(monkeypatch):
    d = Path(tempfile.mkdtemp(prefix="pa_test_"))
    monkeypatch.setenv("STRATENGINE_DB_PATH", str(d / "test.db"))
    yield d


def test_log_and_finalize(tmp_db):
    from prompt_logger import all_entries, finalize, log_call

    id1 = log_call("extract.txt", context={"url": "x"}, input_obj={"len": 100})
    id2 = log_call("synthesize.txt", context={"round": "r1"})
    finalize(id1, "success", metric=0.8)
    finalize(id2, "failure", notes="bad json")
    rows = all_entries()
    assert len(rows) == 2
    r1 = next(r for r in rows if r.id == id1)
    assert r1.outcome == "success"
    assert r1.outcome_metric == 0.8


def test_per_template_stats(tmp_db):
    from prompt_analyzer import per_template_stats
    from prompt_logger import finalize, log_call

    for _ in range(3):
        finalize(log_call("extract.txt"), "success", metric=0.7)
    for _ in range(2):
        finalize(log_call("extract.txt"), "failure")
    stats = per_template_stats()
    s = [x for x in stats if x.template == "extract.txt"][0]
    assert s.n_success == 3
    assert s.n_failure == 2
    assert abs(s.success_rate - 0.6) < 1e-9
