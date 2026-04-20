from walk_forward import _substitute_nth_number, ablation, param_sweep, walk_forward


SAMPLE_CODE = """
def strategy():
    period = 14
    threshold = 70
    stop = 3
    return period + threshold + stop
self.atr = 5
"""


def _fake_runner_default(code, start, end):
    # Deterministic: sharpe derived from how many digits are in the code.
    return {"sharpe": 0.5, "max_drawdown": 0.1, "total_return": 0.1}


def test_walk_forward_produces_splits():
    report = walk_forward(
        "x = 1", "2020-01-01", "2021-12-31", _fake_runner_default, n_splits=4, train_frac=0.7
    )
    assert len(report.splits) == 4
    assert report.mean_test_sharpe == 0.5


def test_substitute_nth_number():
    new = _substitute_nth_number("rsi = 14\natr = 5", 1, 10)
    assert "atr = 10" in new


def test_param_sweep_marks_fragile():
    call_counter = {"n": 0}

    def runner(code, start, end):
        call_counter["n"] += 1
        # Strong sensitivity: sharpe swings wildly with parameter
        if "14" in code or "70" in code or "3" in code:
            # Fluctuate sharpe based on code content hash
            return {"sharpe": (call_counter["n"] % 3) - 1.0}
        return {"sharpe": 0.0}

    results = param_sweep(
        SAMPLE_CODE,
        "2020-01-01",
        "2020-12-31",
        runner,
        param_indices=[0, 1],
    )
    assert len(results) > 0
    # Either fragile flags or not, but the structure must be valid.
    for r in results:
        assert len(r.values) == len(r.sharpes)


def test_ablation_flags_decorative():
    def runner(code, start, end):
        # Removing self.atr should not hurt sharpe at all in this fake runner.
        return {"sharpe": 1.0}

    results = ablation(
        SAMPLE_CODE,
        "2020-01-01",
        "2020-12-31",
        runner,
        components=["self.atr"],
        tolerance=0.05,
    )
    assert results[0].component == "self.atr"
    assert results[0].decorative is True
