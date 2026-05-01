"""Tests for generator prompt routing."""
from generator import _coder_template_name, _synth_template_name
from schema import RoundContext


def _ctx(competition: str) -> RoundContext:
    return RoundContext(
        competition=competition,
        round_name="Round 1",
        asset_classes=["equity"],
        timeframe="1d",
        backtest_start="2024-01-01",
        backtest_end="2024-12-31",
    )


def test_worldquant_uses_brain_prompts():
    ctx = _ctx("worldquant_iqc")
    assert _synth_template_name(ctx) == "synthesize_brain.txt"
    assert _coder_template_name(ctx) == "code_brain.txt"


def test_imc_and_quantconnect_use_competition_specific_coder_prompts():
    assert _coder_template_name(_ctx("imc_prosperity")) == "code_imc.txt"
    assert _coder_template_name(_ctx("quantconnect")) == "code_quantconnect.txt"


def test_custom_competition_falls_back_to_generic_prompts():
    ctx = _ctx("custom")
    assert _synth_template_name(ctx) == "synthesize.txt"
    assert _coder_template_name(ctx) == "code.txt"
