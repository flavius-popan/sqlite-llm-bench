#!/usr/bin/env python3
"""
Build a compact SQLite DB with the top-K most "difficult" WikiSQL NL→SQL examples.

What goes into the final DB:
  1) questions ............ the top-K ranked items with features + difficulty score
  2) wikisql_tables ....... metadata for referenced tables (headers, types, row counts)
  3) physical tables ...... copied from the official split DBs with clean, unique column names

Scoring (pure SQL; constants below):
  difficulty_score =
      1.5 * cond_count
    + 0.9 * op_rarity_sum
    + 0.8 * has_agg
    + 0.7 * agg_rarity
    + 0.001 * MIN(n_rows, 10000)
    + 0.25 * n_cols
    + 0.05 * q_words
    + 0.5 * has_hard_ops

Notes:
- We also compute an *expected_rows* (schema-only estimate) to help reason about
  selectivity in small tables (<50 rows). It is **not** used for ranking.
"""

from __future__ import annotations
import argparse
import bz2
import concurrent.futures as cf
import io
import json
import re
import sqlite3
import string
import sys
import tarfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple, Any

# ------------------------------------------------------------
# Constants
# ------------------------------------------------------------

DATA_URL = "https://raw.githubusercontent.com/salesforce/WikiSQL/master/data.tar.bz2"

AGG_MAP = {
    0: None,   # NONE
    1: "MAX",
    2: "MIN",
    3: "COUNT",
    4: "SUM",
    5: "AVG",
}

OP_MAP = {
    0: "=",
    1: ">",
    2: "<",
    3: ">=",
    4: "<=",
    5: "!=",
}

HARD_OPS = {3, 4, 5}  # >=, <=, !=

# Scoring weights (keep in one place, easy to tweak)
WEIGHTS = {
    "cond_count": 1.5,
    "op_rarity_sum": 0.9,
    "has_agg": 0.8,
    "agg_rarity": 0.7,
    "n_rows": 0.001,  # applied to MIN(n_rows, 10000)
    "n_cols": 0.25,
    "q_words": 0.05,
    "has_hard_ops": 0.5,
}

# Default values for command line arguments
DEFAULT_DATA_DIR = "data/raw/wikisql"
DEFAULT_OUT = "wikisql_top500.db"
DEFAULT_K = 500
DEFAULT_PROCESSES = 3

# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------

def _create_task_dict():
    """Helper function to create task dictionary for defaultdict."""
    return {"col_idxs": set(), "questions": []}

def _json_array_length(s):
    """Helper function to get JSON array length for SQLite function."""
    return len(json.loads(s)) if s else 0

def derived_table_name(table_id: str) -> str:
    """Convert table_id from format '1-1000181-1' to 'table_1_1000181_1'."""
    return "table_" + table_id.replace("-", "_")

def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)

def ensure_wikisql_data(data_dir: Path) -> None:
    """Ensure WikiSQL files exist under data_dir; otherwise download & extract."""
    expected = ["train.jsonl", "dev.jsonl", "test.jsonl",
                "tables.jsonl", "train.db", "dev.db", "test.db"]
    if all((data_dir / f).exists() for f in expected):
        return
    data_dir.mkdir(parents=True, exist_ok=True)
    archive = data_dir / "data.tar.bz2"
    if not archive.exists():
        import urllib.request
        log("Downloading WikiSQL data.tar.bz2 ...")
        urllib.request.urlretrieve(DATA_URL, archive)
    log("Extracting data.tar.bz2 ...")
    with bz2.BZ2File(archive, "rb") as f_in:
        with tarfile.open(fileobj=io.BytesIO(f_in.read())) as tf:
            tf.extractall(data_dir, filter='data')

def sanitize_identifier(name: str) -> str:
    """Turn an arbitrary column header into a safe SQL identifier."""
    # Lowercase, remove accents-ish (basic), replace non-alnum with underscores.
    name = name.strip().lower()
    # Keep letters, numbers, underscore only
    allowed = set(string.ascii_lowercase + string.digits + "_")
    cleaned = []
    prev_us = False
    for ch in name:
        ch = ch if ch in allowed else "_"
        if ch == "_" and prev_us:
            continue
        prev_us = (ch == "_")
        cleaned.append(ch)
    s = "".join(cleaned).strip("_")
    if not s:
        s = "col"
    if s[0].isdigit():
        s = "_" + s
    return s

def unique_names(names: List[str]) -> List[str]:
    """Ensure column names are unique with suffixes _1, _2, ..."""
    seen = {}
    out = []
    for n in names:
        base = n
        i = seen.get(base, 0)
        if i == 0 and base not in seen:
            out.append(base)
            seen[base] = 1
        else:
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
    Build a human-readable single-table SQL using sanitized, unique identifiers.
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
        else:
            # Quote single quotes
            val_sql = "'" + str(val).replace("'", "''") + "'"
        cond_parts.append(f'"{col_name}" {op} {val_sql}')
    where = (" WHERE " + " AND ".join(cond_parts)) if cond_parts else ""
    table_name = derived_table_name(table)
    return f'SELECT {select_expr} FROM "{table_name}"{where};', proper

def count_words(s: str) -> int:
    return len([w for w in re.split(r"\s+", s.strip()) if w])

# ------------------------------------------------------------
# Data loading
# ------------------------------------------------------------

@dataclass
class TableMeta:
    table_id: str
    header: List[str]
    types: List[str]
    page_title: str
    section_title: str
    caption: str
    page_id: int

def read_tables_jsonl(data_dir: Path) -> Dict[str, TableMeta]:
    """Read table metadata from all split table files."""
    meta = {}
    extracted_dir = data_dir / "data"
    for split in ["train", "dev", "test"]:
        table_file = extracted_dir / f"{split}.tables.jsonl"
        if table_file.exists():
            with table_file.open("r", encoding="utf-8") as f:
                for line in f:
                    obj = json.loads(line)
                    if obj["id"] not in meta:  # Avoid duplicates
                        meta[obj["id"]] = TableMeta(
                            table_id=obj["id"],
                            header=obj["header"],
                            types=obj["types"],
                            page_title=obj.get("page_title", ""),
                            section_title=obj.get("section_title", ""),
                            caption=obj.get("caption", ""),
                            page_id=int(obj.get("page_id", -1)),
                        )
    return meta

def read_split_jsonl(data_dir: Path, split: str) -> List[dict]:
    extracted_dir = data_dir / "data"
    p = extracted_dir / f"{split}.jsonl"
    out = []
    with p.open("r", encoding="utf-8") as f:
        for row in f:
            j = json.loads(row)
            out.append({
                "qid": f"{split}_{len(out)}",  # generate unique id for traceability
                "split": split,
                "table_id": j["table_id"],
                "question": j["question"],
                "agg": int(j["sql"]["agg"]),
                "sel": int(j["sql"]["sel"]),
                "conds": [[int(c[0]), int(c[1]), c[2]] for c in j["sql"]["conds"]],
            })
    return out

# ------------------------------------------------------------
# Per-split worker: validation + minimal column stats
# ------------------------------------------------------------

def _mk_where_and_params(conds: List[List]) -> Tuple[str, List]:
    if not conds:
        return "", []
    parts, params = [], []
    for col_idx, op_idx, val in conds:
        op = OP_MAP[op_idx]
        parts.append(f'"col{col_idx}" {op} ?')
        params.append(val)
    return " WHERE " + " AND ".join(parts), params

def _validate_question(cur: sqlite3.Cursor, table: str, agg: int, sel: int, conds: List[List]) -> bool:
    where_sql, params = _mk_where_and_params(conds)
    table_name = derived_table_name(table)
    if agg == 0:  # NONE
        q = f'SELECT COUNT(*) FROM "{table_name}"{where_sql} AND "col{sel}" IS NOT NULL' if where_sql else \
            f'SELECT COUNT(*) FROM "{table_name}" WHERE "col{sel}" IS NOT NULL'
        cur.execute(q, params)
        return cur.fetchone()[0] > 0
    if agg == 3:  # COUNT
        q = f'SELECT COUNT(*) FROM "{table_name}"{where_sql}'
        cur.execute(q, params)
        return cur.fetchone()[0] > 0
    else:  # MAX/MIN/SUM/AVG
        agg_kw = AGG_MAP[agg]
        q = f'SELECT {agg_kw}("col{sel}") FROM "{table_name}"{where_sql}'
        cur.execute(q, params)
        return cur.fetchone()[0] is not None

def _compute_table_stats(cur: sqlite3.Cursor, table: str, col_idxs: Iterable[int]) -> dict:
    stats = {}
    table_name = derived_table_name(table)
    cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
    n_rows = int(cur.fetchone()[0])
    stats["n_rows"] = n_rows
    # For requested columns only
    for i in sorted(set(col_idxs)):
        cur.execute(f'SELECT COUNT("col{i}") FROM "{table_name}"')
        nn = int(cur.fetchone()[0])
        cur.execute(f'SELECT COUNT(DISTINCT "col{i}") FROM "{table_name}"')
        nd = int(cur.fetchone()[0])
        stats[f"col{i}_nonnull"] = nn
        stats[f"col{i}_ndistinct"] = max(nd, 1)
    return stats

def worker_validate_and_stats(args):
    split, db_path, tasks = args  # tasks: dict(table_id -> {"col_idxs": set, "questions": [qdict,...]})
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    out_valid = {}
    out_stats = {}
    for table, bundle in tasks.items():
        # stats first
        col_idxs = bundle["col_idxs"]
        out_stats[(split, table)] = _compute_table_stats(cur, table, col_idxs)
        # validation
        for q in bundle["questions"]:
            ok = _validate_question(cur, table, q["agg"], q["sel"], q["conds"])
            out_valid[q["uid"]] = ok
    conn.close()
    return out_valid, out_stats

# ------------------------------------------------------------
# Expected rows estimator (schema-only; tiny & conservative)
# ------------------------------------------------------------

def estimate_expected_rows(n_rows: int,
                           conds: List[List],
                           per_col_stats: Dict[int, Tuple[int, int]]) -> float:
    """
    Estimate the expected number of rows that satisfy conds.

    For each condition on column j with (nonnull_count, n_distinct):
      - '='  -> p ≈ (nonnull/n_rows) * (1 / n_distinct)
      - '!=' -> p ≈ (nonnull/n_rows) * (1 - 1 / n_distinct)
      - {>,<,>=,<=} -> p ≈ (nonnull/n_rows) * 0.33  # small tables: rough one-third
    Combine assuming independence; clamp to [1/n_rows, 1] if any conds exist.
    """
    if n_rows <= 0:
        return 0.0
    if not conds:
        return float(n_rows)
    p = 1.0
    for col_idx, op_idx, _ in conds:
        nn, nd = per_col_stats.get(col_idx, (n_rows, max(1, n_rows)))
        nonnull_frac = nn / max(n_rows, 1)
        if OP_MAP[op_idx] == "=":
            frac = nonnull_frac * (1.0 / max(nd, 1))
        elif OP_MAP[op_idx] == "!=":
            frac = nonnull_frac * (1.0 - 1.0 / max(nd, 1))
        else:  # inequalities
            frac = nonnull_frac * 0.33
        p *= max(min(frac, 1.0), 0.0)
    # Smoothing: for small tables avoid collapsing to zero
    p = min(max(p, 1.0 / max(n_rows, 1)), 1.0)
    return p * n_rows

# ------------------------------------------------------------
# Main build
# ------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Build a top-K WikiSQL SQLite DB (no boost).")
    ap.add_argument("--data-dir", type=Path, default=Path(DEFAULT_DATA_DIR),
                    help=f"Directory containing WikiSQL data (jsonl and split .db files). Default: {DEFAULT_DATA_DIR}")
    ap.add_argument("--out", type=Path, default=Path(DEFAULT_OUT),
                    help=f"Output SQLite DB path. Default: {DEFAULT_OUT}")
    ap.add_argument("--k", type=int, default=DEFAULT_K,
                    help=f"Number of top questions to select. Default: {DEFAULT_K}")
    ap.add_argument("--processes", type=int, default=DEFAULT_PROCESSES,
                    help=f"Number of processes for split-parallel validation (<=3 makes sense). Default: {DEFAULT_PROCESSES}")
    args = ap.parse_args()

    ensure_wikisql_data(args.data_dir)

    # Load metadata & examples
    tables_meta = read_tables_jsonl(args.data_dir)
    splits = {
        "train": read_split_jsonl(args.data_dir, "train"),
        "dev":   read_split_jsonl(args.data_dir, "dev"),
        "test":  read_split_jsonl(args.data_dir, "test"),
    }

    # Build per-table tasks for workers and enumerate all questions
    uid = 0
    all_questions = []
    per_split_tasks: Dict[str, Dict[str, Dict[str, Any]]] = {
        "train": defaultdict(_create_task_dict),
        "dev":   defaultdict(_create_task_dict),
        "test":  defaultdict(_create_task_dict)
    }

    for split, rows in splits.items():
        for q in rows:
            t = q["table_id"]
            q["uid"] = uid
            uid += 1
            # Track which columns we need stats on (conds + sel)
            cols = [c[0] for c in q["conds"]] + [q["sel"]]
            per_split_tasks[split][t]["col_idxs"].update(cols)
            per_split_tasks[split][t]["questions"].append(q)
            all_questions.append(q)

    # Parallel validation + stats by split
    jobs = []
    extracted_dir = args.data_dir / "data"
    for split in ["train", "dev", "test"]:
        db_path = extracted_dir / f"{split}.db"
        if len(per_split_tasks[split]) == 0:
            continue
        jobs.append((split, str(db_path), per_split_tasks[split]))

    log("Validating questions and collecting minimal stats (parallel by split) ...")
    valid_map = {}
    table_stats = {}
    with cf.ProcessPoolExecutor(max_workers=args.processes) as ex:
        for ok_map, stats in ex.map(worker_validate_and_stats, jobs):
            valid_map.update(ok_map)
            table_stats.update(stats)

    # Prepare in-memory build DB (faster) with relaxed PRAGMAs
    log("Building features in an in-memory SQLite DB ...")
    mem = sqlite3.connect(":memory:")
    mem.execute("PRAGMA journal_mode = MEMORY;")
    mem.execute("PRAGMA synchronous = OFF;")
    mem.execute("PRAGMA temp_store = MEMORY;")
    mem.execute("PRAGMA cache_size = -200000;")  # ~200MB
    mem.create_function("json_array_length", 1, _json_array_length)

    # Create raw tables
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

    # Batch insert questions_raw
    q_batch = []
    for q in all_questions:
        tm = tables_meta[q["table_id"]]
        sql_text, proper_cols = build_sql_text(tm.table_id, tm.header, q["agg"], q["sel"], q["conds"])
        stats = table_stats.get((q["split"], q["table_id"]), {"n_rows": 0})
        n_rows = stats.get("n_rows", 0)
        # pack per-column stats for estimator
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

    # Batch insert wikisql_tables (with row/col counts & clean colnames)
    t_batch = []
    for split in ["train", "dev", "test"]:
        for t_id, tm in tables_meta.items():
            # Skip tables not in this split to reduce size in memory DB
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

    # TEMP stats tables (simple, ephemeral)
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

    # Final top-K table in one SQL
    # - Computes per-question features
    # - Applies weights
    # - Filters invalid items
    # - Ranks and selects top K
    mem.executescript(f"""
    -- convenience totals
    CREATE TEMP VIEW v_totals AS
    SELECT
      (SELECT SUM(cnt) FROM op_stats) AS total_op_cnt,
      (SELECT SUM(cnt) FROM agg_stats) AS total_agg_cnt;

    -- per-question op rarity sum
    CREATE TEMP TABLE op_rarity_sum AS
    SELECT q.uid,
           COALESCE(SUM( (SELECT total_op_cnt FROM v_totals) * 1.0 / os.cnt ), 0.0) AS op_rarity_sum
    FROM questions_raw q
    LEFT JOIN json_each(q.conds_json) j
         ON 1=1
    LEFT JOIN op_stats os
         ON os.op_idx = json_extract(j.value,'$[1]')
    GROUP BY q.uid;

    -- per-question has_hard_ops
    CREATE TEMP TABLE has_hard AS
    SELECT q.uid,
           CASE WHEN EXISTS (
             SELECT 1
             FROM json_each(q.conds_json) jj
             WHERE json_extract(jj.value,'$[1]') IN (3,4,5)
           ) THEN 1 ELSE 0 END AS has_hard_ops
    FROM questions_raw q;

    -- per-question cond_count
    CREATE TEMP TABLE cond_counts AS
    SELECT uid, json_array_length(conds_json) AS cond_count
    FROM questions_raw;

    -- per-question agg_rarity and has_agg
    CREATE TEMP TABLE agg_feats AS
    WITH t AS (SELECT total_agg_cnt FROM v_totals)
    SELECT q.uid,
           CASE WHEN q.agg=0 THEN 0 ELSE 1 END AS has_agg,
           CASE WHEN q.agg=0 THEN 0.0
                ELSE (SELECT total_agg_cnt FROM t) * 1.0 / (SELECT cnt FROM agg_stats WHERE agg=q.agg)
           END AS agg_rarity
    FROM questions_raw q;

    -- Join everything & compute difficulty
    CREATE TABLE top_questions AS
    SELECT
      q.uid, q.split, q.table_id, q.question, q.agg, q.sel, q.conds_json,
      q.sql_text, q.clean_colnames_json,
      t.header_json, t.types_json, t.page_title, t.section_title, t.caption, t.page_id,
      t.n_rows, t.n_cols, q.q_words, q.expected_rows,
      cc.cond_count, hr.has_hard_ops, ors.op_rarity_sum, af.has_agg, af.agg_rarity,
      -- difficulty score (no boosts)
      ({WEIGHTS["cond_count"]} * cc.cond_count) +
      ({WEIGHTS["op_rarity_sum"]} * ors.op_rarity_sum) +
      ({WEIGHTS["has_agg"]} * af.has_agg) +
      ({WEIGHTS["agg_rarity"]} * af.agg_rarity) +
      ({WEIGHTS["n_rows"]} * MIN(t.n_rows, 10000)) +
      ({WEIGHTS["n_cols"]} * t.n_cols) +
      ({WEIGHTS["q_words"]} * q.q_words) +
      ({WEIGHTS["has_hard_ops"]} * hr.has_hard_ops)
      AS difficulty_score
    FROM questions_raw q
    JOIN wikisql_tables t ON (t.split=q.split AND t.table_id=q.table_id)
    LEFT JOIN cond_counts cc ON cc.uid=q.uid
    LEFT JOIN has_hard hr ON hr.uid=q.uid
    LEFT JOIN op_rarity_sum ors ON ors.uid=q.uid
    LEFT JOIN agg_feats af ON af.uid=q.uid
    WHERE q.is_valid=1;

    -- Materialize just the top K now; smaller + easier to copy out.
    CREATE TABLE topk AS
    SELECT * FROM top_questions
    ORDER BY difficulty_score DESC, uid ASC
    LIMIT {int(args.k)};
    """)

    # Build final on-disk DB
    out = args.out
    if out.exists():
        out.unlink()
    dst = sqlite3.connect(out)
    # Restore durability for the final DB
    dst.execute("PRAGMA journal_mode = WAL;")
    dst.execute("PRAGMA synchronous = NORMAL;")

    # Core tables (questions + table metadata)
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
      has_hard_ops INTEGER NOT NULL,
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

    # Populate questions + metadata from in-memory topk
    rows = mem.execute("""
        SELECT uid, split, table_id, 'table_' || REPLACE(table_id, '-', '_') as table_name,
               question, agg, sel, conds_json,
               sql_text, q_words, n_rows, n_cols,
               cond_count, has_hard_ops, op_rarity_sum, has_agg, agg_rarity,
               difficulty_score, expected_rows
        FROM topk
    """).fetchall()
    dst.executemany("""
        INSERT INTO questions
        (uid, split, table_id, table_name, question, agg, sel, conds_json, sql_text, q_words, n_rows, n_cols,
         cond_count, has_hard_ops, op_rarity_sum, has_agg, agg_rarity, difficulty_score, expected_rows)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)

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

    # Copy physical source tables referenced by top-K, renaming columns to clean names
    log("Copying referenced physical tables with clean column names ...")
    used = {(r[0], r[1]) for r in meta_rows}
    # Attach the split DBs once
    extracted_dir = args.data_dir / "data"
    for split in ["train", "dev", "test"]:
        dst.execute(f"ATTACH DATABASE ? AS {split}_db", (str(extracted_dir / f"{split}.db"),))
    for split, table_id in sorted(used):
        clean_cols = json.loads(dst.execute("""
            SELECT clean_colnames_json FROM wikisql_tables
            WHERE split=? AND table_id=?""", (split, table_id)).fetchone()[0])
        # Build CREATE TABLE AS SELECT mapping col0.. to clean names
        select_list = ", ".join([f'"col{i}" AS "{clean_cols[i]}"' for i in range(len(clean_cols))])
        derived_name = derived_table_name(table_id)
        dst.execute(f'CREATE TABLE "{derived_name}" AS SELECT {select_list} FROM {split}_db."{derived_name}"')

    # Finalize
    dst.commit()
    dst.close()
    mem.close()
    log(f"Done. Wrote {args.k} items to {out}.")


if __name__ == "__main__":
    main()
