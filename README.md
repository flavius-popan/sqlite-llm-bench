# SQLite LLM Benchmark

A benchmark suite for evaluating Large Language Models on SQLite Text-to-SQL tasks, with a focus on Small Language Models run locally via LM Studio, Ollama, etc. This benchmark bundles a handful of the most popular Text-to-SQL datasets, including WikiSQL, Spider, and BIRD, but refined for local testing against SQLite.

## Quickstart

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Prepare datasets**
   - **WikiSQL**: Build top-500 dataset: `python datasets/scripts/build_wikisql_top500.py`
   - **Spider**: download original Spider dataset and run filter_and_convert_spider.py --spider-root /path/to/spider
   - **BIRD**: obtain raw files and run datasets/bird/download_bird.py (or place raw files in datasets/bird/raw/ and run conversion)

3. **Run benchmark**
   ```bash
   BENCH_BACKEND=ollama BENCH_MODEL=your_model python run_benchmark.py
   ```

## Dataset Versioning

This benchmark uses a semantic versioning system for datasets to ensure reproducibility and compatibility:

### Quick Start with Versioning

```bash
# Build WikiSQL dataset (latest version)
python datasets/scripts/build_wikisql_top500.py

# List available datasets and versions
python datasets/scripts/manage.py list

# Show dataset information
python datasets/scripts/manage.py show wikisql top500

# Validate dataset integrity
python datasets/scripts/manage.py validate wikisql top500 --verify-checksum
```

### Version Management

```bash
# Build new version with archiving
python datasets/scripts/manage.py build wikisql top500 --version 1.1.0 --archive-existing

# Load specific version in code
from datasets import load_dataset
loader = load_dataset("wikisql", "top500", version="1.0.0")  # specific version
loader = load_dataset("wikisql", "top500")                   # latest version
```

### Version Semantics

- **Major (X.0.0)**: Breaking changes (schema, evaluation methodology)
- **Minor (1.X.0)**: Backward-compatible additions (more questions, enhanced metadata)
- **Patch (1.1.X)**: Bug fixes and corrections

All datasets include version metadata, checksums for integrity validation, and automatic archiving of previous versions. See [VERSIONING.md](VERSIONING.md) for complete documentation.

## FAQ

### Why did you pick those benchmarks?

[This paper](https://openproceedings.org/2025/conf/edbt/paper-41.pdf) from March 2025 lists them as the most popular and cover the widest swath of domains.

## License notes

- This repo (code, manifests, and any added examples) is licensed CC BY 4.0 (root LICENSE).
- datasets/wikisql is included under MIT (preserve their LICENSE file in that folder).
- datasets/spider_small is included under CC BY-SA 4.0 (preserve their LICENSE file).
- BIRD is not redistributed; use the download script or obtain BIRD manually.


---
## Data locations

Large artifacts live under `data/` (git-ignored). Use `DATA_DIR` env var to override the location.

Build WikiSQL top-500 dataset:
```bash
python datasets/scripts/build_wikisql_top500.py --version 1.0.0
```

Manage dataset versions:
```bash
python datasets/scripts/manage.py list                    # List all datasets
python datasets/scripts/manage.py show wikisql top500     # Show dataset info
python datasets/scripts/manage.py validate wikisql top500 # Validate integrity
```

Test the versioning system:
```bash
python datasets/scripts/test.py                   # Full test suite
python datasets/scripts/demo.py                   # Interactive demonstration
```
