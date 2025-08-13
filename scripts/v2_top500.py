#!/usr/bin/env python3
"""
WikiSQL Top-K Question Selection Script

This script processes the WikiSQL dataset to select the top K most difficult questions
based on a weighted difficulty scoring system. It downloads the WikiSQL data,
validates questions against their corresponding databases, computes difficulty metrics,
and creates a consolidated SQLite database with the selected questions and tables.

The difficulty score considers:
- Condition complexity (number and rarity of operators)
- Aggregation usage and rarity
- Table dimensions (rows/columns)
- Question word count

Author: SQLite-LLM-Bench Project
Version: 2
"""

import argparse
import bz2
import concurrent.futures as cf
import io
import json
import re
import sqlite3
import string
import tarfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple, Any
import shutil

DATASET_VERSION = 1

DATA_URL = "https://raw.githubusercontent.com/salesforce/WikiSQL/master/data.tar.bz2"

# Aggregation function mappings from WikiSQL integer codes
AGG_MAP = {
    0: None,     # No aggregation
    1: "MAX",    # Maximum value
    2: "MIN",    # Minimum value
    3: "COUNT",  # Count rows
    4: "SUM",    # Sum values
    5: "AVG",    # Average value
}

# SQL operator mappings from WikiSQL integer codes
OP_MAP = {
    0: "=",      # Equal
    1: ">",      # Greater than
    2: "<",      # Less than
    3: ">=",     # Greater than or equal
    4: "<=",     # Less than or equal
    5: "!=",     # Not equal
}

# Difficulty scoring weights for different question attributes
WEIGHTS = {
    "cond_count": 1.5,      # Number of WHERE conditions
    "op_rarity_sum": 0.9,   # Rarity of operators used
    "has_agg": 0.8,         # Whether aggregation is used
    "agg_rarity": 0.7,      # Rarity of aggregation function
    "n_rows": 0.001,        # Table size (rows)
    "n_cols": 0.25,         # Table width (columns)
    "q_words": 0.05,        # Question length in words
}

# Default configuration values
DEFAULT_DATA_DIR = "data/raw/wikisql"
DEFAULT_OUT = f"data/processed/wikisql/wikisql-top500-v{DATASET_VERSION}.db"
DEFAULT_K = 500
DEFAULT_PROCESSES = 3

def _create_task_dict():
    """Create a new task dictionary for tracking column usage and questions per table."""
    return {"col_idxs": set(), "questions": []}

def _json_array_length(s):
    """SQLite function to calculate the length of a JSON array string."""
    return len(json.loads(s)) if s else 0

def derived_table_name(table_id: str) -> str:
    """Convert WikiSQL table ID to a valid SQLite table name by replacing hyphens with underscores."""
    return "table_" + table_id.replace("-", "_")



def ensure_wikisql_data(data_dir: Path) -> None:
    """
    Download and extract WikiSQL dataset if not already present.

    Args:
        data_dir: Directory where WikiSQL data should be stored

    The function checks for required files and downloads/extracts the dataset
    if any files are missing. Cleans up the archive after extraction.
    """
    print(f"Ensuring WikiSQL data is available in {data_dir}")

    # Check if all required files exist
    expected = ["train.jsonl", "dev.jsonl", "test.jsonl",
                "tables.jsonl", "train.db", "dev.db", "test.db"]

    if all((data_dir / f).exists() for f in expected):
        print("All required WikiSQL files found")
        return

    print("Missing WikiSQL files, downloading and extracting...")
    data_dir.mkdir(parents=True, exist_ok=True)
    archive = data_dir / "data.tar.bz2"

    if not archive.exists():
        print(f"Downloading WikiSQL dataset from {DATA_URL}")
        import urllib.request
        urllib.request.urlretrieve(DATA_URL, archive)

    print("Extracting WikiSQL archive...")
    with bz2.BZ2File(archive, "rb") as f_in:
        with tarfile.open(fileobj=io.BytesIO(f_in.read())) as tf:
            tf.extractall(data_dir, filter='data')

    if archive.exists():
        print("Cleaning up archive file")
        archive.unlink()

def sanitize_identifier(name: str) -> str:
    """
    Convert a column name to a valid SQL identifier.

    Args:
        name: Original column name from WikiSQL

    Returns:
        Sanitized column name safe for use as SQL identifier

    Handles special cases like 4-digit years and ensures valid SQL naming conventions.
    """
    original_name = name.strip()
    # Special case: preserve 4-digit years with yr_ prefix
    if re.match(r'^\d{4}$', original_name):
        return 'yr_' + original_name

    name = name.strip().lower()
    allowed = set(string.ascii_lowercase + string.digits + "_")
    cleaned = []
    prev_us = False
    for ch in name:
        ch = ch if ch in allowed else "_"
        # Avoid consecutive underscores
        if ch == "_" and prev_us:
            continue
        prev_us = (ch == "_")
        cleaned.append(ch)
    s = "".join(cleaned).strip("_")
    if not s:
        s = "col"
    # Handle identifiers starting with digits
    if s[0].isdigit():
        if re.match(r'^\d{4}$', s):
            s = "yr_" + s
        else:
            s = "col_" + s
    return s

def unique_names(names: List[str]) -> List[str]:
    """
    Ensure all column names are unique by appending numeric suffixes as needed.

    Args:
        names: List of potentially duplicate column names

    Returns:
        List of unique column names with numeric suffixes where needed

    This prevents SQL table creation errors from duplicate column names.
    """
    seen = {}
    out = []
    for n in names:
        base = n
        i = seen.get(base, 0)
        if i == 0 and base not in seen:
            out.append(base)
            seen[base] = 1
        else:
            # Generate unique name with numeric suffix
            i = seen[base]
            candidate = f"{base}_{i}"
            while candidate in seen:
                i += 1
                candidate = f"{base}_{i}"
            out.append(candidate)
            seen[base] = i + 1
            seen[candidate] = 1
    return out

def build_sql_text(table: str, headers: List[str], agg: int, sel: int, conds: List[List]):
    """
    Generate SQL query text from WikiSQL question components.

    Args:
        table: Table ID
        headers: Column headers from the table
        agg: Aggregation function code (0=none, 1=MAX, 2=MIN, 3=COUNT, 4=SUM, 5=AVG)
        sel: Selected column index
        conds: List of conditions [column_idx, operator_idx, value]

    Returns:
        Tuple of (sql_query_string, sanitized_column_names)
    """
    proper = unique_names([sanitize_identifier(h) for h in headers])
    sel_name = proper[sel]
    agg_kw = AGG_MAP.get(agg)
    select_expr = f'"{sel_name}"' if agg_kw is None else f'{agg_kw}("{sel_name}")'
    cond_parts = []
    for col_idx, op_idx, val in conds:
        op = OP_MAP[op_idx]
        col_name = proper[col_idx]
        if isinstance(val, (int, float)):
            val_sql = str(val)
        else:  # Other aggregations - check if result is not null
            # Escape single quotes in string values
            val_sql = "'" + str(val).replace("'", "''") + "'"
        cond_parts.append(f'"{col_name}" {op} {val_sql}')
    where = (" WHERE " + " AND ".join(cond_parts)) if cond_parts else ""
    table_name = derived_table_name(table)
    return f'SELECT {select_expr} FROM "{table_name}"{where};', proper

def count_words(s: str) -> int:
    """Count the number of words in a string, splitting on whitespace."""
    return len([w for w in re.split(r"\s+", s.strip()) if w])

@dataclass
class TableMeta:
    """Metadata for a WikiSQL table including schema and context information."""
    table_id: str
    header: List[str]
    types: List[str]
    page_title: str
    section_title: str
    caption: str
    page_id: int

def read_tables_jsonl(data_dir: Path) -> Dict[str, TableMeta]:
    """
    Load table metadata from WikiSQL JSONL files.

    Args:
        data_dir: Directory containing WikiSQL data

    Returns:
        Dictionary mapping table_id to TableMeta objects

    Reads from train.tables.jsonl, dev.tables.jsonl, and test.tables.jsonl
    and deduplicates tables that appear in multiple splits.
    """
    print("Loading table metadata from JSONL files...")
    meta = {}
    extracted_dir = data_dir / "data"
    for split in ["train", "dev", "test"]:
        table_file = extracted_dir / f"{split}.tables.jsonl"
        if table_file.exists():
            print(f"Reading {split} table metadata...")
            with table_file.open("r", encoding="utf-8") as f:
                for line in f:
                    obj = json.loads(line)
                    if obj["id"] not in meta:
                        meta[obj["id"]] = TableMeta(
                            table_id=obj["id"],
                            header=obj["header"],
                            types=obj["types"],
                            page_title=obj.get("page_title", ""),
                            section_title=obj.get("section_title", ""),
                            caption=obj.get("caption", ""),
                            page_id=int(obj.get("page_id", -1)),
                        )
    print(f"Loaded metadata for {len(meta)} unique tables")
    return meta

def read_split_jsonl(data_dir: Path, split: str) -> List[dict]:
    """
    Load questions from a specific WikiSQL split.

    Args:
        data_dir: Directory containing WikiSQL data
        split: Split name ("train", "dev", or "test")

    Returns:
        List of question dictionaries with normalized structure
    """
    print(f"Loading {split} questions...")
    extracted_dir = data_dir / "data"
    p = extracted_dir / f"{split}.jsonl"
    out = []
    with p.open("r", encoding="utf-8") as f:
        for row in f:
            j = json.loads(row)
            out.append({
                "qid": f"{split}_{len(out)}",
                "split": split,
                "table_id": j["table_id"],
                "question": j["question"],
                "agg": int(j["sql"]["agg"]),
                "sel": int(j["sql"]["sel"]),
                "conds": [[int(c[0]), int(c[1]), c[2]] for c in j["sql"]["conds"]],
            })
    print(f"Loaded {len(out)} questions from {split}")
    return out

def _mk_where_and_params(conds: List[List]) -> Tuple[str, List]:
    """
    Generate WHERE clause and parameters for SQL validation queries.

    Uses parameterized queries to safely handle different value types.
    """
    if not conds:
        return "", []
    parts, params = [], []
    for col_idx, op_idx, val in conds:
        op = OP_MAP[op_idx]
        parts.append(f'"col{col_idx}" {op} ?')
        params.append(val)
    return " WHERE " + " AND ".join(parts), params

def _validate_question(cur: sqlite3.Cursor, table: str, agg: int, sel: int, conds: List[List]) -> bool:
    """
    Validate that a question can be executed against its table and returns meaningful results.

    Args:
        cur: Database cursor for the split containing the table
        table: Table ID
        agg: Aggregation function code
        sel: Selected column index
        conds: List of WHERE conditions

    Returns:
        True if question is valid (returns non-empty, non-null results)

    Handles different validation logic for different aggregation types.
    """
    where_sql, params = _mk_where_and_params(conds)
    table_name = derived_table_name(table)
    if agg == 0:  # No aggregation - check for non-null values in selected column
        q = f'SELECT COUNT(*) FROM "{table_name}"{where_sql} AND "col{sel}" IS NOT NULL' if where_sql else \
            f'SELECT COUNT(*) FROM "{table_name}" WHERE "col{sel}" IS NOT NULL'
        cur.execute(q, params)
        return cur.fetchone()[0] > 0
    if agg == 3:  # COUNT aggregation - just check if any rows match conditions
        q = f'SELECT COUNT(*) FROM "{table_name}"{where_sql}'
        cur.execute(q, params)
        return cur.fetchone()[0] > 0
    else:
        agg_kw = AGG_MAP[agg]
        q = f'SELECT {agg_kw}("col{sel}") FROM "{table_name}"{where_sql}'
        cur.execute(q, params)
        return cur.fetchone()[0] is not None

def _compute_table_stats(cur: sqlite3.Cursor, table: str, col_idxs: Iterable[int]) -> dict:
    """
    Compute statistics for a table and its referenced columns.

    Args:
        cur: Database cursor
        table: Table ID
        col_idxs: Column indices that are referenced by questions

    Returns:
        Dictionary containing table row count and per-column statistics

    Statistics include non-null counts and distinct value counts for selectivity estimation.
    """
    stats = {}
    table_name = derived_table_name(table)
    cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
    n_rows = int(cur.fetchone()[0])
    stats["n_rows"] = n_rows
    # Compute column statistics for selectivity estimation
    for i in sorted(set(col_idxs)):
        cur.execute(f'SELECT COUNT("col{i}") FROM "{table_name}"')
        nn = int(cur.fetchone()[0])
        cur.execute(f'SELECT COUNT(DISTINCT "col{i}") FROM "{table_name}"')
        nd = int(cur.fetchone()[0])
        stats[f"col{i}_nonnull"] = nn
        stats[f"col{i}_ndistinct"] = max(nd, 1)  # Avoid division by zero
    return stats

def worker_validate_and_stats(args):
    """
    Worker function for parallel validation and statistics computation.

    Args:
        args: Tuple of (split_name, db_path, tasks_dict)

    Returns:
        Tuple of (validation_results, table_statistics)

    This function runs in a separate process to validate questions and compute
    table statistics for one split of the dataset.
    """
    split, db_path, tasks = args
    print(f"Worker starting validation for {split} split...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    out_valid = {}
    out_stats = {}

    tables_processed = 0
    for table, bundle in tasks.items():
        col_idxs = bundle["col_idxs"]
        out_stats[(split, table)] = _compute_table_stats(cur, table, col_idxs)
        for q in bundle["questions"]:
            ok = _validate_question(cur, table, q["agg"], q["sel"], q["conds"])
            out_valid[q["uid"]] = ok
        tables_processed += 1
        if tables_processed % 100 == 0:
            print(f"  {split}: Processed {tables_processed} tables")

    conn.close()
    print(f"Worker completed {split} split: {len(out_valid)} questions validated")
    return out_valid, out_stats

def estimate_expected_rows(n_rows: int,
                           conds: List[List],
                           per_col_stats: Dict[int, Tuple[int, int]]) -> float:
    """
    Estimate the number of rows a query will return based on table statistics.

    Args:
        n_rows: Total number of rows in the table
        conds: List of WHERE conditions
        per_col_stats: Dictionary mapping column_idx to (non_null_count, distinct_count)

    Returns:
        Estimated number of rows the query will return

    Uses simple selectivity estimation assuming independence between conditions.
    Different operators have different estimated selectivity.
    """
    if n_rows <= 0:
        return 0.0
    if not conds:
        return float(n_rows)

    # Multiply selectivity of all conditions (independence assumption)
    p = 1.0
    for col_idx, op_idx, _ in conds:
        nn, nd = per_col_stats.get(col_idx, (n_rows, max(1, n_rows)))
        nonnull_frac = nn / max(n_rows, 1)
        if OP_MAP[op_idx] == "=":
            # Equality: 1/distinct_values of non-null rows
            frac = nonnull_frac * (1.0 / max(nd, 1))
        elif OP_MAP[op_idx] == "!=":
            # Inequality: (distinct-1)/distinct of non-null rows
            frac = nonnull_frac * (1.0 - 1.0 / max(nd, 1))
        else:
            # Range operators: assume 1/3 selectivity of non-null rows
            frac = nonnull_frac * 0.33
        p *= max(min(frac, 1.0), 0.0)
    # Ensure result is within reasonable bounds
    p = min(max(p, 1.0 / max(n_rows, 1)), 1.0)
    return p * n_rows

def main():
    """
    Main function that orchestrates the entire WikiSQL top-K selection process.

    Process overview:
    1. Download and extract WikiSQL data
    2. Load table metadata and questions from all splits
    3. Validate questions in parallel across splits
    4. Compute difficulty scores based on multiple factors
    5. Select top-K most difficult questions
    6. Create consolidated database with selected questions and tables
    """
    print("Starting WikiSQL Top-K Question Selection")
    ap = argparse.ArgumentParser(description="Build a top-K WikiSQL SQLite DB (no boost).")
    ap.add_argument("--data-dir", type=Path, default=Path(DEFAULT_DATA_DIR),
                    help=f"Directory containing WikiSQL data (jsonl and split .db files). Default: {DEFAULT_DATA_DIR}")
    ap.add_argument("--out", type=Path, default=Path(DEFAULT_OUT),
                    help=f"Output SQLite DB path. Default: {DEFAULT_OUT}")
    ap.add_argument("--k", type=int, default=DEFAULT_K,
                    help=f"Number of top questions to select. Default: {DEFAULT_K}")
    ap.add_argument("--processes", type=int, default=DEFAULT_PROCESSES,
                    help=f"Number of processes for split-parallel validation (<=3 makes sense). Default: {DEFAULT_PROCESSES}")
    ap.add_argument("--keep-source-data", action="store_true",
                    help="Preserve extracted source data after processing (default: False to save disk space)")
    args = ap.parse_args()

    print("Configuration:")
    print(f"  Data directory: {args.data_dir}")
    print(f"  Output database: {args.out}")
    print(f"  Top K questions: {args.k}")
    print(f"  Parallel processes: {args.processes}")
    print(f"  Keep source data: {args.keep_source_data}")

    args.out.parent.mkdir(parents=True, exist_ok=True)

    ensure_wikisql_data(args.data_dir)

    tables_meta = read_tables_jsonl(args.data_dir)
    splits = {
        "train": read_split_jsonl(args.data_dir, "train"),
        "dev":   read_split_jsonl(args.data_dir, "dev"),
        "test":  read_split_jsonl(args.data_dir, "test"),
    }

    print("Organizing questions by table and split for parallel processing...")
    uid = 0
    all_questions = []
    # Group questions by split and table for efficient batch processing
    per_split_tasks: Dict[str, Dict[str, Dict[str, Any]]] = {
        "train": defaultdict(_create_task_dict),
        "dev":   defaultdict(_create_task_dict),
        "test":  defaultdict(_create_task_dict)
    }

    total_questions = 0
    for split, rows in splits.items():
        print(f"Processing {len(rows)} questions from {split} split...")
        for q in rows:
            t = q["table_id"]
            q["uid"] = uid
            uid += 1
            # Track which columns are used for table statistics computation
            cols = [c[0] for c in q["conds"]] + [q["sel"]]
            per_split_tasks[split][t]["col_idxs"].update(cols)
            per_split_tasks[split][t]["questions"].append(q)
            all_questions.append(q)
            total_questions += 1

    print(f"Total questions loaded: {total_questions}")
    print("Starting parallel validation and statistics computation...")

    # Prepare jobs for parallel processing - one per split
    jobs = []
    extracted_dir = args.data_dir / "data"
    for split in ["train", "dev", "test"]:
        db_path = extracted_dir / f"{split}.db"
        if len(per_split_tasks[split]) == 0:
            continue
        print(f"Preparing job for {split}: {len(per_split_tasks[split])} tables")
        jobs.append((split, str(db_path), per_split_tasks[split]))

    # Run validation and statistics computation in parallel
    valid_map = {}
    table_stats = {}
    with cf.ProcessPoolExecutor(max_workers=args.processes) as ex:
        print(f"Executing {len(jobs)} parallel validation jobs...")
        for ok_map, stats in ex.map(worker_validate_and_stats, jobs):
            valid_map.update(ok_map)
            table_stats.update(stats)

    print(f"Validation complete: {len(valid_map)} questions processed")
    valid_count = sum(1 for v in valid_map.values() if v)
    print(f"Valid questions: {valid_count}/{len(valid_map)} ({100*valid_count/len(valid_map):.1f}%)")

    print("Setting up in-memory database for difficulty scoring...")
    # Use in-memory database for fast computation of difficulty metrics
    mem = sqlite3.connect(":memory:")
    mem.execute("PRAGMA journal_mode = MEMORY;")
    mem.execute("PRAGMA synchronous = OFF;")
    mem.execute("PRAGMA temp_store = MEMORY;")
    mem.execute("PRAGMA cache_size = -200000;")  # 200MB cache
    mem.create_function("json_array_length", 1, _json_array_length)

    mem.executescript("""
    CREATE TABLE questions_raw(
        uid INTEGER PRIMARY KEY,
        split TEXT NOT NULL,
        table_id TEXT NOT NULL,
        question TEXT NOT NULL,
        agg INTEGER NOT NULL,
        sel INTEGER NOT NULL,
        conds_json TEXT NOT NULL,
        is_valid INTEGER NOT NULL,
        q_words INTEGER NOT NULL,
        sql_text TEXT NOT NULL,
        clean_colnames_json TEXT NOT NULL,
        expected_rows REAL NOT NULL
    );

    CREATE TABLE wikisql_tables(
        split TEXT NOT NULL,
        table_id TEXT NOT NULL,
        header_json TEXT NOT NULL,
        types_json  TEXT NOT NULL,
        page_title TEXT,
        section_title TEXT,
        caption TEXT,
        page_id INTEGER,
        n_rows INTEGER NOT NULL,
        n_cols INTEGER NOT NULL,
        clean_colnames_json TEXT NOT NULL,
        PRIMARY KEY (split, table_id)
    );
    """)

    print("Computing question features and loading into temporary database...")
    q_batch = []
    for q in all_questions:
        tm = tables_meta[q["table_id"]]
        sql_text, proper_cols = build_sql_text(tm.table_id, tm.header, q["agg"], q["sel"], q["conds"])
        stats = table_stats.get((q["split"], q["table_id"]), {"n_rows": 0})
        n_rows = stats.get("n_rows", 0)
        # Prepare per-column statistics for row estimation
        per_col = {}
        for cidx in set([c[0] for c in q["conds"]]):
            nn = stats.get(f"col{cidx}_nonnull", n_rows)
            nd = stats.get(f"col{cidx}_ndistinct", max(1, n_rows))
            per_col[cidx] = (nn, nd)
        exp_rows = estimate_expected_rows(n_rows, q["conds"], per_col)
        q_batch.append((
            q["uid"], q["split"], q["table_id"], q["question"], q["agg"], q["sel"],
            json.dumps(q["conds"]), int(valid_map.get(q["uid"], False)), count_words(q["question"]),
            sql_text, json.dumps(proper_cols), float(exp_rows)
        ))

    mem.executemany("""
        INSERT INTO questions_raw
        (uid, split, table_id, question, agg, sel, conds_json, is_valid, q_words, sql_text, clean_colnames_json, expected_rows)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, q_batch)

    print("Loading table metadata into temporary database...")
    t_batch = []
    for split in ["train", "dev", "test"]:
        for t_id, tm in tables_meta.items():
            if (split, t_id) not in table_stats:
                continue
            n_rows = table_stats[(split, t_id)]["n_rows"]
            clean_cols = unique_names([sanitize_identifier(h) for h in tm.header])
            t_batch.append((split, t_id, json.dumps(tm.header), json.dumps(tm.types),
                            tm.page_title, tm.section_title, tm.caption, tm.page_id,
                            n_rows, len(tm.header), json.dumps(clean_cols)))
    mem.executemany("""
        INSERT INTO wikisql_tables
        (split, table_id, header_json, types_json, page_title, section_title, caption, page_id, n_rows, n_cols, clean_colnames_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, t_batch)

    print("Computing operator and aggregation rarity statistics...")
    # Compute global statistics for rarity-based scoring
    mem.executescript("""
    CREATE TEMP TABLE op_stats AS
    SELECT json_extract(j.value,'$[1]') AS op_idx, COUNT(*) AS cnt
    FROM questions_raw q, json_each(q.conds_json) j
    GROUP BY op_idx;

    CREATE TEMP TABLE agg_stats AS
    SELECT agg, COUNT(*) AS cnt
    FROM questions_raw
    GROUP BY agg;
    """)

    print("Computing difficulty scores using weighted feature combination...")
    # Create the main scoring query using the defined weights
    mem.executescript(f"""
    CREATE TEMP VIEW v_totals AS
    SELECT
      (SELECT SUM(cnt) FROM op_stats) AS total_op_cnt,
      (SELECT SUM(cnt) FROM agg_stats) AS total_agg_cnt;

    CREATE TEMP TABLE op_rarity_sum AS
    SELECT q.uid,
           COALESCE(SUM( (SELECT total_op_cnt FROM v_totals) * 1.0 / os.cnt ), 0.0) AS op_rarity_sum
    FROM questions_raw q
    LEFT JOIN json_each(q.conds_json) j
         ON 1=1
    LEFT JOIN op_stats os
         ON os.op_idx = json_extract(j.value,'$[1]')
    GROUP BY q.uid;

    CREATE TEMP TABLE cond_counts AS
    SELECT uid, json_array_length(conds_json) AS cond_count
    FROM questions_raw;

    CREATE TEMP TABLE agg_feats AS
    WITH t AS (SELECT total_agg_cnt FROM v_totals)
    SELECT q.uid,
           CASE WHEN q.agg=0 THEN 0 ELSE 1 END AS has_agg,
           CASE WHEN q.agg=0 THEN 0.0
                ELSE (SELECT total_agg_cnt FROM t) * 1.0 / (SELECT cnt FROM agg_stats WHERE agg=q.agg)
           END AS agg_rarity
    FROM questions_raw q;

    CREATE TABLE top_questions AS
    SELECT
      q.uid, q.split, q.table_id, q.question, q.agg, q.sel, q.conds_json,
      q.sql_text, q.clean_colnames_json,
      t.header_json, t.types_json, t.page_title, t.section_title, t.caption, t.page_id,
      t.n_rows, t.n_cols, q.q_words, q.expected_rows,
      cc.cond_count, ors.op_rarity_sum, af.has_agg, af.agg_rarity,
      ({WEIGHTS["cond_count"]} * cc.cond_count) +
      ({WEIGHTS["op_rarity_sum"]} * ors.op_rarity_sum) +
      ({WEIGHTS["has_agg"]} * af.has_agg) +
      ({WEIGHTS["agg_rarity"]} * af.agg_rarity) +
      ({WEIGHTS["n_rows"]} * MIN(t.n_rows, 10000)) +
      ({WEIGHTS["n_cols"]} * t.n_cols) +
      ({WEIGHTS["q_words"]} * q.q_words)
      AS difficulty_score
    FROM questions_raw q
    JOIN wikisql_tables t ON (t.split=q.split AND t.table_id=q.table_id)
    LEFT JOIN cond_counts cc ON cc.uid=q.uid
    LEFT JOIN op_rarity_sum ors ON ors.uid=q.uid
    LEFT JOIN agg_feats af ON af.uid=q.uid
    WHERE q.is_valid=1;

    CREATE TABLE topk AS
    SELECT * FROM top_questions
    ORDER BY difficulty_score DESC, uid ASC
    LIMIT {int(args.k)};
    """)

    print(f"Selecting top {args.k} most difficult questions...")
    total_candidates = mem.execute("SELECT COUNT(*) FROM top_questions").fetchone()[0]
    print(f"Found {total_candidates} valid questions for ranking")

    print("Creating output database and schema...")
    out = args.out
    if out.exists():
        print(f"Removing existing output file: {out}")
        out.unlink()
    dst = sqlite3.connect(out)
    dst.execute("PRAGMA journal_mode = WAL;")
    dst.execute("PRAGMA synchronous = NORMAL;")

    dst.executescript("""
    CREATE TABLE questions(
      uid INTEGER PRIMARY KEY,
      split TEXT NOT NULL,
      table_id TEXT NOT NULL,
      table_name TEXT NOT NULL,
      question TEXT NOT NULL,
      agg INTEGER NOT NULL,
      sel INTEGER NOT NULL,
      conds_json TEXT NOT NULL,
      sql_text TEXT NOT NULL,
      q_words INTEGER NOT NULL,
      n_rows INTEGER NOT NULL,
      n_cols INTEGER NOT NULL,
      cond_count INTEGER NOT NULL,
      op_rarity_sum REAL NOT NULL,
      has_agg INTEGER NOT NULL,
      agg_rarity REAL NOT NULL,
      difficulty_score REAL NOT NULL,
      expected_rows REAL NOT NULL
    );

    CREATE TABLE wikisql_tables(
      split TEXT NOT NULL,
      table_id TEXT NOT NULL,
      header_json TEXT NOT NULL,
      types_json  TEXT NOT NULL,
      clean_colnames_json TEXT NOT NULL,
      page_title TEXT,
      section_title TEXT,
      caption TEXT,
      page_id INTEGER,
      n_rows INTEGER NOT NULL,
      n_cols INTEGER NOT NULL,
      PRIMARY KEY (split, table_id)
    );
    """)

    print("Copying selected questions to output database...")
    rows = mem.execute("""
        SELECT uid, split, table_id, 'table_' || REPLACE(table_id, '-', '_') as table_name,
               question, agg, sel, conds_json,
               sql_text, q_words, n_rows, n_cols,
               cond_count, op_rarity_sum, has_agg, agg_rarity,
               difficulty_score, expected_rows
        FROM topk
    """).fetchall()
    dst.executemany("""
        INSERT INTO questions
        (uid, split, table_id, table_name, question, agg, sel, conds_json, sql_text, q_words, n_rows, n_cols,
         cond_count, op_rarity_sum, has_agg, agg_rarity, difficulty_score, expected_rows)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    print(f"Inserted {len(rows)} questions into output database")

    print("Copying table metadata to output database...")
    meta_rows = mem.execute("""
        SELECT DISTINCT t.split, t.table_id, t.header_json, t.types_json, t.clean_colnames_json,
                        t.page_title, t.section_title, t.caption, t.page_id, t.n_rows, t.n_cols
        FROM wikisql_tables t
        JOIN topk k ON (k.split=t.split AND k.table_id=t.table_id)
    """).fetchall()
    dst.executemany("""
        INSERT INTO wikisql_tables
        (split, table_id, header_json, types_json, clean_colnames_json,
         page_title, section_title, caption, page_id, n_rows, n_cols)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, meta_rows)
    print(f"Inserted metadata for {len(meta_rows)} tables")

    print("Copying actual table data with cleaned column names...")
    used = {(r[0], r[1]) for r in meta_rows}
    extracted_dir = args.data_dir / "data"
    for split in ["train", "dev", "test"]:
        dst.execute(f"ATTACH DATABASE ? AS {split}_db", (str(extracted_dir / f"{split}.db"),))

    tables_copied = 0
    for split, table_id in sorted(used):
        if tables_copied % 50 == 0:
            print(f"  Copied {tables_copied}/{len(used)} tables...")
        clean_cols = json.loads(dst.execute("""
            SELECT clean_colnames_json FROM wikisql_tables
            WHERE split=? AND table_id=?""", (split, table_id)).fetchone()[0])
        select_list = ", ".join([f'"col{i}" AS "{clean_cols[i]}"' for i in range(len(clean_cols))])
        derived_name = derived_table_name(table_id)
        dst.execute(f'CREATE TABLE "{derived_name}" AS SELECT {select_list} FROM {split}_db."{derived_name}"')
        tables_copied += 1

    dst.executescript("""
        CREATE VIEW v_top500_questions AS
        SELECT
          q.question,
          q.sql_text,
          q.table_name,
          wt.n_rows,
          wt.page_title,
          wt.section_title,
          wt.caption
        FROM questions q
        JOIN wikisql_tables wt
          ON wt.table_id = q.table_id AND wt.split = q.split
        ORDER BY q.difficulty_score DESC;
    """)

    dst.commit()
    dst.close()
    mem.close()

    print(f"Output database created successfully: {args.out}")

    if not args.keep_source_data:
        print("Cleaning up temporary source data...")
        extracted_data_dir = args.data_dir / "data"
        if extracted_data_dir.exists():
            shutil.rmtree(extracted_data_dir)

        for split_file in ["train.jsonl", "dev.jsonl", "test.jsonl", "tables.jsonl"]:
            split_path = args.data_dir / split_file
            if split_path.exists():
                split_path.unlink()

if __name__ == "__main__":
    main()
