#!/usr/bin/env python3
"""
Base evaluation script for SQL generation tasks with shared foundation.
Supports simple mode (schema in prompt) with extensibility for tool calling.
"""

import argparse
import json
import sqlite3
import sys
import signal
from pathlib import Path
from typing import Optional, Dict, Any
import litellm


def describe_database(db_path: str, table_name: Optional[str] = None) -> str:
    """Get database schema information in SQLite CLI format.

    Args:
        db_path: Path to SQLite database file
        table_name: Optional table name to describe, or None for all tables

    Returns:
        Schema information as pipe-separated text
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = 1")
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
        Query results as pipe-separated text
    """
    def timeout_handler(signum, frame):
        raise TimeoutError("Query execution timed out")

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = 1")
    cursor = conn.cursor()

    try:
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(3)

        cursor.execute(query)
        rows = cursor.fetchall()

        signal.alarm(0)

        if not rows:
            return ""

        return "\n".join("|".join(str(col) if col is not None else "" for col in row) for row in rows)

    except Exception as e:
        signal.alarm(0)
        return f"Error: {str(e)}"
    finally:
        conn.close()


def create_prompt(question: str, db_path: str, use_tools: bool = False) -> str:
    """Create prompt for SQL generation.

    Args:
        question: Natural language question
        db_path: Path to database
        use_tools: Whether to use tool calling (future extension)

    Returns:
        Formatted prompt string
    """
    if use_tools:
        # Future extension point for tool calling
        raise NotImplementedError("Tool calling mode not yet implemented")

    # Simple mode: embed schema directly in prompt
    schema = describe_database(db_path)

    prompt = f"""Given the following database schema, generate a SQL query to answer the question.

Database Schema:
{schema}

Question: {question}

Please provide only the SQL query wrapped in ```sql blocks."""

    return prompt


def extract_sql(response: str) -> Optional[str]:
    """Extract SQL query from model response.

    Args:
        response: Raw model response

    Returns:
        Extracted SQL query or None if not found
    """
    # Look for SQL in code blocks
    import re

    # Try ```sql blocks first
    sql_pattern = r'```sql\s*(.*?)\s*```'
    match = re.search(sql_pattern, response, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Try generic ``` blocks
    code_pattern = r'```\s*(.*?)\s*```'
    match = re.search(code_pattern, response, re.DOTALL)
    if match:
        content = match.group(1).strip()
        # Basic heuristic: if it contains SQL keywords, likely SQL
        if any(keyword in content.upper() for keyword in ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE']):
            return content

    # Fallback: look for SELECT statements without code blocks
    select_pattern = r'(SELECT\s+.*?)(?:\n\s*\n|$)'
    match = re.search(select_pattern, response, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return None


def generate_response(prompt: str, model: str, use_tools: bool = False) -> str:
    """Generate response from model.

    Args:
        prompt: Input prompt
        model: Model identifier
        use_tools: Whether to use tool calling

    Returns:
        Raw model response
    """
    if use_tools:
        # Future extension point
        raise NotImplementedError("Tool calling mode not yet implemented")

    # Simple mode: direct API call
    try:
        import os
        # Configure for LM Studio
        base_url = os.getenv("OPENAI_API_BASE", "http://localhost:1234/v1")
        api_key = os.getenv("OPENAI_API_KEY", "lm-studio")

        # Set environment for litellm
        os.environ["OPENAI_API_BASE"] = base_url
        os.environ["OPENAI_API_KEY"] = api_key


        response = litellm.completion(
            model=f"openai/{model}",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"


def evaluate_response(expected_result: str, actual_result: str) -> bool:
    """Compare expected vs actual SQL execution results.

    Args:
        expected_result: Expected query result
        actual_result: Actual query result

    Returns:
        True if results match, False otherwise
    """
    if expected_result.startswith("Error:") or actual_result.startswith("Error:"):
        return False

    return expected_result.strip() == actual_result.strip()


def run_evaluation(questions_file: str, db_path: str, model: str, use_tools: bool = False) -> Dict[str, Any]:
    """Run evaluation on dataset.

    Args:
        questions_file: Path to JSONL questions file
        db_path: Path to database
        model: Model identifier
        use_tools: Whether to use tool calling

    Returns:
        Evaluation results dictionary
    """
    results = []
    correct = 0
    total = 0

    with open(questions_file, 'r') as f:
        for line in f:
            question_data = json.loads(line.strip())
            question = question_data['question']
            expected_sql = question_data['sql']

            print(f"\nQuestion: {question}")

            # Generate response
            prompt = create_prompt(question, db_path, use_tools)
            response = generate_response(prompt, model, use_tools)

            # Extract SQL
            extracted_sql = extract_sql(response)

            if extracted_sql is None:
                print("Failed to extract SQL from response")
                results.append({
                    'question': question,
                    'expected_sql': expected_sql,
                    'extracted_sql': None,
                    'correct': False,
                    'error': 'SQL extraction failed'
                })
                total += 1
                continue

            print(f"Generated SQL: {extracted_sql}")

            # Execute both queries
            expected_result = execute_sql(db_path, expected_sql)
            actual_result = execute_sql(db_path, extracted_sql)

            # Evaluate
            is_correct = evaluate_response(expected_result, actual_result)
            if is_correct:
                correct += 1
                print("✓ Correct")
            else:
                print("✗ Incorrect")
                print(f"Expected: {expected_result}")
                print(f"Actual: {actual_result}")

            results.append({
                'question': question,
                'expected_sql': expected_sql,
                'extracted_sql': extracted_sql,
                'expected_result': expected_result,
                'actual_result': actual_result,
                'correct': is_correct
            })

            total += 1

    accuracy = correct / total if total > 0 else 0
    print(f"\nResults: {correct}/{total} correct ({accuracy:.2%})")

    return {
        'accuracy': accuracy,
        'correct': correct,
        'total': total,
        'results': results
    }


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Evaluate SQL generation models',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dataset mode
  python eval.py hello_world --model qwen/qwen3-30b-a3b-2507
  python eval.py wikisql --model google/gemma-3-12b

  # Direct file mode
  python eval.py --questions questions.jsonl --db database.db --model llama3:8b
        """
    )

    parser.add_argument(
        'dataset',
        nargs='?',
        help='Dataset name (e.g., hello_world, wikisql)'
    )

    parser.add_argument(
        '--questions',
        help='Path to questions JSONL file'
    )

    parser.add_argument(
        '--db',
        help='Path to database file'
    )

    parser.add_argument(
        '--model', '-m',
        required=True,
        help='Model identifier'
    )

    parser.add_argument(
        '--use-tools',
        action='store_true',
        help='Use tool calling mode (future)'
    )

    parser.add_argument(
        '--output',
        help='Output results to JSON file (default: runs/results_TIMESTAMP.json)'
    )

    args = parser.parse_args()

    if args.use_tools:
        print("Tool calling mode not yet implemented")
        sys.exit(1)

    # Determine paths based on input mode
    if args.questions and args.db:
        # Direct file mode
        questions_file = args.questions
        db_path = args.db
        dataset_name = "direct_file"
    elif args.dataset:
        # Dataset mode
        dataset_path = Path(f'datasets/{args.dataset}')
        if not dataset_path.exists():
            print(f"Error: Dataset '{args.dataset}' not found at {dataset_path}")
            sys.exit(1)

        questions_file = str(dataset_path / 'questions.jsonl')
        db_path = str(dataset_path / 'database.db')
        dataset_name = args.dataset
    else:
        print("Error: Must specify either:")
        print("  <dataset> --model <model>")
        print("  --questions <file> --db <path> --model <model>")
        sys.exit(1)

    # Validate inputs
    if not Path(questions_file).exists():
        print(f"Questions file not found: {questions_file}")
        sys.exit(1)

    if not Path(db_path).exists():
        print(f"Database file not found: {db_path}")
        sys.exit(1)

    print(f"Dataset: {dataset_name}")
    print(f"Questions: {questions_file}")
    print(f"Database: {db_path}")
    print(f"Model: {args.model}")
    print()

    # Run evaluation
    results = run_evaluation(questions_file, db_path, args.model, args.use_tools)

    # Determine output file
    if args.output:
        output_file = args.output
    else:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_name = args.model.replace('/', '_').replace('@', '_')
        output_file = f"runs/results_{dataset_name}_{model_name}_{timestamp}.json"

    # Create runs directory if it doesn't exist
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    # Save results
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to: {output_file}")


if __name__ == "__main__":
    main()
