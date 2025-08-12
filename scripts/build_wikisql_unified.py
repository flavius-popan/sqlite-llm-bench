#!/usr/bin/env python3
"""
Build a single WikiSQL SQLite DB from the original compressed dataset.

What you get:
- Many data tables: table_1_... copied as-is from train/dev/test (column names are the real headers)
- questions(split, table_id, table_name, question, agg, sel_col_idx, conds_json, sql_text?)
- wikisql_tables(table_name, split, table_id, header_json, types_json, n_rows, pretty_name, page_title, section_title, caption, page_id)
- op_map(op_idx, symbol)
- v_questions_with_schema (view)
- v_tables_browse (view) exposing a "display_name" that uses pretty_name if available

CLI:
  python scripts/build_wikisql_unified.py [--src <URL-or-path>]

Defaults:
  --src defaults to the canonical GitHub raw: https://raw.githubusercontent.com/salesforce/WikiSQL/master/data.tar.bz2
  Output: data/processed/wikisql/wikisql-v1.sqlite
"""
import os
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

import argparse
import json
import sqlite3
import sys
import tarfile
from pathlib import Path
from typing import Dict, List

DEFAULT_URL = "https://raw.githubusercontent.com/salesforce/WikiSQL/master/data.tar.bz2"

try:
    import requests  # only needed if --src is a URL
except ImportError:
    requests = None


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def download_to_bytes(url: str) -> bytes:
    if requests is None:
        raise RuntimeError("The 'requests' package is required to download from URLs. Install it or pass a local --src path.")
    eprint(f"Downloading: {url}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content


def extract_tar_bz2(archive: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, mode="r:bz2") as tar:
        tar.extractall(path=dest_dir, filter='data')
    return dest_dir


def quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def quote_literal(val: str) -> str:
    return "'" + str(val).replace("'", "''") + "'"


AGG_MAP = {0: None, 1: "MAX", 2: "MIN", 3: "COUNT", 4: "SUM", 5: "AVG"}
OP_MAP_BASE = {0: "=", 1: ">", 2: "<"}
OP_EXTS = {3: ">=", 4: "<=", 5: "!="}


def derived_table_name(table_id: str) -> str:
    return "table_" + table_id.replace("-", "_")


def validate_split_files(extracted_root: Path) -> Dict[str, Dict[str, Path]]:
    """Validate that all required split files exist and return their paths."""
    data_dir = extracted_root / "data"
    if not data_dir.exists():
        raise RuntimeError(f"Could not find 'data/' directory under extracted root: {extracted_root}")

    splits = ["train", "dev", "test"]
    split_files = {}
    for s in splits:
        dbp = data_dir / f"{s}.db"
        tbl = data_dir / f"{s}.tables.jsonl"
        exm = data_dir / f"{s}.jsonl"
        if not dbp.exists() or not tbl.exists() or not exm.exists():
            raise RuntimeError(f"Missing files for split '{s}'. Expected: {dbp}, {tbl}, {exm}")
        split_files[s] = {"db": dbp, "tables": tbl, "examples": exm}
    return split_files


def setup_database(out_db: Path) -> sqlite3.Connection:
    """Create and configure the output database with schema."""
    if out_db.exists():
        out_db.unlink()

    # Ensure the output directory exists
    out_db.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(out_db))
    conn.execute("PRAGMA journal_mode = MEMORY;")
    conn.execute("PRAGMA synchronous = OFF;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("PRAGMA cache_size = -200000;")

    conn.executescript("""
        CREATE TABLE wikisql_tables (
            table_name TEXT PRIMARY KEY,
            split TEXT NOT NULL CHECK (split IN ('train','dev','test')),
            table_id TEXT NOT NULL,
            header_json TEXT NOT NULL,
            types_json TEXT NOT NULL,
            n_rows INTEGER NOT NULL,
            pretty_name TEXT,
            page_title TEXT,
            section_title TEXT,
            caption TEXT,
            page_id TEXT
        );

        CREATE TABLE questions (
            id INTEGER PRIMARY KEY,
            split TEXT NOT NULL CHECK (split IN ('train','dev','test')),
            table_id TEXT NOT NULL,
            table_name TEXT NOT NULL,
            question TEXT NOT NULL,
            agg INTEGER NOT NULL,
            sel_col_idx INTEGER NOT NULL,
            conds_json TEXT NOT NULL,
            sql_text TEXT
        );

        CREATE INDEX idx_questions_table    ON questions(table_name);
        CREATE INDEX idx_questions_split    ON questions(split);
        CREATE INDEX idx_questions_table_id ON questions(table_id);

        CREATE TABLE op_map (op_idx INTEGER PRIMARY KEY, symbol TEXT NOT NULL);
    """)
    return conn


def copy_tables_from_splits(conn: sqlite3.Connection, split_files: Dict[str, Dict[str, Path]]) -> None:
    """Copy all data tables from split databases to the unified database."""
    seen_tables = set()
    for split, files in split_files.items():
        alias = f"{split}_db"
        conn.execute(f"ATTACH DATABASE ? AS {alias}", (str(files["db"]),))
        cur = conn.execute(f"SELECT name FROM {alias}.sqlite_master WHERE type='table' AND name LIKE 'table_%'")
        names = [r[0] for r in cur.fetchall()]
        eprint(f"[{split}] copying {len(names)} tables")
        for tname in names:
            if tname in seen_tables:
                raise RuntimeError(f"Duplicate table name across splits: {tname}")
            seen_tables.add(tname)
            conn.execute(f'CREATE TABLE {quote_ident(tname)} AS SELECT * FROM {alias}.{quote_ident(tname)};')
        conn.execute(f"DETACH DATABASE {alias}")


def process_table_metadata(conn: sqlite3.Connection, split_files: Dict[str, Dict[str, Path]]) -> Dict[str, List[str]]:
    """Process table metadata from JSONL files and return table headers."""
    table_headers: Dict[str, List[str]] = {}
    table_types: Dict[str, List[str]] = {}

    for split, files in split_files.items():
        with files["tables"].open("r", encoding="utf-8") as f:
            count = 0
            for line in f:
                obj = json.loads(line)
                tid = obj["id"]
                tname = derived_table_name(tid)
                header = obj.get("header", [])
                types = obj.get("types", [])
                table_headers[tname] = header
                table_types[tname] = types
                pretty_name = obj.get("name")
                page_title = obj.get("page_title")
                section_title = obj.get("section_title")
                caption = obj.get("caption")
                page_id = obj.get("page_id")

                try:
                    n_rows = conn.execute(f"SELECT COUNT(*) FROM {quote_ident(tname)}").fetchone()[0]
                except sqlite3.OperationalError as e:
                    raise RuntimeError(f"Expected table {tname} from split {split} not found in merged DB") from e

                conn.execute(
                    """INSERT INTO wikisql_tables
                       (table_name, split, table_id, header_json, types_json, n_rows, pretty_name, page_title, section_title, caption, page_id)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (tname, split, tid,
                     json.dumps(header, ensure_ascii=False),
                     json.dumps(types, ensure_ascii=False),
                     n_rows, pretty_name, page_title, section_title, caption, None if page_id is None else str(page_id))
                )
                count += 1
        eprint(f"[{split}] registered {count} table metadata rows")
    return table_headers


def build_operator_mapping(conn: sqlite3.Connection, split_files: Dict[str, Dict[str, Path]]) -> Dict[int, str]:
    """Build and populate the operator mapping table."""
    observed_ops = set()
    for split, files in split_files.items():
        with files["examples"].open("r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                conds = obj.get("sql", {}).get("conds", [])
                for c in conds:
                    if isinstance(c, list) and len(c) >= 2:
                        observed_ops.add(int(c[1]))

    op_map = dict(OP_MAP_BASE)
    for op_idx in sorted(observed_ops):
        if op_idx not in op_map:
            op_map[op_idx] = OP_EXTS.get(op_idx, "=")
    for k, v in sorted(op_map.items()):
        conn.execute("INSERT INTO op_map (op_idx, symbol) VALUES (?,?)", (k, v))
    return op_map


def build_sql_text(table_name: str, sel_idx: int, agg: int, conds: list,
                   table_headers: Dict[str, List[str]], op_map: Dict[int, str]) -> str:
    """Build SQL text from structured query components."""
    header = table_headers.get(table_name)
    if header is None:
        raise RuntimeError(f"No header known for table {table_name}")
    if not (0 <= sel_idx < len(header)):
        raise RuntimeError(f"sel_col_idx {sel_idx} out of bounds for table {table_name}")
    sel_col = header[sel_idx]
    agg_name = AGG_MAP.get(agg)
    sel_expr = f"{quote_ident(sel_col)}" if agg_name is None else f"{agg_name}({quote_ident(sel_col)})"
    where = []
    for c in conds or []:
        if not isinstance(c, list) or len(c) < 3:
            continue
        col_idx, op_idx, value = int(c[0]), int(c[1]), c[2]
        if not (0 <= col_idx < len(header)):
            raise RuntimeError(f"cond col_idx {col_idx} out of bounds for table {table_name}")
        op = op_map.get(op_idx)
        if op is None:
            raise RuntimeError(f"Unknown operator index {op_idx}")
        where.append(f"{quote_ident(header[col_idx])} {op} {quote_literal(str(value))}")
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    return f"SELECT {sel_expr} FROM {quote_ident(table_name)}{where_sql};"


def process_questions(conn: sqlite3.Connection, split_files: Dict[str, Dict[str, Path]],
                     table_headers: Dict[str, List[str]], op_map: Dict[int, str]) -> int:
    """Process questions from JSONL files and return total count inserted."""
    inserted = 0
    for split, files in split_files.items():
        eprint(f"[{split}] ingesting questions…")
        with files["examples"].open("r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                tid = obj["table_id"]
                tname = derived_table_name(tid)
                question = obj["question"]
                sql_obj = obj.get("sql", {})
                sel = int(sql_obj.get("sel", 0))
                agg = int(sql_obj.get("agg", 0))
                conds = sql_obj.get("conds", [])
                sql_text = build_sql_text(tname, sel, agg, conds, table_headers, op_map)
                conn.execute(
                    "INSERT INTO questions (split, table_id, table_name, question, agg, sel_col_idx, conds_json, sql_text) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (split, tid, tname, question, agg, sel, json.dumps(conds, ensure_ascii=False), sql_text)
                )
                inserted += 1
        eprint(f"[{split}] inserted questions: (cumulative) {inserted}")
    return inserted


def create_views(conn: sqlite3.Connection) -> None:
    """Create database views for easier querying."""
    conn.executescript("""
        CREATE VIEW v_questions_with_schema AS
        SELECT q.*, wt.header_json, wt.types_json, wt.n_rows
        FROM questions q
        JOIN wikisql_tables wt ON wt.table_name = q.table_name;

        CREATE VIEW v_tables_browse AS
        SELECT
          table_name,
          COALESCE(NULLIF(TRIM(pretty_name), ''), table_name) AS display_name,
          split,
          table_id,
          n_rows,
          page_title,
          section_title,
          caption
        FROM wikisql_tables;
    """)


def validate_queries(conn: sqlite3.Connection, table_headers: Dict[str, List[str]], op_map: Dict[int, str]) -> int:
    """Validate all reconstructed queries by executing them."""
    eprint("Validating all reconstructed queries by executing them…")
    validation_errors = 0
    sel = conn.execute("SELECT id, table_name, agg, sel_col_idx, conds_json, sql_text FROM questions").fetchall()
    for qid, tname, agg, sel_idx, conds_json, sql_text in sel:
        if sql_text is None:
            conds = json.loads(conds_json)
            try:
                sql_text = build_sql_text(tname, int(sel_idx), int(agg), conds, table_headers, op_map)
            except Exception:
                validation_errors += 1
                raise
        try:
            conn.execute(sql_text).fetchone()
        except Exception:
            validation_errors += 1
            raise
    return validation_errors


def build_unified_db(extracted_root: Path, out_db: Path) -> dict:
    """Build unified WikiSQL SQLite database from extracted data."""
    split_files = validate_split_files(extracted_root)
    conn = setup_database(out_db)

    try:
        copy_tables_from_splits(conn, split_files)
        table_headers = process_table_metadata(conn, split_files)
        op_map = build_operator_mapping(conn, split_files)
        total_questions = process_questions(conn, split_files, table_headers, op_map)
        create_views(conn)
        validation_errors = validate_queries(conn, table_headers, op_map)

        num_tables = conn.execute("SELECT COUNT(*) FROM wikisql_tables").fetchone()[0]
        sum_rows = conn.execute("SELECT SUM(n_rows) FROM wikisql_tables").fetchone()[0]

        conn.commit()

        if validation_errors > 0:
            raise RuntimeError(f"Validation failed with {validation_errors} errors.")

        return {
            "out_db": str(out_db),
            "total_questions": int(total_questions),
            "total_tables": int(num_tables),
            "total_rows_across_tables": int(sum_rows) if sum_rows is not None else 0,
            "validation_errors": int(validation_errors),
        }
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Build unified WikiSQL SQLite DB from compressed source.")
    parser.add_argument("--src", default=DEFAULT_URL,
                        help=f"URL or local path to the WikiSQL data archive (data.tar.bz2). Default: {DEFAULT_URL}")
    args = parser.parse_args()

    out_db = Path("data/processed/wikisql/wikisql-v1.sqlite").resolve()
    workdir = Path("data/raw/wikisql").resolve()

    if is_url(args.src):
        archive_path = workdir / "data.tar.bz2"
        # Check if archive already exists before downloading
        if archive_path.exists():
            eprint(f"Using existing archive: {archive_path}")
        else:
            workdir.mkdir(parents=True, exist_ok=True)
            archive_bytes = download_to_bytes(args.src)
            archive_path.write_bytes(archive_bytes)
            eprint(f"Downloaded archive to: {archive_path}")
    else:
        archive_path = Path(args.src).expanduser().resolve()
        if not archive_path.exists():
            raise FileNotFoundError(f"--src path not found: {archive_path}")

    eprint(f"Extracting archive to: {workdir}")
    extract_tar_bz2(archive_path, workdir)

    summary = build_unified_db(extracted_root=workdir, out_db=out_db)

    meta_path = Path(str(out_db) + ".meta.json")
    meta = {
        "dataset": "wikisql",
        "version": "1.0.0",
        "source_url": DEFAULT_URL if is_url(args.src) else str(args.src),
        "counts": {
            "questions": summary["total_questions"],
            "tables": summary["total_tables"],
            "rows_total": summary["total_rows_across_tables"],
        }
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
