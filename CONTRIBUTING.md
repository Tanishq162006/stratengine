# Contributing

This repository is optimized for clean competition research workflows.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
```

## Standards

- Keep changes scoped to engine code, prompts, schemas, templates, tests, or curated knowledge.
- Do not commit raw competition data, copied submissions, generated candidates, local databases, or private notes.
- Add tests when changing shared behavior, schema contracts, plugin output, or CLI flows.
- Prefer typed, explicit data structures over ad hoc strings for round context and strategy metadata.
- Run `pytest -q` before opening a PR.

## Competition Plugins

Plugins live under `competitions/<name>/` and are registered through `competitions/__init__.py`. A plugin should declare:

- `name`
- `output_ext`
- `run_backtest(code, data_path, ctx, **kwargs)`

Plugin-specific prompts and defaults should live in `prompts/` and `templates/`, not inside the CLI.
