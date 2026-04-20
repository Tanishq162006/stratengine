import tempfile
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_db(monkeypatch):
    d = Path(tempfile.mkdtemp(prefix="sq_test_"))
    monkeypatch.setenv("STRATENGINE_DB_PATH", str(d / "test.db"))
    yield d


def test_unseen_source_defaults_to_neutral(tmp_db):
    from source_quality import NEUTRAL_DEFAULT, score_for

    assert score_for("SomeNewSource") == NEUTRAL_DEFAULT


def test_extraction_success_pushes_score_up(tmp_db):
    from source_quality import record_extraction, score_for

    before = score_for("GoodSource")
    for _ in range(20):
        record_extraction("GoodSource", success=True, card_confidence=0.9)
    after = score_for("GoodSource")
    assert after > before


def test_extraction_failure_pushes_score_down(tmp_db):
    from source_quality import record_extraction, score_for

    before = score_for("BadSource")
    for _ in range(20):
        record_extraction("BadSource", success=False)
    after = score_for("BadSource")
    assert after < before


def test_playbook_clarity_updates_only_clarity_dimension(tmp_db):
    from source_quality import all_scores, record_playbook

    for _ in range(5):
        record_playbook("TestSource", signal_clarity=0.9)
    rows = {r.source_name: r for r in all_scores()}
    r = rows["TestSource"]
    assert r.playbook_clarity_score > 0.5
    # Other dims should remain at the neutral default.
    assert r.extraction_success_rate == 0.5
    assert r.backtest_survival_rate == 0.5
