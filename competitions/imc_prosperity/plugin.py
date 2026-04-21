"""IMC Prosperity competition plugin.

Isolated from the core engine. The engine calls plugin.run_backtest() and
never imports imc_simulator or knows about TradingState, OrderDepth, etc.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schema import RoundContext

_SIMULATOR = Path(__file__).parent / "simulator.py"

DEFAULT_PRODUCTS = [
    "INTARIAN_PEPPER_ROOT", "ASH_COATED_OSMIUM",
]


class IMCProsperityPlugin:
    name = "imc_prosperity"

    def run_backtest(
        self,
        code: str,
        data_path: Path,
        ctx: "RoundContext",
        timeout: int = 600,
        **kwargs,
    ) -> tuple[str, str, int]:
        products = list(ctx.symbols) if ctx.symbols else DEFAULT_PRODUCTS
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            trader_path = Path(f.name)
        try:
            cmd = [
                sys.executable, str(_SIMULATOR),
                "--code", str(trader_path),
                "--data", str(data_path),
                "--start", ctx.backtest_start,
                "--end", ctx.backtest_end,
                "--products", ",".join(products),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return proc.stdout, proc.stderr, proc.returncode
        finally:
            trader_path.unlink(missing_ok=True)


plugin = IMCProsperityPlugin()
