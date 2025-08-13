#!/usr/bin/env python3
"""
Build a slim, deterministic WikiSQL SQLite DB containing the 500 most difficult NL->SQL pairs.

CLI:
  python build_wikisql_top500.py [--src <URL-or-path>] [--out <final_db_path>]

Defaults:
  --src defaults to the canonical GitHub raw: https://raw.githubusercontent.com/salesforce/WikiSQL/master/data.tar.bz2
  --out defaults to: data/processed/wikisql/wikisql-top500.sqlite
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import tarfile
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_URL = "https://raw.githubusercontent.com/salesforce/WikiSQL/master/data.tar.bz2"
DEFAULT_OUT = "data/processed/wikisql/wikisql-top500.sqlite"

os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

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


def extract_tar_bz2(archive: Path, dest_dir: Path, delete_archive: bool = True) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Use tarfile's member filtering to avoid path traversal; extract deterministically
    with tarfile.open(archive, mode="r:bz2") as tar:
        # Sort members by name for deterministic extraction order
        members = sorted(tar.getmembers(), key=lambda m: m.name)
        def _safe(member: tarfile.TarInfo):
            # Disallow absolute paths and parent directory traversal
            if member.islnk() or member.issym():
                return None
            if not member.name or member.name.startswith("/") or ".." in Path(member.name).parts:
                return None
            return member
        safe_members = [m for m in members if _safe(m) is not None]
        tar.extractall(path=dest_dir, members=safe_members, filter='data')

    # Delete the archive file after successful extraction
    if delete_archive and archive.exists():
        archive.unlink()
        eprint(f"Deleted archive file: {archive}")

    return dest_dir


def quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def quote_literal(val: str) -> str:
    return "'" + str(val).replace("'", "''") + "'"


AGG_MAP = {0: None, 1: "MAX", 2: "MIN", 3: "COUNT", 4: "SUM", 5: "AVG"}


def sanitize_column_name(name: str) -> str:
    """Convert a human-readable column name to a valid SQL identifier with consistent snake_case."""
    import re

    if not name:
        return 'unnamed_col'

    name = str(name).strip()
    if not name:
        return 'unnamed_col'

    exponent_replacements = {
        '¹': '_1',
        '²': '_squared',
        '³': '_cubed',
        '⁴': '_4',
        '⁵': '_5',
        '⁶': '_6',
        '⁷': '_7',
        '⁸': '_8',
        '⁹': '_9',
        '⁰': '_0',
    }
    for exponent, replacement in exponent_replacements.items():
        name = name.replace(exponent, replacement)

    if re.match(r'^\d{4}$', name):
        return 'yr_' + name

    name = re.sub(r'\b(\d{4})[\-/](\d{2})\b', r'yr_\1_\2', name)
    name = re.sub(r'\b(\d{4})\b', r'yr_\1', name)

    name = re.sub(r'\b(\w+)\s*#(\d+)', r'\1_number_\2', name, flags=re.IGNORECASE)
    name = re.sub(r'\b(\w+)\s*#\s*$', r'\1_number', name, flags=re.IGNORECASE)

    name = re.sub(r'%\s+', 'percent_', name, flags=re.IGNORECASE)
    name = re.sub(r'^%\s*', 'percent_', name, flags=re.IGNORECASE)

    name = re.sub(r'#\s*of\s+', 'num_of_', name, flags=re.IGNORECASE)

    name = re.sub(r'\bno\.\s*', 'number_', name, flags=re.IGNORECASE)
    name = re.sub(r'\bno\s+of\s+', 'number_of_', name, flags=re.IGNORECASE)

    replacements = {
        r'\btotal\s+w[–\-]l\b': 'total_wins_losses',
        r'\bsingles\s+w[–\-]l\b': 'singles_wins_losses',
        r'\bdoubles\s+w[–\-]l\b': 'doubles_wins_losses',
        r'\bw[–\-]l\b': 'wins_losses',
        r'\bnumber\s+of\s+': 'number_of_',
        r'\bamount\s+of\s+': 'amount_of_',
        r'\btotal\s+': 'total_',
        r'\bhighest\s+': 'highest_',
        r'\blowest\s+': 'lowest_',
        r'\bfirst\s+': 'first_',
        r'\blast\s+': 'last_',
        r'\boriginal\s+': 'original_',
        r'\bproduction\s+': 'production_',
        r'\bair\s+date\b': 'air_date',
        r'\byrs\b': 'years',
        r'\bmin\b': 'minimum',
        r'\bmax\b': 'maximum',
        r'\bavg\b': 'average',
        r'\btemp\b': 'temperature',
        r'\bpop\b': 'population',
        r'\bpct\b': 'percent',
        r'\bsemi[_\s\-]finalist\b': 'semi_finalist',
    }
    for pattern, replacement in replacements.items():
        name = re.sub(pattern, replacement, name, flags=re.IGNORECASE)

    name = re.sub(r'\s*\(\s*([^)]+)\s*\)', r'_\1', name)
    name = re.sub(r'([a-z])([A-Z])', r'\1_\2', name)
    name = name.lower()
    name = re.sub(r'[^\w\.\']', '_', name)
    name = re.sub(r'[\.\']', '', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('_')

    if name and name[0].isdigit() and not name.startswith('yr_'):
        name = 'col_' + name

    if not name:
        name = 'unnamed_col'

    return name


def ensure_unique_column_names(headers: list) -> list:
    """Ensure all column names are unique by adding suffixes to duplicates."""
    seen = {}
    result = []
    for header in headers:
        sanitized = sanitize_column_name(str(header))
        if sanitized in seen:
            seen[sanitized] += 1
            unique_name = f"{sanitized}_{seen[sanitized]}"
        else:
            seen[sanitized] = 0
            unique_name = sanitized
        result.append(unique_name)
    return result

OP_MAP_BASE = {0: "=", 1: ">", 2: "<"}
OP_EXTS = {3: ">=", 4: "<=", 5: "!="}

# --- Deterministic scoring weights (stable constants) ---
W_COND_COUNT = 1.5
W_OP_RARITY  = 0.9
W_HAS_AGG    = 0.8
W_AGG_RARITY = 0.7
W_N_ROWS     = 0.001
W_N_COLS     = 0.25
W_Q_WORDS    = 0.05
W_HARD_OPS   = 0.5
W_MATCH_CT   = 0.002
MATCH_CAP    = 1000
NROWS_CAP    = 10000

# --- Regex for SELECT ... FROM prefix (case-insensitive, DOTALL, minimal) ---
SELECT_FROM_RE = re.compile(r'(?is)^select\s+.+?\s+from\s+')


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


def setup_intermediate_db(intermediate_db: Path) -> sqlite3.Connection:
    """
    Create the intermediate database (metadata only; no raw data tables are copied here).
    It holds:
      - wikisql_tables (metadata)
      - questions (with reconstructed sql_text)
      - op_map
      - views for scoring
      - where_matches (ambiguity boost results)
    """
    if intermediate_db.exists():
        intermediate_db.unlink()

    intermediate_db.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(intermediate_db))
    # Deterministic + fast-enough settings (durability is not critical in intermediate DB)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")   # stable journaling
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("PRAGMA cache_size = -200000;")
    conn.execute("PRAGMA case_sensitive_like = OFF;")

    conn.executescript("""
        CREATE TABLE wikisql_tables (
            table_name TEXT PRIMARY KEY,
            split TEXT NOT NULL CHECK (split IN ('train','dev','test')),
            header_json TEXT NOT NULL,
            types_json TEXT NOT NULL,
            n_rows INTEGER NOT NULL,
            page_title TEXT,
            section_title TEXT,
            caption TEXT,
            page_id TEXT
        );

        CREATE TABLE questions (
            id INTEGER PRIMARY KEY,
            split TEXT NOT NULL CHECK (split IN ('train','dev','test')),
            table_name TEXT NOT NULL,
            question TEXT NOT NULL,
            agg INTEGER NOT NULL,
            sel_col_idx INTEGER NOT NULL,
            conds_json TEXT NOT NULL,
            sql_text TEXT NOT NULL
        );

        CREATE INDEX idx_questions_table    ON questions(table_name);
        CREATE INDEX idx_questions_split    ON questions(split);

        CREATE TABLE op_map (op_idx INTEGER PRIMARY KEY, symbol TEXT NOT NULL);

        -- Ambiguity counts (row matches for WHERE)
        CREATE TABLE where_matches (
            id INTEGER PRIMARY KEY,
            where_match_count INTEGER NOT NULL
        );
    """)
    return conn


def attach_split_aliases(conn: sqlite3.Connection, split_files: Dict[str, Dict[str, Path]]) -> Dict[str, str]:
    """Attach each split DB under a deterministic alias."""
    aliases = {}
    for split in sorted(split_files.keys()):
        pass
    for split in ["dev", "test", "train"]:
        files = split_files[split]
        alias = f"{split}_db"
        conn.execute(f"ATTACH DATABASE ? AS {alias}", (str(files["db"]),))
        aliases[split] = alias
    return aliases


def detach_split_aliases(conn: sqlite3.Connection, aliases: Dict[str, str]) -> None:
    for split in ["train", "test", "dev"]:
        alias = aliases.get(split)
        if alias:
            conn.execute(f"DETACH DATABASE {alias}")


def build_operator_mapping(conn: sqlite3.Connection, split_files: Dict[str, Dict[str, Path]]) -> Dict[int, str]:
    """Build and populate the operator mapping table from all splits deterministically."""
    observed_ops = set()
    for split in ["dev", "test", "train"]:
        with split_files[split]["examples"].open("r", encoding="utf-8") as f:
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
    for k in sorted(op_map.keys()):
        conn.execute("INSERT INTO op_map (op_idx, symbol) VALUES (?,?)", (k, op_map[k]))
    return op_map


def build_sql_text(table_name: str, sel_idx: int, agg: int, conds: list,
                   table_headers: Dict[str, List[str]], op_map: Dict[int, str]) -> str:
    """Build SQL text from structured query components (single-table, safe identifiers)."""
    header = table_headers.get(table_name)
    if header is None:
        raise RuntimeError(f"No header known for table {table_name}")
    if not (0 <= sel_idx < len(header)):
        raise RuntimeError(f"sel_col_idx {sel_idx} out of bounds for table {table_name}")

    sanitized_headers = ensure_unique_column_names(header)

    sel_col = sanitized_headers[sel_idx]
    agg_name = AGG_MAP.get(agg)
    sel_expr = f"{quote_ident(sel_col)}" if agg_name is None else f"{agg_name}({quote_ident(sel_col)})"
    where = []
    for c in (conds or []):
        if not isinstance(c, list) or len(c) < 3:
            continue
        col_idx, op_idx, value = int(c[0]), int(c[1]), c[2]
        if not (0 <= col_idx < len(sanitized_headers)):
            raise RuntimeError(f"cond col_idx {col_idx} out of bounds for table {table_name}")
        op = op_map.get(op_idx)
        if op is None:
            raise RuntimeError(f"Unknown operator index {op_idx}")
        where.append(f"{quote_ident(sanitized_headers[col_idx])} {op} {quote_literal(str(value))}")
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    return f"SELECT {sel_expr} FROM {quote_ident(table_name)}{where_sql};"


def process_table_metadata(conn: sqlite3.Connection, split_files: Dict[str, Dict[str, Path]]) -> Dict[str, List[str]]:
    """
    Read *.tables.jsonl across splits and populate wikisql_tables.
    Do NOT copy raw data tables here. n_rows is computed by counting in the attached split DBs.
    Returns: table_headers[table_name] = [col1, col2, ...]
    """
    aliases = attach_split_aliases(conn, split_files)
    table_headers: Dict[str, List[str]] = {}
    table_types: Dict[str, List[str]] = {}

    for split in ["dev", "test", "train"]:
        files = split_files[split]
        alias = aliases[split]
        count = 0
        with files["tables"].open("r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                tid = obj["id"]
                tname = derived_table_name(tid)
                header = obj.get("header", [])
                types = obj.get("types", [])
                table_headers[tname] = header
                table_types[tname] = types

                page_title = obj.get("page_title")
                section_title = obj.get("section_title")
                caption = obj.get("caption")
                page_id = obj.get("page_id")
                try:
                    n_rows = conn.execute(f'SELECT COUNT(*) FROM {alias}.{quote_ident(tname)}').fetchone()[0]
                except sqlite3.OperationalError as e:
                    raise RuntimeError(f"Expected table {tname} from split {split} not found in {alias}") from e

                conn.execute(
                    """INSERT INTO wikisql_tables
                       (table_name, split, header_json, types_json, n_rows, page_title, section_title, caption, page_id)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (tname, split,
                     json.dumps(header, ensure_ascii=False),
                     json.dumps(types,  ensure_ascii=False),
                     int(n_rows), page_title, section_title, caption,
                     None if page_id is None else str(page_id))
                )
                count += 1
        eprint(f"[{split}] registered {count} table metadata rows")

    conn.commit()
    detach_split_aliases(conn, aliases)
    return table_headers


def process_questions(conn: sqlite3.Connection, split_files: Dict[str, Dict[str, Path]],
                      table_headers: Dict[str, List[str]], op_map: Dict[int, str]) -> int:
    """Parse *.jsonl examples across splits, reconstruct sql_text, insert into questions deterministically."""
    inserted = 0
    for split in ["dev", "test", "train"]:
        eprint(f"[{split}] ingesting questions…")
        with split_files[split]["examples"].open("r", encoding="utf-8") as f:
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
                    "INSERT INTO questions (split, table_name, question, agg, sel_col_idx, conds_json, sql_text) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (split, tname, question, agg, sel, json.dumps(conds, ensure_ascii=False), sql_text)
                )
                inserted += 1
        eprint(f"[{split}] inserted questions: (cumulative) {inserted}")
    return inserted


def create_scoring_views(conn: sqlite3.Connection) -> None:
    """Create deterministic, pure-SQL feature and scoring views."""
    conn.executescript(f"""
        DROP VIEW IF EXISTS v_questions_with_schema;
        CREATE VIEW v_questions_with_schema AS
        SELECT q.*, wt.header_json, wt.types_json, wt.n_rows
        FROM questions q
        JOIN wikisql_tables wt
          ON wt.table_name = q.table_name
         AND wt.split = q.split;

        DROP TABLE IF EXISTS op_stats;
        CREATE TABLE op_stats AS
        SELECT CAST(json_extract(je.value, '$[1]') AS INT) AS op_idx,
               COUNT(*) AS cnt
        FROM questions q, json_each(q.conds_json) AS je
        GROUP BY op_idx
        ORDER BY op_idx;

        DROP TABLE IF EXISTS agg_stats;
        CREATE TABLE agg_stats AS
        SELECT agg, COUNT(*) AS cnt
        FROM questions
        GROUP BY agg
        ORDER BY agg;

        DROP TABLE IF EXISTS totals;
        CREATE TABLE totals AS
        SELECT
          (SELECT COALESCE(SUM(cnt),0) FROM op_stats)  AS total_op_cnt,
          (SELECT COALESCE(SUM(cnt),0) FROM agg_stats) AS total_agg_cnt;

        DROP VIEW IF EXISTS v_q_features;
        CREATE VIEW v_q_features AS
        SELECT
          q.id,
          q.split,
          q.table_name,
          q.question,
          q.agg,
          json_array_length(q.conds_json) AS cond_count,
          EXISTS (
            SELECT 1
            FROM json_each(q.conds_json) je
            WHERE CAST(json_extract(je.value,'$[1]') AS INT) IN (3,4,5)
          ) AS has_hard_ops,
          COALESCE((
            SELECT SUM( (SELECT total_op_cnt*1.0/cnt FROM op_stats os, totals t
                         WHERE os.op_idx = CAST(json_extract(je.value,'$[1]') AS INT)) )
            FROM json_each(q.conds_json) je
          ), 0.0) AS op_rarity_sum,
          CASE WHEN q.agg = 0 THEN 0.0 ELSE
            (SELECT total_agg_cnt*1.0/cnt FROM agg_stats a, totals t
             WHERE a.agg = q.agg)
          END AS agg_rarity,
          (length(q.question) - length(replace(q.question,' ',''))
             + 1) AS q_words
        FROM questions q;

        DROP VIEW IF EXISTS v_q_with_schema;
        CREATE VIEW v_q_with_schema AS
        SELECT
          f.*,
          vqs.n_rows,
          json_array_length(vqs.header_json) AS n_cols
        FROM v_q_features f
        JOIN v_questions_with_schema vqs ON vqs.id = f.id;

        DROP VIEW IF EXISTS v_q_difficulty;
        CREATE VIEW v_q_difficulty AS
        SELECT
          vws.id, vws.split, vws.table_name, vws.question, vws.agg, q.sel_col_idx, q.conds_json, q.sql_text,
          vws.cond_count, vws.has_hard_ops, vws.op_rarity_sum, vws.agg_rarity, vws.q_words, vws.n_rows, vws.n_cols,
          ({W_COND_COUNT} * vws.cond_count)
          + ({W_OP_RARITY}  * vws.op_rarity_sum)
          + ({W_HAS_AGG}    * (vws.agg != 0))
          + ({W_AGG_RARITY} * vws.agg_rarity)
          + ({W_N_ROWS}     * MIN(vws.n_rows, {NROWS_CAP}))
          + ({W_N_COLS}     * vws.n_cols)
          + ({W_Q_WORDS}    * vws.q_words)
          + ({W_HARD_OPS}   * vws.has_hard_ops)
          AS difficulty_score
        FROM v_q_with_schema vws
        JOIN questions q ON q.id = vws.id;
    """)


def compute_where_match_counts(conn: sqlite3.Connection, split_files: Dict[str, Dict[str, Path]]) -> int:
    """
    Ambiguity boost: for each question, execute a COUNT(*) version of its sql_text
    against its source split DB. We prefix the table with the correct attached alias
    to avoid copying raw tables into the intermediate DB.
    """
    aliases = attach_split_aliases(conn, split_files)
    cur = conn.execute("SELECT id, split, table_name, sql_text FROM questions ORDER BY id ASC")
    rows = cur.fetchall()
    updated = 0

    for qid, split, table_name, sql_text in rows:
        alias = aliases[split]
        from_pat = re.compile(r'(?is)\bfrom\s+' + re.escape(f'"{table_name}"'))
        qualified_from = f'FROM {alias}.{quote_ident(table_name)}'
        sql_qualified = from_pat.sub(qualified_from, sql_text, count=1)

        i = 0
        in_quotes = False
        quote_char = None

        while i < len(sql_qualified):
            char = sql_qualified[i]
            if not in_quotes and char in ('"', "'"):
                in_quotes = True
                quote_char = char
            elif in_quotes and char == quote_char:
                in_quotes = False
                quote_char = None
            elif not in_quotes and sql_qualified[i:i+4].upper() == 'FROM' and (i == 0 or sql_qualified[i-1].isspace()) and (i+4 >= len(sql_qualified) or sql_qualified[i+4].isspace()):
                count_sql = 'SELECT COUNT(*) ' + sql_qualified[i:]
                break
            i += 1
        else:
            raise RuntimeError(f"Could not identify FROM clause in SQL for id={qid}")

        try:
            cnt = conn.execute(count_sql).fetchone()[0]
        except Exception as e:
            raise RuntimeError(f"Executing COUNT failed for id={qid}, split={split}, table={table_name}") from e
        conn.execute("INSERT INTO where_matches(id, where_match_count) VALUES (?,?)",
                     (int(qid), int(cnt)))
        updated += 1

        if updated % 1000 == 0:
            conn.commit()

    conn.commit()
    detach_split_aliases(conn, aliases)
    return updated


def select_top500(conn: sqlite3.Connection) -> None:
    """Create final difficulty_plus scores, pick deterministic top 500."""
    conn.executescript(f"""
        DROP VIEW IF EXISTS v_q_difficulty_plus;
        CREATE VIEW v_q_difficulty_plus AS
        SELECT d.*,
               COALESCE(w.where_match_count, 0) AS where_match_count,
               d.difficulty_score
                 + ({W_MATCH_CT} * MIN(COALESCE(w.where_match_count, 0), {MATCH_CAP}))
                 AS difficulty_score_plus
        FROM v_q_difficulty d
        LEFT JOIN where_matches w ON w.id = d.id;

        DROP TABLE IF EXISTS top500_questions;
        CREATE TABLE top500_questions AS
        SELECT *
        FROM v_q_difficulty_plus
        ORDER BY difficulty_score_plus DESC, id ASC
        LIMIT 500;

        DROP TABLE IF EXISTS top500_tables;
        CREATE TABLE top500_tables AS
        SELECT DISTINCT wt.*
        FROM top500_questions t
        JOIN wikisql_tables wt ON wt.table_name = t.table_name AND wt.split = t.split;
    """)


def build_final_db(intermediate_conn: sqlite3.Connection,
                   split_files: Dict[str, Dict[str, Path]],
                   out_db: Path) -> Dict[str, int]:
    """
    Create the final slim DB on disk:
      - questions (top 500 with scores)
      - wikisql_tables (only referenced tables)
      - physical source tables copied from split DBs (exact names)
    """
    if out_db.exists():
        out_db.unlink()
    out_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(out_db))
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = FULL;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        conn.execute("PRAGMA cache_size = -200000;")

        conn.executescript("""
            CREATE TABLE questions (
                id INTEGER PRIMARY KEY,
                split TEXT NOT NULL CHECK (split IN ('train','dev','test')),
                table_name TEXT NOT NULL,
                question TEXT NOT NULL,
                agg INTEGER NOT NULL,
                sel_col_idx INTEGER NOT NULL,
                conds_json TEXT NOT NULL,
                sql_text TEXT NOT NULL,
                cond_count INTEGER NOT NULL,
                has_hard_ops INTEGER NOT NULL,
                op_rarity_sum REAL NOT NULL,
                agg_rarity REAL NOT NULL,
                q_words INTEGER NOT NULL,
                n_rows INTEGER NOT NULL,
                n_cols INTEGER NOT NULL,
                difficulty_score REAL NOT NULL,
                where_match_count INTEGER NOT NULL,
                difficulty_score_plus REAL NOT NULL
            );

            CREATE TABLE wikisql_tables (
                table_name TEXT PRIMARY KEY,
                split TEXT NOT NULL CHECK (split IN ('train','dev','test')),
                header_json TEXT NOT NULL,
                types_json TEXT NOT NULL,
                n_rows INTEGER NOT NULL,
                page_title TEXT,
                section_title TEXT,
                caption TEXT,
                page_id TEXT
            );

            CREATE VIEW v_tables_browse AS
            SELECT
              table_name,
              split,
              n_rows,
              page_title,
              section_title,
              caption
            FROM wikisql_tables;

            CREATE VIEW v_top500_questions AS
            SELECT
              table_name,
              question,
              sql_text
            FROM questions
            ORDER BY difficulty_score_plus DESC;
        """)

        cols_q = [c[1] for c in intermediate_conn.execute("PRAGMA table_info(top500_questions)").fetchall()]
        cols_w = [c[1] for c in intermediate_conn.execute("PRAGMA table_info(top500_tables)").fetchall()]

        q_rows = intermediate_conn.execute(f"SELECT {', '.join(map(quote_ident, cols_q))} FROM top500_questions ORDER BY difficulty_score_plus DESC, id ASC").fetchall()
        w_rows = intermediate_conn.execute(f"SELECT {', '.join(map(quote_ident, cols_w))} FROM top500_tables ORDER BY table_name ASC").fetchall()

        q_placeholders = ','.join(['?'] * len(cols_q))
        conn.executemany(f"""
            INSERT INTO questions ({', '.join(map(quote_ident, cols_q))})
            VALUES ({q_placeholders})
        """, q_rows)

        w_placeholders = ','.join(['?'] * len(cols_w))
        conn.executemany(f"""
            INSERT INTO wikisql_tables ({', '.join(map(quote_ident, cols_w))})
            VALUES ({w_placeholders})
        """, w_rows)

        aliases = {}
        for split in ["dev", "test", "train"]:
            alias = f"{split}_db"
            conn.execute(f"ATTACH DATABASE ? AS {alias}", (str(split_files[split]["db"]),))
            aliases[split] = alias

        tables = intermediate_conn.execute("""
            SELECT split, table_name
            FROM top500_tables
            ORDER BY split ASC, table_name ASC
        """).fetchall()

        for split, table_name in tables:
            alias = aliases[split]

            header_json = intermediate_conn.execute(
                "SELECT header_json FROM top500_tables WHERE table_name = ?",
                (table_name,)
            ).fetchone()[0]
            headers = json.loads(header_json)

            source_columns = conn.execute(f"PRAGMA {alias}.table_info({quote_ident(table_name)})").fetchall()
            proper_column_names = ensure_unique_column_names(headers)

            if len(proper_column_names) != len(source_columns):
                eprint(f"Warning: Header count mismatch for {table_name}. Headers: {len(headers)}, Columns: {len(source_columns)}")
                while len(proper_column_names) < len(source_columns):
                    proper_column_names.append(f"col_{len(proper_column_names)}")
                proper_column_names = proper_column_names[:len(source_columns)]

            column_defs = []
            for i, (cid, old_name, type_name, notnull, default, pk) in enumerate(source_columns):
                new_name = quote_ident(proper_column_names[i])
                column_defs.append(f"{new_name} {type_name}")

            create_sql = f"CREATE TABLE {quote_ident(table_name)} ({', '.join(column_defs)})"
            conn.execute(create_sql)

            old_columns = [f"col{i}" for i in range(len(source_columns))]
            conn.execute(f"""
                INSERT INTO {quote_ident(table_name)}
                SELECT {', '.join(old_columns)}
                FROM {alias}.{quote_ident(table_name)}
            """)

        conn.commit()

        for split in ["train", "test", "dev"]:
            conn.execute(f"DETACH DATABASE {aliases[split]}")

        conn.commit()

        stats = {
            "questions": len(q_rows),
            "tables": len(tables),
        }
        return stats
    finally:
        conn.close()


def validate_all_queries(db_path: Path) -> Dict[str, Any]:
    """
    Validate that all 500 SQL queries in the database execute successfully.
    Returns detailed validation statistics and any errors found.
    """
    eprint("[validation] Testing all 500 SQL queries...")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")

    try:
        questions = conn.execute("""
            SELECT id, table_name, sql_text, split
            FROM questions
            ORDER BY id ASC
        """).fetchall()

        validation_results = {
            "total_queries": len(questions),
            "successful_queries": 0,
            "failed_queries": 0,
            "errors": [],
            "query_types": {"SELECT": 0, "SELECT_AGG": 0},
            "splits": {"train": 0, "dev": 0, "test": 0},
            "tables_tested": set()
        }

        for question_id, table_name, sql_text, split in questions:
            validation_results["tables_tested"].add(table_name)
            validation_results["splits"][split] += 1

            if " AVG(" in sql_text or " SUM(" in sql_text or " MIN(" in sql_text or " MAX(" in sql_text or " COUNT(" in sql_text:
                validation_results["query_types"]["SELECT_AGG"] += 1
            else:
                validation_results["query_types"]["SELECT"] += 1

            try:
                result = conn.execute(sql_text).fetchall()
                validation_results["successful_queries"] += 1

                is_agg_query = " AVG(" in sql_text or " SUM(" in sql_text or " MIN(" in sql_text or " MAX(" in sql_text or " COUNT(" in sql_text
                if len(result) > 1 and is_agg_query:
                    eprint(f"Warning: Aggregation query {question_id} returned multiple rows ({len(result)}), expected single value")

            except Exception as e:
                validation_results["failed_queries"] += 1
                error_info = {
                    "question_id": question_id,
                    "table_name": table_name,
                    "sql_text": sql_text,
                    "error": str(e),
                    "split": split
                }
                validation_results["errors"].append(error_info)
                eprint(f"ERROR: Query {question_id} failed: {e}")
                eprint(f"  SQL: {sql_text}")

        validation_results["unique_tables_tested"] = len(validation_results["tables_tested"])
        del validation_results["tables_tested"]

        success_rate = (validation_results["successful_queries"] / max(validation_results["total_queries"], 1)) * 100
        eprint(f"[validation] Results: {validation_results['successful_queries']}/{validation_results['total_queries']} queries successful ({success_rate:.1f}%)")

        if validation_results["failed_queries"] > 0:
            eprint(f"[validation] WARNING: {validation_results['failed_queries']} queries failed!")
            for error in validation_results["errors"][:5]:
                eprint(f"  - Query {error['question_id']}: {error['error']}")
            if len(validation_results["errors"]) > 5:
                eprint(f"  - ... and {len(validation_results['errors']) - 5} more errors")

        return validation_results

    finally:
        conn.close()


def compute_top500_distribution(db_path: Path) -> Dict[str, Any]:
    """
    Compute concise distribution stats over the top-500 questions in the final DB.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("""
            SELECT split, agg, cond_count, has_hard_ops, q_words, n_rows, n_cols, where_match_count, conds_json
            FROM questions
        """).fetchall()

        totals = len(rows)
        splits = {"train": 0, "dev": 0, "test": 0}
        aggs = {"NONE": 0, "MAX": 0, "MIN": 0, "COUNT": 0, "SUM": 0, "AVG": 0}
        op_counts = {"=": 0, ">": 0, "<": 0, ">=": 0, "<=": 0, "!=": 0}

        for split, agg_idx, cond_count, has_hard, q_words, n_rows, n_cols, where_ct, conds_json in rows:
            if split in splits:
                splits[split] += 1
            agg_name = AGG_MAP.get(int(agg_idx))
            aggs["NONE" if agg_name is None else agg_name] += 1

            try:
                conds = json.loads(conds_json) if conds_json else []
            except Exception:
                conds = []
            for c in conds:
                if isinstance(c, list) and len(c) >= 2:
                    op_idx = int(c[1])
                    sym = OP_MAP_BASE.get(op_idx, OP_EXTS.get(op_idx, "="))
                    if sym in op_counts:
                        op_counts[sym] += 1
                    else:
                        op_counts[sym] = 1

        # Only include operators actually present to keep it tidy
        op_counts = {k: v for k, v in op_counts.items() if v > 0}

        return {
            "total": totals,
            "splits": splits,
            "aggregations": aggs,
            "operators": op_counts,
        }

    finally:
        conn.close()


def build_top500(extracted_root: Path, out_db: Path, keep_intermediate_db: bool = False) -> Dict[str, Any]:
    """
    End-to-end pipeline:
      1) Create intermediate DB (metadata only).
      2) Populate metadata (tables, questions, op_map).
      3) Create scoring views (pure-SQL features).
      4) Compute ambiguity counts (where_match_count) by executing COUNT(*) against source DBs.
      5) Rank deterministically and pick top 500.
      6) Build final DB with top-500 + referenced tables.
    """
    split_files = validate_split_files(extracted_root)

    # e.g., wikisql-top500.sqlite -> wikisql-intermediate.sqlite
    intermediate_db = out_db.with_name("wikisql-intermediate.sqlite")
    if intermediate_db.exists():
        intermediate_db.unlink()
    conn = setup_intermediate_db(intermediate_db)

    try:
        op_map = build_operator_mapping(conn, split_files)
        table_headers = process_table_metadata(conn, split_files)
        total_questions = process_questions(conn, split_files, table_headers, op_map)
        create_scoring_views(conn)
        n_amb = compute_where_match_counts(conn, split_files)
        select_top500(conn)

        sum_rows = conn.execute("SELECT SUM(n_rows) FROM top500_tables").fetchone()[0]

        stats = build_final_db(conn, split_files, out_db)

        conn.commit()

        validation_results = validate_all_queries(out_db)
        distribution = compute_top500_distribution(out_db)

        return {
            "total_questions_all_splits": total_questions,
            "top500_questions": stats["questions"],
            "top500_tables": stats["tables"],
            "top500_rows_across_tables": sum_rows,
            "where_match_counts_computed": n_amb,
            "validation": validation_results,
            "top500_distribution": distribution,
            "intermediate_db": str(intermediate_db),
            "final_db": str(out_db),
        }
    finally:
        conn.close()
        # Delete the intermediate database unless explicitly requested to keep it
        if not keep_intermediate_db and intermediate_db.exists():
            intermediate_db.unlink()
            eprint(f"Deleted intermediate database: {intermediate_db}")


def main():
    parser = argparse.ArgumentParser(description="Build a slim, deterministic WikiSQL top-500 difficulty DB.")
    parser.add_argument("--src", default=DEFAULT_URL,
                        help=f"URL or local path to the WikiSQL data archive (data.tar.bz2). Default: {DEFAULT_URL}")
    parser.add_argument("--out", default=DEFAULT_OUT,
                        help=f"Output SQLite DB path. Default: {DEFAULT_OUT}")
    parser.add_argument("--validate-only", action="store_true",
                        help="Only run validation on existing database (skip build process)")
    parser.add_argument("--keep-intermediate", action="store_true",
                        help="Keep the intermediate database file after completion")
    args = parser.parse_args()

    out_db = Path(args.out).resolve()

    if args.validate_only:
        if not out_db.exists():
            raise FileNotFoundError(f"Database not found for validation: {out_db}")

        eprint(f"Running validation on existing database: {out_db}")
        validation_results = validate_all_queries(out_db)
        distribution = compute_top500_distribution(out_db)

        summary = {
            "validation_only": True,
            "database_path": str(out_db),
            "validation": validation_results,
            "top500_distribution": distribution,
        }
    else:
        workdir = Path("data/raw/wikisql").resolve()

        # Obtain archive
        if is_url(args.src):
            archive_path = workdir / "data.tar.bz2"
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

        summary = build_top500(extracted_root=workdir, out_db=out_db, keep_intermediate_db=args.keep_intermediate)

    if "validation_only" in summary and summary["validation_only"]:
        eprint(f"[summary] Database: {summary['database_path']}")
        validation = summary["validation"]
        eprint(f"[summary] Validation: {validation['successful_queries']}/{validation['total_queries']} queries successful ({(validation['successful_queries']/max(validation['total_queries'],1)*100):.1f}%)")
        if validation['failed_queries'] > 0:
            eprint(f"[summary] Failed queries: {validation['failed_queries']}")
    else:
        eprint(f"[summary] Total questions processed: {summary['total_questions_all_splits']}")
        eprint(f"[summary] Top 500 questions selected: {summary['top500_questions']}")
        eprint(f"[summary] Top 500 tables: {summary['top500_tables']}")
        eprint(f"[summary] Total rows across tables: {summary['top500_rows_across_tables']}")
        eprint(f"[summary] Where match counts computed: {summary['where_match_counts_computed']}")
        validation = summary["validation"]
        eprint(f"[summary] Validation: {validation['successful_queries']}/{validation['total_queries']} queries successful ({(validation['successful_queries']/max(validation['total_queries'],1)*100):.1f}%)")
        eprint(f"[summary] Final database: {summary['final_db']}")

    # Distribution stats
    dist = summary["top500_distribution"]
    eprint(f"[distribution] Total: {dist['total']}")
    splits_str = ", ".join([f"{k}:{v}" for k, v in dist['splits'].items()])
    eprint(f"[distribution] Splits: {splits_str}")
    aggs_str = ", ".join([f"{k}:{v}" for k, v in dist['aggregations'].items() if v > 0])
    eprint(f"[distribution] Aggregations: {aggs_str}")
    ops_str = ", ".join([f"{k}:{v}" for k, v in dist['operators'].items() if v > 0])
    eprint(f"[distribution] Operators: {ops_str}")


if __name__ == "__main__":
    main()
