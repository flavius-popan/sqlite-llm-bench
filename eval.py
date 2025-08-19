#!/usr/bin/env python3
"""
Basic CLI setup for evaluating language models on SQL generation tasks.
"""

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Optional


def describe_database(db_path: str, table_name: Optional[str] = None) -> str:
    """Get database schema information in SQLite CLI format.

    Args:
        db_path: Path to SQLite database file
        table_name: Optional table name to describe, or None for all tables

    Returns:
        Schema information as pipe-separated text
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = 1")  # Extra safety
    cursor = conn.cursor()

    try:
        if table_name:
            cursor.execute(f"PRAGMA table_info({table_name})")
            return "\n".join("|".join(str(col) for col in row) for row in cursor.fetchall())
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            result = []
            for table in tables:
                result.append(f"Table: {table}")
                cursor.execute(f"PRAGMA table_info({table})")
                result.extend("|".join(str(col) for col in row) for row in cursor.fetchall())
                result.append("")
            return "\n".join(result)
    finally:
        conn.close()


def execute_sql(db_path: str, query: str) -> str:
    """Execute SELECT query and return results in SQLite CLI format.

    Args:
        db_path: Path to SQLite database file
        query: SQL query to execute

    Returns:
        Query results as pipe-separated text with headers
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = 1")  # Extra safety
    cursor = conn.cursor()

    try:
        # Simple timeout protection
        def timeout_handler():
            raise sqlite3.OperationalError("Query timeout")

        import signal
        signal.signal(signal.SIGALRM, lambda s, f: timeout_handler())
        signal.alarm(3)  # 3s timeout

        cursor.execute(query)
        rows = cursor.fetchall()

        signal.alarm(0)  # Cancel timeout

        # Get column names (available even for empty results)
        headers = [desc[0] for desc in cursor.description]

        # Format as pipe-separated with headers
        result = ["|".join(headers)]

        if rows:
            result.extend("|".join(str(col) if col is not None else "" for col in row) for row in rows)

        return "\n".join(result)
    finally:
        conn.close()


def main():
    """Main entry point for the evaluation script."""
    parser = argparse.ArgumentParser(
        description="Evaluate language models on SQL generation tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Direct file mode
  python eval.py --questions questions.jsonl --db mydata.db --model llama3:8b
  python eval.py --questions questions.jsonl --db databases/ --model gpt-4

  # Dataset mode
  python eval.py hello_world --model qwen/qwen3-30b-a3b-2507
  python eval.py hello_world --model openai/gpt-oss-20b
        """
    )

    parser.add_argument(
        '--questions',
        help='Path to questions.jsonl file'
    )

    parser.add_argument(
        '--db',
        help='Path to database file or directory'
    )

    parser.add_argument(
        'dataset',
        nargs='?',
        help='Dataset name (e.g., hello_world)'
    )

    parser.add_argument(
        '--model', '-m',
        required=True,
        help='Model name (e.g., qwen/qwen3-30b-a3b-2507)'
    )

    args = parser.parse_args()
    if args.questions and args.db:
        questions_file = Path(args.questions)
        if not questions_file.exists():
            print(f"Error: Questions file not found at {questions_file}")
            sys.exit(1)

        db_path = Path(args.db)
        if not db_path.exists():
            print(f"Error: Database path not found at {db_path}")
            sys.exit(1)

        print(f"Questions: {questions_file}")
        print(f"Database: {db_path}")
        print(f"Model: {args.model}")

    elif args.dataset:
        dataset_path = Path(f'datasets/{args.dataset}')
        if not dataset_path.exists():
            print(f"Error: Dataset '{args.dataset}' not found at {dataset_path}")
            sys.exit(1)

        questions_file = dataset_path / 'questions.jsonl'
        if not questions_file.exists():
            print(f"Error: Questions file not found at {questions_file}")
            sys.exit(1)

        database_file = dataset_path / 'database.db'
        if not database_file.exists():
            print(f"Error: Database file not found at {database_file}")
            sys.exit(1)

        print(f"Dataset: {args.dataset}")
        print(f"Questions: {questions_file}")
        print(f"Database: {database_file}")
        print(f"Model: {args.model}")

    else:
        print("Error: Must specify either:")
        print("  --questions <file> --db <path> --model <model>")
        print("  <dataset> --model <model>")
        sys.exit(1)

    print("\nEvaluation pipeline not yet implemented")


if __name__ == '__main__':
    main()
