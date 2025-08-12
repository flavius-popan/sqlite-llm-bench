# Expected Fields and Evaluation (WikiSQL)

## `questions` table
- `split` ∈ {train, dev, test}
- `table_id` – canonical ID from JSONL
- `table_name` – derived SQLite table name: `table_` + `table_id.replace('-', '_')`
- `question` – natural language question
- `agg` – 0=None, 1=MAX, 2=MIN, 3=COUNT, 4=SUM, 5=AVG
- `sel_col_idx` – column index into table header
- `conds_json` – `[[col_idx, op_idx, value], ...]`
- `sql_text` – canonical reconstructed SQL (optional if built with `--skip-sql-text`)

## Scoring
- **Execution Accuracy (EX)** recommended; optional **Logical Form** comparison
- Open DB read-only; only allow SELECT
