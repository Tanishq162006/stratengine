# TODO: brain_api.py — autonomous BRAIN simulation client

**Status**: parked. User wants this on the roadmap, not yet built. The
study-the-techniques work was prioritised first.

## Why

Without a live BRAIN client, the alpha-gpt loop scores candidates with
local heuristics (canonical-pipeline presence, operator diversity,
self-correlation token similarity). That is a useful filter but it is
not the real fitness signal — only BRAIN's simulator produces actual
Sharpe / Fitness / Turnover / Sub-Universe-Sharpe / Self-Correlation
numbers.

A working `brain_api.py` would let the loop close: seed → simulate →
mutate using *real* metrics → simulate → submit the survivor. That is
the actual Alpha-GPT paper loop (arXiv:2308.00016) end-to-end.

## Reference Implementation

The shape is well-established in the public domain:

- `github.com/RussellDash332/WQ-Brain/blob/main/main.py` — `WQSession`
  class extending `requests.Session`. Authenticates via basic auth
  against `https://api.worldquantbrain.com/authentication`. Submits
  simulations via `POST .../simulations` with a settings JSON body and
  polls the `Location` header for results.
- `github.com/AbnerTeng/WorldQuant-Brain` — the upstream version that
  RussellDash332 forked from.

## API surface to implement

```python
class BrainSession:
    def __init__(self, credentials: dict | Path) -> None: ...
    def login(self) -> None: ...
    def simulate(
        self,
        expression: str,
        *,
        delay: int = 1,
        universe: str = "TOP3000",
        truncation: float = 0.08,
        decay: int = 4,
        neutralization: str = "SUBINDUSTRY",
        region: str = "USA",
        pasteurization: str = "ON",
        nan_handling: str = "OFF",
        unit_handling: str = "VERIFY",
        timeout_s: int = 600,
    ) -> SimulationResult: ...
    # SimulationResult includes:
    #   sharpe, fitness, turnover_pct, sub_universe_sharpe,
    #   passed_checks, failed_checks, alpha_url
    # NEVER auto-submit. Submission is a user action only.

class SimulationResult: ...
```

## CLI hooks to add

- `python3 run.py brain-simulate <expression> [--universe ... --decay ...]`
  Single-shot simulate. Prints the full check breakdown.
- `python3 run.py alpha-gpt --use-brain ...` flag that swaps the local
  heuristic fitness in `alpha_gpt.py` for `brain_api.simulate(...)` and
  uses the real Sharpe / Fitness as the loop fitness signal.

## Credentials handling

- Read from `credentials.json` (already gitignored via `.env*` rule —
  may need an explicit `.gitignore` entry for `credentials.json` to be
  safe).
- Provide `credentials.json.example` template with empty fields.
- Bail with a clear error if file is missing or fields are empty.

## Risks / why this is opt-in

1. **Costs live BRAIN simulation slots** per call. The user should
   know the rate limit (3 concurrent simulations) and burn rate before
   running the alpha-gpt loop with `--use-brain`.
2. **Auth involves email + password.** Basic auth header with optional
   biometric step. Credentials must never log to stdout.
3. **NEVER auto-submit.** The submit endpoint exists
   (`POST /alphas/{aid}/submit`) but submission is a user action — the
   client should support fetching `is.checks` to verify everything
   passes locally, and the user clicks Submit by hand on the platform.
4. **Network failures**: simulations can take minutes. Need exponential
   backoff and a long polling loop, plus graceful handling of 504
   gateway timeouts and 401 expired-credentials errors.

## Tests

- Mock the `requests.Session` layer in tests.
- Test happy path: simulate → poll → return SimulationResult.
- Test auth-expired path.
- Test failure: simulator returns FAIL status.
- Test alpha-gpt --use-brain happy path with mocked simulate().

## When to build

When user says go. Should take ~half a day to ship safely (client +
tests + CLI + alpha-gpt integration + documentation).
