"""Competition plugin registry.

Each competition is an isolated plugin. The core engine never imports
competition-specific code directly — it always goes through load_plugin().

A plugin must implement CompetitionPlugin:
    name: str
    run_backtest(code, data_path, ctx, **kwargs) -> (stdout, stderr, returncode)

The default backtest (Backtrader script) is used for any competition that
does not register a plugin (or returns None from load_plugin).
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from schema import RoundContext

_REGISTRY: dict[str, "CompetitionPlugin"] = {}


@runtime_checkable
class CompetitionPlugin(Protocol):
    name: str

    def run_backtest(
        self,
        code: str,
        data_path: Path,
        ctx: "RoundContext",
        **kwargs,
    ) -> tuple[str, str, int]:
        """Run the generated code and return (stdout, stderr, returncode).

        stdout MUST contain a STRATENGINE_STATS: {...} line for the evaluator
        to parse results. Return non-zero returncode on hard failure.
        """
        ...


def register(plugin: "CompetitionPlugin") -> None:
    _REGISTRY[plugin.name] = plugin


def load_plugin(competition_name: str) -> "CompetitionPlugin | None":
    """Return the plugin for `competition_name`, or None for default Backtrader path."""
    return _REGISTRY.get(competition_name)


# Auto-register all built-in plugins at import time.
def _auto_register() -> None:
    import importlib
    builtin = ["imc_prosperity", "worldquant_iqc", "quantconnect"]
    for name in builtin:
        try:
            mod = importlib.import_module(f"competitions.{name}")
            if hasattr(mod, "plugin"):
                register(mod.plugin)
        except Exception:
            pass  # plugin missing or broken — engine continues without it


_auto_register()
