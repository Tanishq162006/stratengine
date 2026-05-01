"""Tests for context_builder.py."""
import json
import pytest

from context_builder import build_context, _extract_json, _render
from schema import RoundContext, TradingContext


def test_render_substitutes_vars():
    tpl = "Hello {{name}}, competition: {{comp}}"
    result = _render(tpl, name="World", comp="IMC")
    assert result == "Hello World, competition: IMC"


def test_extract_json_finds_embedded():
    text = 'Some preamble {"mode": "algo", "context": {"a": 1}} trailing'
    data = _extract_json(text)
    assert data["mode"] == "algo"
    assert data["context"]["a"] == 1


def test_extract_json_raises_on_no_json():
    with pytest.raises(ValueError, match="No JSON"):
        _extract_json("no json here at all")


def test_build_context_algo(monkeypatch):
    """build_context returns (algo, RoundContext) when LLM outputs algo mode."""
    import llm_client

    mock_output = json.dumps({
        "mode": "algo",
        "context": {
            "competition": "imc_prosperity",
            "round_name": "Round 3",
            "asset_classes": ["multi_asset"],
            "timeframe": "1m",
            "backtest_start": "2024-04-08",
            "backtest_end": "2024-04-14",
            "starting_capital": 0.0,
            "max_leverage": 1.0,
            "transaction_cost_bps": 0.0,
            "slippage_bps": 0.0,
            "objective": "total_return",
            "preferred_strategy_families": ["market_making"],
        },
    })
    monkeypatch.setattr(llm_client, "complete", lambda **kwargs: mock_output)

    mode, ctx = build_context("KELP market making IMC round 3", template_name="imc_prosperity")
    assert mode == "algo"
    assert isinstance(ctx, RoundContext)
    assert ctx.competition == "imc_prosperity"
    assert ctx.round_name == "Round 3"


def test_build_context_manual(monkeypatch):
    """build_context returns (manual, TradingContext) when LLM outputs manual mode."""
    import llm_client

    mock_output = json.dumps({
        "mode": "manual",
        "context": {
            "asset_classes": ["equity"],
            "timeframe": "1d",
            "symbols": ["SPY"],
            "risk_tolerance": "medium",
            "notes": "momentum playbook",
        },
    })
    monkeypatch.setattr(llm_client, "complete", lambda **kwargs: mock_output)

    mode, ctx = build_context("SPY momentum discretionary playbook")
    assert mode == "manual"
    assert isinstance(ctx, TradingContext)
    assert "SPY" in ctx.symbols


def test_build_context_normalizes_aliases(monkeypatch):
    """Common LLM aliases are normalized before schema validation."""
    import llm_client

    mock_output = json.dumps({
        "mode": "algo",
        "context": {
            "competition": "worldquant",
            "round_name": "Alias Test",
            "asset_class": "forex",
            "symbol": "EURUSD",
            "timeframe": "1mo",
            "backtest_start": "2024-01-01",
            "backtest_end": "2024-12-31",
        },
    })
    monkeypatch.setattr(llm_client, "complete", lambda **kwargs: mock_output)

    mode, ctx = build_context("monthly FX signal")
    assert mode == "algo"
    assert isinstance(ctx, RoundContext)
    assert ctx.competition == "worldquant_iqc"
    assert ctx.asset_classes[0].value == "fx"
    assert ctx.symbols == ["EURUSD"]
    assert ctx.timeframe.value == "1M"


def test_build_context_uses_template_loader_defaults(monkeypatch):
    """Missing algo fields are filled from the template file, not duplicated constants."""
    import llm_client

    mock_output = json.dumps({
        "mode": "algo",
        "context": {
            "round_name": "Template Defaults",
            "asset_classes": ["equity"],
            "timeframe": "1d",
        },
    })
    monkeypatch.setattr(llm_client, "complete", lambda **kwargs: mock_output)

    _, ctx = build_context("simple QC idea", template_name="quantconnect")
    assert isinstance(ctx, RoundContext)
    assert ctx.competition == "quantconnect"
    assert ctx.backtest_start == "2018-01-01"
    assert ctx.backtest_end == "2023-12-31"
    assert ctx.starting_capital == 100000.0


def test_build_context_llm_failure_raises(monkeypatch):
    """build_context re-raises LLM errors."""
    import llm_client

    def bad_complete(**kwargs):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(llm_client, "complete", bad_complete)

    with pytest.raises(RuntimeError, match="LLM unavailable"):
        build_context("any prompt")


def test_build_context_schema_validation_error(monkeypatch):
    """build_context raises ValueError when LLM output fails Pydantic validation."""
    import llm_client

    # Missing required fields in context
    mock_output = json.dumps({"mode": "algo", "context": {"competition": "imc_prosperity"}})
    monkeypatch.setattr(llm_client, "complete", lambda **kwargs: mock_output)

    with pytest.raises((ValueError, Exception)):
        build_context("bad prompt")
