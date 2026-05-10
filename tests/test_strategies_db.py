"""strategies_db CRUD smoke tests on a tmp SQLite path."""
from __future__ import annotations

from pathlib import Path

import pytest

import strategies_db as sdb


@pytest.fixture()
def db(tmp_path) -> Path:
    return tmp_path / "test_strats.db"


def test_upsert_and_list(db):
    sid = sdb.upsert_strategy(
        competition="worldquant_iqc",
        name="reversal v1",
        expression="scale(group_neutralize(zscore(returns), subindustry))",
        thesis="short-term reversal",
        config={"decay": 4},
        db_path=db,
    )
    assert sid
    rows = sdb.list_strategies("worldquant_iqc", db_path=db)
    assert len(rows) == 1
    assert rows[0]["name"] == "reversal v1"
    # default feedback row created
    assert rows[0]["rating"] == 0
    assert rows[0]["status"] == "draft"


def test_results_and_latest_metrics(db):
    sid = sdb.upsert_strategy(
        competition="worldquant_iqc", name="x",
        expression="scale(group_neutralize(zscore(close), subindustry))", db_path=db,
    )
    sdb.add_result(sid, "sharpe", 1.47, db_path=db)
    sdb.add_result(sid, "fitness", 0.78, db_path=db)
    sdb.add_result(sid, "sharpe", 1.62, db_path=db)
    latest = sdb.latest_metrics(sid, db_path=db)
    assert latest["sharpe"] == 1.62
    assert latest["fitness"] == 0.78


def test_feedback_round_trip(db):
    sid = sdb.upsert_strategy(
        competition="quantconnect", name="ema_cross",
        expression="def Initialize(self): pass", db_path=db,
    )
    sdb.set_feedback(sid, rating=4, status="submitted", notes="meh", db_path=db)
    fb = sdb.get_feedback(sid, db_path=db)
    assert fb["rating"] == 4
    assert fb["status"] == "submitted"
    assert fb["notes"] == "meh"


def test_competitions_isolated(db):
    sdb.upsert_strategy(competition="worldquant_iqc", name="a", expression="x", db_path=db)
    sdb.upsert_strategy(competition="quantconnect",   name="b", expression="y", db_path=db)
    sdb.upsert_strategy(competition="imc_prosperity", name="c", expression="z", db_path=db)
    assert len(sdb.list_strategies("worldquant_iqc", db_path=db)) == 1
    assert len(sdb.list_strategies("quantconnect", db_path=db)) == 1
    assert len(sdb.list_strategies("imc_prosperity", db_path=db)) == 1


def test_unknown_competition_rejected(db):
    with pytest.raises(ValueError):
        sdb.upsert_strategy(
            competition="nasdaq_pirates", name="x", expression="y", db_path=db,
        )


def test_import_alpha_history(db, tmp_path):
    history = tmp_path / "alpha_history.md"
    history.write_text(
        "# alpha history\n\n"
        "### alpha_001 — Volume-Confirmed Reversal v1\n"
        "**Expression:**\n```\nscale(group_neutralize(rank(close), subindustry))\n```\n"
        "**Results:** Sharpe 1.47 PASS | Turnover 41.84% PASS | Fitness 0.78 FAIL | Sub-Sharpe 0.94 PASS\n"
        "**Lesson:** Use zscore not rank.\n",
        encoding="utf-8",
    )
    n = sdb.import_alpha_history(history_path=history, db_path=db)
    assert n == 1
    rows = sdb.list_strategies("worldquant_iqc", db_path=db)
    assert rows[0]["name"].startswith("alpha_001")
    assert rows[0]["thesis"].startswith("Use zscore")
    metrics = sdb.latest_metrics(rows[0]["strategy_id"], db_path=db)
    assert metrics["sharpe"] == 1.47
    assert metrics["fitness"] == 0.78
