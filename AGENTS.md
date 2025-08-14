# .AGENTS - Debugging Guide for sqlite-llm-bench

This file contains essential information for debugging issues in the sqlite-llm-bench project.

## Project Structure

- `datasets/`: Contains dataset-specific evaluation scripts and data
  - `wikisql/scripts/eval_wikisql.py`: Main WikiSQL evaluation script
- `data/`: Dataset files (databases, JSON files, etc.)
- `runs/`: Output logs from evaluation runs (JSONL format)

## Common Debugging Workflows

### 1. SQL Extraction Issues (Model Not Returning Valid SQL)

**Symptoms:**
- Low execution accuracy (EX close to 0%)
- "no_sql_extracted" errors in logs
- `pred_sql: null` in run logs

**Investigation Steps:**
1. Check recent run logs in `runs/` directory
2. Look for `"pred_err": "no_sql_extracted"` entries
3. Examine `"raw_assistant"` field to see what model actually returned
4. Test `extract_sql()` function with sample model outputs

**Common Causes:**
- Model returning incomplete SQL (missing SELECT keyword)
- Model wrapping SQL in code blocks that aren't handled
- Prefill messages causing fragmented responses
- Unclear prompts about expected output format

**Solutions:**
- Fix prompts to be explicit about complete SQL requirements
- Remove problematic prefill messages
- Keep `extract_sql()` regex simple, focusing on SELECT patterns
- Test prompt changes with small `--limit` values first

### 2. Model Accuracy Issues

**Symptoms:**
- SQL extracts correctly but wrong results (low EX despite valid SQL)
- `"pred_err": null` but `"ex": 0`

**Investigation Steps:**
1. Compare `gold_sql` vs `pred_sql` in logs
2. Look for patterns: wrong columns, missing aggregations, incorrect conditions
3. Check if model understands natural language correctly

**Common Patterns:**
- Wrong column selection (e.g., `natural_change_per_1000` vs `natural_change`)
- Missing aggregations (SELECT column vs SELECT AVG(column))
- Incorrect WHERE conditions (= vs < or >)
- Order vs aggregation confusion (ORDER BY...LIMIT vs MIN/MAX)

### 3. Running Evaluations

**Basic Commands:**
```bash
# Small test run
python datasets/wikisql/scripts/eval_wikisql.py --model "model_name" --limit 3

# With LM Studio logging
lms log stream &  # Run in background
python datasets/wikisql/scripts/eval_wikisql.py --model "qwen/qwen3-30b-a3b-2507" --limit 10
```

**Key Parameters:**
- `--limit N`: Evaluate only N samples (use small numbers for testing)
- `--model`: Model identifier (must match LM Studio model)
- `--temperature`: Controls randomness (default 0.0 for deterministic)
- `--tool-choice`: "auto", "required", or "none" for tool usage

### 4. Analyzing Results

**Log File Location:**
- Files saved to `runs/wikisql_{model}_{timestamp}.jsonl`
- Each line is a JSON record for one evaluation sample

**Key Fields:**
- `pred_sql`: Extracted SQL from model
- `gold_sql`: Correct reference SQL
- `em`: Exact match (1 if pred_sql == gold_sql exactly)
- `ex`: Execution match (1 if both queries return same results)
- `pred_err`: Error message if SQL failed to execute
- `raw_assistant`: Raw model response before extraction
- `used_tools`: Whether model used execute_sql tool
- `finish_reason`: How model ended generation

**Quick Analysis Commands:**
```bash
# Count failures by type
cat runs/latest.jsonl | jq -r '.pred_err' | sort | uniq -c

# Show failed cases
cat runs/latest.jsonl | jq -r 'select(.ex == 0) | "\(.question[0:100])... | PRED: \(.pred_sql)"'

# Check extraction issues
cat runs/latest.jsonl | jq -r 'select(.pred_sql == null) | .raw_assistant'
```

### 5. Prompt Engineering Best Practices

**System Prompt Guidelines:**
- Be explicit about output format requirements
- Specify "complete SQL starting with SELECT and ending with semicolon"
- Avoid ambiguous instructions

**User Prompt Guidelines:**
- List available columns clearly
- Specify constraints (no JOINs, subqueries, etc.)
- Handle special cases (comma-formatted numbers as TEXT)
- Be clear about aggregation requirements

**Avoid:**
- Prefill messages that fragment responses
- Complex regex to fix prompt issues
- Overly restrictive constraints that confuse the model

### 6. Testing Changes

**Iterative Testing:**
1. Make small prompt changes
2. Test with `--limit 3` first
3. Check logs to see if change worked
4. Scale up to `--limit 10` then larger sets
5. Compare metrics across runs

**A/B Testing:**
- Save different prompt versions
- Run same test set with each version
- Compare EX scores to validate improvements

### 7. Common Pitfalls

- **Don't** fix prompt issues with complex regex patterns
- **Don't** make multiple changes at once without testing
- **Do** start with small test samples
- **Do** examine raw model outputs when debugging
- **Do** focus on root causes (prompts) over symptoms (parsing)

## Environment Setup

```bash
# Activate environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Ensure LM Studio is running on localhost:1234
```

## Useful Debugging Functions

The `eval_wikisql.py` script contains these key functions:
- `extract_sql()`: Parses SQL from model responses
- `build_system_prompt()`: Creates system message
- `build_user_prompt()`: Creates user message with table info
- `normalize_sql()`: Normalizes SQL for comparison
- `execution_equal()`: Compares query results

Test these functions individually when debugging specific issues.
