"""Tests for competition plugin registry."""
import competitions
from competitions import load_plugin, register, CompetitionPlugin
from competitions.imc_prosperity.plugin import IMCProsperityPlugin


def test_imc_plugin_auto_registered():
    plugin = load_plugin("imc_prosperity")
    assert plugin is not None
    assert plugin.name == "imc_prosperity"


def test_unknown_competition_returns_none():
    assert load_plugin("nonexistent_comp_xyz") is None


def test_worldquant_registered():
    plugin = load_plugin("worldquant_iqc")
    assert plugin is not None
    assert plugin.name == "worldquant_iqc"
    assert getattr(plugin, "output_ext", None) == ".txt"


def test_quantconnect_not_registered():
    assert load_plugin("quantconnect") is None


def test_imc_plugin_implements_protocol():
    plugin = load_plugin("imc_prosperity")
    assert isinstance(plugin, CompetitionPlugin)


def test_custom_plugin_can_be_registered():
    class MockPlugin:
        name = "mock_comp"
        def run_backtest(self, code, data_path, ctx, **kwargs):
            return "STRATENGINE_STATS: {}", "", 0

    register(MockPlugin())
    assert load_plugin("mock_comp") is not None
    assert load_plugin("mock_comp").name == "mock_comp"

    # Cleanup
    competitions._REGISTRY.pop("mock_comp", None)


def test_imc_plugin_name():
    p = IMCProsperityPlugin()
    assert p.name == "imc_prosperity"
