import tempfile
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_db(monkeypatch):
    d = Path(tempfile.mkdtemp(prefix="fa_test_"))
    monkeypatch.setenv("STRATENGINE_DB_PATH", str(d / "test.db"))
    yield d


def test_win_rates_and_boost(tmp_db):
    from family_performance import boost_for, log_result
    from family_analyzer import ranked_win_rates

    for i in range(8):
        log_result("imc", "algo", "momentum", "equity", "1d", sharpe=1.0, success=True)
    for i in range(2):
        log_result("imc", "algo", "momentum", "equity", "1d", sharpe=-0.5, success=False)
    for i in range(3):
        log_result("imc", "algo", "mean_reversion", "equity", "1d", success=False)

    rates = {r.family: r for r in ranked_win_rates("imc")}
    assert rates["momentum"].rate == 0.8
    assert rates["mean_reversion"].rate == 0.0

    # boost bounded
    mom = boost_for("momentum", "imc")
    mr = boost_for("mean_reversion", "imc")
    assert 0.5 <= mom <= 1.5
    assert 0.5 <= mr <= 1.5
    assert mom > mr


def test_unseen_family_is_neutral(tmp_db):
    from family_performance import boost_for

    assert abs(boost_for("macro", "anything") - 1.0) < 1e-9
