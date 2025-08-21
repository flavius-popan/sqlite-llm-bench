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
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
import os
import requests
from openai import OpenAI


_DEFAULT_MODEL_PARAMS = {"temperature": 0.1, "top_p": 1.0, "max_tokens": 512}

REASONING_KEYS = ['reasoning', 'reasoning_content']

BACKENDS = {
    "lm_studio": {
        "base_url": "http://localhost:1234/v1",
        "provider": "openai",
        "api_key": "lm-studio",
        "default_params": _DEFAULT_MODEL_PARAMS
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "provider": "openai",
        "api_key": "ollama",
        "default_params": _DEFAULT_MODEL_PARAMS
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "provider": "openai",
        "api_key": None,
        "default_params": _DEFAULT_MODEL_PARAMS
    }
}


def get_backend(backend_name: Optional[str] = None) -> Optional[str]:
    """Get available backend, either by manual selection or auto-detection.

    Args:
        backend_name: Optional backend name to force selection

    Returns:
        Backend name if available, None if none found
    """
    if backend_name:
        if backend_name in BACKENDS:
            return backend_name
        return None

    # Auto-detection fallback
    for name, config in BACKENDS.items():
        if name == "openrouter":
            if os.getenv("OPENROUTER_API_KEY"):
                return name
            continue

        try:
            response = requests.get(f"{config['base_url'].rstrip('/v1')}/", timeout=2)
            if response.status_code < 500:
                return name
        except (requests.exceptions.RequestException, requests.exceptions.Timeout):
            continue

    return None


def initialize_client(backend_name: Optional[str] = None) -> tuple[Optional[OpenAI], Optional[str]]:
    """Initialize OpenAI client with a specific backend.

    Args:
        backend_name: Optional backend name to initialize

    Returns:
        Tuple of (client, backend_name) or (None, None) if no backend available
    """
    backend_name = get_backend(backend_name)
    if not backend_name:
        return None, None

    backend_config = BACKENDS[backend_name]

    # Get API key
    api_key = backend_config["api_key"]
    if backend_name == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return None, None

    try:
        client = OpenAI(
            base_url=backend_config["base_url"],
            api_key=api_key
        )
        return client, backend_name
    except Exception:
        return None, None


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

Provide ONLY the SQL query wrapped in ```sql blocks."""

    return prompt


def extract_sql(response: str) -> Optional[str]:
    """Extract SQL query from model response content.

    Args:
        response: Raw model response content

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


def generate_response(prompt: str, model: str, client: OpenAI, backend_name: str, use_tools: bool = False) -> Any:
    """Generate response from model.

    Args:
        prompt: Input prompt
        model: Model identifier
        client: Initialized OpenAI client
        backend_name: Name of the backend being used
        use_tools: Whether to use tool calling

    Returns:
        The message object from the API response

    Raises:
        Exception: If model call fails
    """
    if use_tools:
        # Future extension point
        raise NotImplementedError("Tool calling mode not yet implemented")

    # Use backend default params
    params = BACKENDS[backend_name]["default_params"].copy()

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        **params
    )

    return response.choices[0].message


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


def calculate_performance_metrics(response_times: List[float], total_time: float) -> Dict[str, float]:
    """Calculate performance metrics from timing data.

    Args:
        response_times: List of individual response times in seconds
        total_time: Total evaluation time in seconds

    Returns:
        Dictionary with performance metrics
    """
    avg_per_response = sum(response_times) / len(response_times) if response_times else 0

    return {
        'total_time': round(total_time, 2),
        'avg_per_response': round(avg_per_response, 2)
    }


def extract_model_name(model: str) -> str:
    """Extract clean model name for directory structure.

    Args:
        model: Full model identifier (e.g., 'qwen/qwen3-30b-a3b-2507')

    Returns:
        Clean model name for directory (e.g., 'qwen3-30b-a3b-2507')
    """
    # Take last part after '/' and replace '@' with '_'
    return model.split('/')[-1].replace('@', '_')


def run_evaluation(questions_file: str,
                   db_path: str,
                   model: str,
                   client: OpenAI,
                   backend_name: str,
                   use_tools: bool = False) -> Dict[str, Any]:
    """Run evaluation on dataset.

    Args:
        questions_file: Path to JSONL questions file
        db_path: Path to database
        model: Model identifier
        client: Initialized OpenAI client
        backend_name: Name of the backend being used
        use_tools: Whether to use tool calling

    Returns:
        Evaluation results dictionary
    """
    results = []
    correct = 0
    total = 0
    response_times = []

    # Count total questions
    with open(questions_file, 'r') as f:
        total_questions = sum(1 for _ in f)

    print(f"Processing {total_questions} questions: ", end="", flush=True)

    # Start timing from first request
    start_time = time.time()

    with open(questions_file, 'r') as f:
        for line in f:
            question_data = json.loads(line.strip())
            question = question_data['question']
            expected_sql = question_data['sql']

            try:
                # Generate response with timing
                prompt = create_prompt(question, db_path, use_tools)

                response_start = time.time()
                response = generate_response(prompt, model, client, backend_name, use_tools)
                response_end = time.time()
                response_times.append(response_end - response_start)

                # Extract SQL from content field
                raw_content = response.content if response.content else ""
                extracted_sql = extract_sql(raw_content)

                if extracted_sql is None:
                    result_dict = {
                        'question': question,
                        'expected_sql': expected_sql,
                        'extracted_sql': None,
                        'error': 'SQL extraction failed',
                        'raw_content': raw_content,
                        'correct': False
                    }
                    for key in REASONING_KEYS:
                        if hasattr(response, key) and getattr(response, key):
                            result_dict['reasoning'] = getattr(response, key)
                            break

                    results.append(result_dict)
                    total += 1
                    print("F", end="", flush=True)
                    continue

            except Exception as e:
                print(f"\nError: Model call failed - {str(e)}")
                sys.exit(1)

            # Execute both queries
            expected_result = execute_sql(db_path, expected_sql)
            actual_result = execute_sql(db_path, extracted_sql)

            # Evaluate
            is_correct = evaluate_response(expected_result, actual_result)

            result_dict = {
                'question': question,
                'expected_sql': expected_sql,
                'extracted_sql': extracted_sql,
                'expected_result': expected_result,
                'actual_result': actual_result,
                'raw_content': raw_content,
                'correct': is_correct,
            }

            results.append(result_dict)

            if is_correct:
                correct += 1
                print(".", end="", flush=True)
            else:
                print("F", end="", flush=True)

            total += 1

    # End timing after last request
    end_time = time.time()
    total_time = end_time - start_time

    accuracy = correct / total if total > 0 else 0
    failed = total - correct

    # Calculate performance metrics
    perf_metrics = calculate_performance_metrics(response_times, total_time)

    print("\n\n=== EVALUATION RESULTS ===")
    print(f"Accuracy:         {correct}/{total} ({accuracy:.2%})")
    print(f"Total Runtime:    {perf_metrics['total_time']}s")
    print(f"Avg Per Question: {perf_metrics['avg_per_response']}s")
    print(f"Questions Failed: {failed}")

    return {
        'accuracy': accuracy,
        'correct': correct,
        'total': total,
        'failed': failed,
        'performance': perf_metrics,
        'results': results,
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
        '--backend',
        choices=['lm_studio', 'ollama', 'openrouter'],
        help='Manually select backend'
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

    # Initialize client
    client, backend_name = initialize_client(args.backend)
    if not client or not backend_name:
        print(f"Error: Backend '{args.backend}' not available or no backend detected.")
        print("Please ensure one of the following is running:")
        print("  - LM Studio (http://localhost:1234)")
        print("  - Ollama (http://localhost:11434)")
        print("  - Or set OPENROUTER_API_KEY environment variable")
        sys.exit(1)

    print(f"Dataset: {dataset_name}")
    print(f"Questions: {questions_file}")
    print(f"Database: {db_path}")
    print(f"Model: {args.model}")
    print(f"Backend: {backend_name}\n")

    # Run evaluation
    from datetime import datetime
    start_timestamp = datetime.now().isoformat()

    eval_results = run_evaluation(
        questions_file, db_path, args.model, client, backend_name, args.use_tools
    )

    # Determine output file
    if args.output:
        output_file = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_name = extract_model_name(args.model)
        output_file = f"runs/{model_name}/{timestamp}_{dataset_name}.json"

    # Create runs directory if it doesn't exist
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    # Prepare final results object with metadata
    final_results = {
        'metadata': {
            'model': args.model,
            'dataset': dataset_name,
            'backend': backend_name,
            'run_timestamp_utc': start_timestamp,
            'model_params': BACKENDS[backend_name]['default_params']
        },
        **eval_results
    }

    # Save results
    with open(output_file, 'w') as f:
        json.dump(final_results, f, indent=2)
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
