# SQLite LLM Benchmark

A benchmark suite for evaluating Large Language Models on SQLite Text-to-SQL tasks, with a focus on Small Language Models run locally via LM Studio, Ollama, etc. This benchmark bundles a handful of the most popular Text-to-SQL datasets, including WikiSQL, Spider, and BIRD, but refined for local testing against SQLite.

## Quickstart

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Prepare datasets**
   - **WikiSQL**: download and point convert_wikisql.py at the dev.json and tables folder
   - **Spider**: download original Spider dataset and run filter_and_convert_spider.py --spider-root /path/to/spider
   - **BIRD**: obtain raw files and run datasets/bird/download_bird.py (or place raw files in datasets/bird/raw/ and run conversion)

3. **Run benchmark**
   ```bash
   BENCH_BACKEND=ollama BENCH_MODEL=your_model python run_benchmark.py
   ```

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

Build WikiSQL unified DB:
```bash
python scripts/build_wikisql_unified.py
```
