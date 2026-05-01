# Data Policy

StratEngine ships as an engine, not as a bundle of competition data or generated submissions.

## Do Commit

- Source code, tests, schemas, prompt templates, and competition plugins.
- Curated public-domain or original knowledge notes that do not expose private contest data.
- Empty `.gitkeep` placeholders for runtime directories.
- Small synthetic fixtures created specifically for tests.

## Do Not Commit

- Raw competition CSVs, including `prices_round_*.csv` and `trades_round_*.csv`.
- Local backtest folders such as `bt_data/`.
- Generated submission snapshots such as `best_v*.py`.
- Copied winner scripts, private team notes, or private postmortems.
- SQLite databases, Chroma indexes, prompt logs, cache folders, or OS metadata.

## Local Workflow

Place private or downloaded datasets outside the repository, or under ignored local paths. If a command needs data, pass the path explicitly:

```bash
python run.py round --context round.json --template imc_prosperity --data /path/to/local/prices.csv
```

Generated candidates and reports should stay under `memory/`, which is ignored except for placeholder files.
