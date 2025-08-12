# WikiSQL (sqlite-llm-bench)

This folder contains scripts and prompts specific to the WikiSQL dataset.

## Contents
- `convert_wikisql.py` – optional dataset-specific helpers (left as-is from your project or added later)
- `prompt_template.txt` – prompt template used to elicit SQL from models
- `README.md` (this file)
- `EXPECTED.md` – notes on schema, fields, and evaluation metrics

## Build
Use the top-level script to build the unified SQLite:
```bash
uv run python scripts/build_wikisql_unified.py --out data/processed/wikisql/wikisql-v1.sqlite
```

## License
WikiSQL © Salesforce Research. See upstream repo for license details.
