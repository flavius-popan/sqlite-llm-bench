#!/usr/bin/env python3
"""
sqlite-llm-bench: WikiSQL eval (LM Studio via LiteLLM)

- Fixes:
  * Robust extraction from LM Studio where text appears in non-standard `message.reasoning`.
  * Tolerant SQL extraction (no semicolon required; strips code fences).
  * Assistant prefill + stop sequences + temperature=0.0 to suppress long "reasoning" and force SQL early.
  * Optional tool-calling with `execute_sql`; supports "auto"/"required"/"none".
  * Value-hints for comma-formatted TEXT columns to align with WikiSQL labels.
  * Forces LiteLLM to treat LM Studio as OpenAI-compatible even for model ids like "qwen/qwen3-30b-a3b-2507".

Default dataset path (project-relative):
  data/processed/wikisql/wikisql-top500-v1.db

USAGE EXAMPLES
  # Basic run (no tools), 10 samples:
  python datasets/wikisql/scripts/eval_wikisql.py --model "gpt-oss-20b" --limit 10 --tool-choice none

  # With tools (required), Qwen model id containing '/':
  python datasets/wikisql/scripts/eval_wikisql.py --model "qwen/qwen3-30b-a3b-2507" --limit 10 --tool-choice required

  # If LM Studio is on a non-default port:
  python datasets/wikisql/scripts/eval_wikisql.py --model "llama-3.1:8b-instruct" --base-url http://localhost:1234/v1
"""

import argparse
import json
import os
import random
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from litellm import completion  # pip install 'litellm>=1.40.7'
except Exception:
    print("ERROR: LiteLLM is required. Install with: pip install 'litellm>=1.40.7'", file=sys.stderr)
    raise

# ---------- DB & dataset ----------

@dataclass
class Sample:
    idx: int
    question: str
    gold_sql: str
    table_name: str
    columns: List[str]
    comma_text_cols: List[str]


def connect_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA case_sensitive_like=ON;")
    return conn


def detect_comma_text_cols(conn: sqlite3.Connection, table: str, cols: Sequence[str]) -> List[str]:
    """Heuristic: flag columns whose sample values look like '6,950' so the prompt can quote them as TEXT."""
    comma_cols: List[str] = []
    for c in cols:
        try:
            rows = conn.execute(f"SELECT {c} FROM '{table}' WHERE {c} IS NOT NULL LIMIT 20;").fetchall()
        except Exception:
            continue
        for (v,) in rows:
            if isinstance(v, str) and re.fullmatch(r"\d{1,3}(?:,\d{3})+", v):
                comma_cols.append(c)
                break
    return comma_cols


def load_wikisql_samples(conn: sqlite3.Connection, limit: Optional[int], shuffle: bool) -> List[Sample]:
    rows = list(conn.execute("SELECT question, gold_sql, table_name FROM v_top500_questions;").fetchall())
    if shuffle:
        random.shuffle(rows)
    if limit is not None:
        rows = rows[:limit]

    table_cols: Dict[str, List[str]] = {}
    samples: List[Sample] = []
    for i, (q, gold, tname) in enumerate(rows):
        if tname not in table_cols:
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info('{tname}')").fetchall()]
            table_cols[tname] = cols
        comma_cols = detect_comma_text_cols(conn, tname, table_cols[tname])
        samples.append(Sample(idx=i, question=q, gold_sql=gold, table_name=tname,
                              columns=table_cols[tname], comma_text_cols=comma_cols))
    return samples


# ---------- Prompting ----------

def build_system_prompt() -> str:
    return (
        "You are a SQLite query generator. Your job is to output ONLY a complete SQL statement.\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "- Output ONLY the SQL query itself\n"
        "- Do NOT explain what you're doing\n"
        "- Do NOT say 'We need to...' or 'The query should...'\n"
        "- Do NOT include reasoning or thoughts\n"
        "- Start immediately with 'SELECT' and end with semicolon\n"
        "- Example good response: SELECT AVG(column) FROM table WHERE condition;\n"
        "- Example bad response: We need to write a SELECT query that...\n\n"
        "Remember: Output ONLY the SQL statement, nothing else."
    )


def build_user_prompt(table_name: str, columns: Sequence[str], question: str, comma_cols: Sequence[str]) -> str:
    col_list = ", ".join(columns)
    hints = ""
    if comma_cols:
        hints = f"\n- Columns with comma-formatted numbers are TEXT and must be compared as quoted strings: {', '.join(comma_cols)}."
    return (
        f"Table: {table_name}\n"
        f"Columns: {col_list}\n"
        f"Question: {question}\n\n"
        f"RULES:\n"
        f"- Use ONLY the table and columns listed above\n"
        f"- Use aggregates (COUNT, SUM, AVG, MIN, MAX) if the question asks for counts, totals, averages, etc.\n"
        f"- Quote string literals with commas as TEXT (e.g., '6,950'){hints}\n"
        f"- NO JOIN, ORDER BY, LIMIT, subqueries, or unlisted columns\n\n"
        f"OUTPUT FORMAT: Start your response immediately with SELECT and end with semicolon. Nothing else.\n\n"
        f"SQL:"
    ).strip()


# ---------- Extraction & execution ----------

def get_assistant_text(msg: dict) -> str:
    """LM Studio sometimes places text in a non-standard 'reasoning' field; prefer content, fallback to reasoning."""
    c = (msg or {}).get("content")
    if isinstance(c, str) and c.strip():
        return c
    r = (msg or {}).get("reasoning")
    if isinstance(r, str) and r.strip():
        return r
    # Check provider_specific_fields for reasoning_content
    provider_fields = (msg or {}).get("provider_specific_fields", {})
    rc = provider_fields.get("reasoning_content")
    if isinstance(rc, str) and rc.strip():
        return rc
    return ""


def extract_sql(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:sql)?\s*|\s*```$", "", t, flags=re.I | re.S).strip()

    # Look for SQL patterns with actual SQL keywords after SELECT
    # Match SELECT followed by aggregate functions, column names, or *
    sql_patterns = [
        r"(SELECT\s+(?:AVG|SUM|COUNT|MIN|MAX|DISTINCT)\s*\([^)]+\).*?;)",
        r"(SELECT\s+\*\s+FROM\s+\w+.*?;)",
        r"(SELECT\s+[\"']?\w+[\"']?\s+FROM\s+\w+.*?;)",
        r"(SELECT\s+[\"']?\w+[\"']?(?:\s*,\s*[\"']?\w+[\"']?)*\s+FROM\s+\w+.*?;)"
    ]

    for pattern in sql_patterns:
        m = re.search(pattern, t, flags=re.I | re.S)
        if m:
            return m.group(1).strip()

    # Fallback: look for patterns without semicolon and add one
    for pattern in sql_patterns:
        pattern_no_semi = pattern.replace(".*?;)", ".*)")
        m = re.search(pattern_no_semi, t, flags=re.I | re.S)
        if m:
            return m.group(1).strip() + ";"

    return None


def normalize_sql(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = s.strip().rstrip(";")
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def exec_sql(conn: sqlite3.Connection, query: str) -> Tuple[List[str], List[Tuple[Any, ...]]]:
    q = query.strip()
    if not q.lower().startswith("select"):
        raise ValueError("Only SELECT queries are allowed")
    if not q.endswith(";"):
        q += ";"
    cur = conn.execute(q)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    return cols, rows


def canon_cell(x: Any) -> str:
    if isinstance(x, float):
        return f"{x:.6f}"
    if isinstance(x, bytes):
        return x.decode("utf-8", "ignore")
    if x is None:
        return ""
    return str(x)


def canon_rows(rows: List[Tuple[Any, ...]]) -> List[Tuple[str, ...]]:
    return sorted([tuple(canon_cell(c) for c in row) for row in rows])


def execution_equal(rows_a: List[Tuple[Any, ...]], rows_b: List[Tuple[Any, ...]]) -> bool:
    return canon_rows(rows_a) == canon_rows(rows_b)


# ---------- LiteLLM (LM Studio OpenAI-compatible) ----------

def call_model_litellm(
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[str] = None,  # "auto" | "required" | None
    temperature: float = 0.0,
    max_tokens: int = 160,
    stop: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Force LiteLLM to treat LM Studio as an OpenAI-compatible provider,
    so model ids like 'qwen/qwen3-30b-a3b-2507' don't trigger provider autodetect.
    """
    resp = completion(
        model=model,
        messages=messages,
        api_base=base_url,
        api_key=api_key or "lm-studio",
        custom_llm_provider="openai",
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
        tool_choice=tool_choice if tools else None,
        stop=stop,
    )
    return resp  # type: ignore


# ---------- Tool schema & handler ----------

def tool_schema_execute_sql() -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "Execute a read-only SQLite SELECT on the given table and return rows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "A single valid SQLite SELECT statement."},
                    "table_name": {"type": "string", "description": "The table that the query reads from."},
                    "limit": {"type": "integer", "description": "Optional row cap for preview.", "minimum": 1},
                },
                "required": ["query", "table_name"],
            },
        },
    }


def handle_tool_calls(conn: sqlite3.Connection, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out_messages = []
    for tc in tool_calls:
        fn = tc.get("function", {})
        name = fn.get("name")
        call_id = tc.get("id")
        if name != "execute_sql":
            continue
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except Exception:
            args = {}
        query = (args.get("query") or "").strip()

        limit = int(args.get("limit") or 200)
        if not query.lower().startswith("select"):
            result = {"error": "Only SELECT is allowed"}
        else:
            q_preview = query.rstrip().rstrip(";")
            if " limit " not in q_preview.lower():
                q_preview = f"{q_preview} LIMIT {limit};"
            try:
                cols, rows = exec_sql(conn, q_preview)
                result = {"columns": cols, "rows": rows}
            except Exception as e:
                result = {"error": str(e)}
        out_messages.append({
            "role": "tool",
            "tool_call_id": call_id,
            "name": name,
            "content": json.dumps(result, ensure_ascii=False),
        })
    return out_messages


# ---------- Eval loop ----------

def evaluate(
    db_path: Path,
    base_url: str,
    api_key: str,
    model: str,
    limit: Optional[int],
    shuffle: bool,
    tool_choice: str,  # "auto" | "required" | "none"
    temperature: float,
    max_tokens: int,
    logfile: Optional[Path],
) -> None:
    conn = connect_db(db_path)
    samples = load_wikisql_samples(conn, limit=limit, shuffle=shuffle)

    runs_dir = Path("./runs")
    model_safe_name = model.replace('/', '_').replace(':', '_')
    model_runs_dir = runs_dir / model_safe_name
    model_runs_dir.mkdir(parents=True, exist_ok=True)
    if logfile is None:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        logfile = model_runs_dir / f"wikisql_{timestamp}.jsonl"

    em_correct = 0
    ex_correct = 0
    total = 0

    use_tools = tool_choice in ("auto", "required")
    tools = [tool_schema_execute_sql()] if use_tools else None
    stop_seq = ["```", "\n\nSQL:", "\n\n"]

    with logfile.open("w", encoding="utf-8") as logf:
        for s in samples:
            total += 1
            system = {"role": "system", "content": build_system_prompt()}
            user = {"role": "user", "content": build_user_prompt(s.table_name, s.columns, s.question, s.comma_text_cols)}

            messages = [system, user]

            resp = call_model_litellm(
                base_url=base_url,
                api_key=api_key,
                model=model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice if use_tools else None,
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop_seq,
            )
            choice = (resp.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            content = get_assistant_text(msg)
            tool_calls = msg.get("tool_calls") or []

            tool_messages = []
            tool_query_sql: Optional[str] = None
            if use_tools and tool_calls:
                tool_messages = handle_tool_calls(conn, tool_calls)
                for tc in tool_calls:
                    if tc.get("function", {}).get("name") == "execute_sql":
                        try:
                            tool_args = json.loads(tc["function"].get("arguments") or "{}")
                            if isinstance(tool_args.get("query"), str):
                                tool_query_sql = tool_args["query"].strip()
                                break
                        except Exception:
                            pass
                messages = messages + [msg] + tool_messages
                resp2 = call_model_litellm(
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    messages=messages,
                    tools=None,
                    tool_choice=None,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stop=stop_seq,
                )
                choice2 = (resp2.get("choices") or [{}])[0]
                content = get_assistant_text(choice2.get("message") or {}) or content

            pred_sql = tool_query_sql or extract_sql(content)
            gold_sql = s.gold_sql

            em = int(normalize_sql(pred_sql) == normalize_sql(gold_sql))

            ex = 0
            pred_error = None
            try:
                if pred_sql:
                    _, pred_rows = exec_sql(conn, pred_sql)
                    _, gold_rows = exec_sql(conn, gold_sql)
                    ex = int(execution_equal(pred_rows, gold_rows))
                else:
                    pred_error = "no_sql_extracted"
            except Exception as e:
                pred_error = str(e)

            em_correct += em
            ex_correct += ex

            record = {
                "idx": s.idx,
                "table_name": s.table_name,
                "columns": s.columns,
                "comma_text_cols": s.comma_text_cols,
                "question": s.question,
                "gold_sql": s.gold_sql,
                "pred_sql": pred_sql,
                "em": em,
                "ex": ex,
                "pred_err": pred_error,
                "used_tools": bool(use_tools and tool_calls),
                "raw_assistant": content,
                "finish_reason": (choice.get("finish_reason") if choice else None),
            }
            logf.write(json.dumps(record, ensure_ascii=False) + "\n")

            if total % 25 == 0 or total == len(samples):
                print(f"[{total}/{len(samples)}] EM={em_correct/total:.3f} EX={ex_correct/total:.3f}", flush=True)

    print("\n=== FINAL ===")
    print(f"Total: {total}")
    print(f"EM: {em_correct}/{total} = {em_correct/total if total else 0:.3f}")
    print(f"EX: {ex_correct}/{total} = {ex_correct/total if total else 0:.3f}")
    print(f"Log: {logfile}")


# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser(description="Evaluate LM Studio models on WikiSQL (top-500) via LiteLLM.")
    parser.add_argument("--model", required=True, help="Model name as loaded in LM Studio (e.g., 'gpt-oss-20b' or 'qwen/qwen3-30b-a3b-2507').")
    parser.add_argument("--base-url", default=os.environ.get("LMSTUDIO_BASE_URL", "http://localhost:1234/v1"),
                        help="LM Studio OpenAI-compatible base URL.")
    parser.add_argument("--api-key", default=os.environ.get("LMSTUDIO_API_KEY", "lm-studio"),
                        help="API key (LM Studio accepts any non-empty string).")
    parser.add_argument("--db-path", default=str(Path("data/processed/wikisql/wikisql-top500-v1.db")),
                        help="Path to the WikiSQL SQLite database.")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument("--tool-choice", choices=["auto", "required", "none"], default="required",
                        help="Force tool usage ('required'), allow ('auto'), or disable ('none').")
    parser.add_argument("--logfile", default=None, help="Path to JSONL log file.")
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"ERROR: DB not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    logfile = Path(args.logfile) if args.logfile else None

    evaluate(
        db_path=db_path,
        base_url=args.base_url,
        api_key=args.api_key,
        model=args.model,
        limit=args.limit,
        shuffle=bool(args.shuffle),
        tool_choice=args.tool_choice,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        logfile=logfile,
    )


if __name__ == "__main__":
    main()
