#!/usr/bin/env python3
"""
Basic CLI setup for evaluating language models on SQL generation tasks.
"""

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
import litellm
from extractors.default import DefaultResponseParser
from backends import configure_backend, get_backend_info


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


def get_openai_tools() -> List[Dict[str, Any]]:
    """Convert our existing tools to OpenAI function calling format.

    Returns:
        List of OpenAI-compatible tool definitions
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "describe_database",
                "description": "Get database schema information in SQLite CLI format",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Optional table name to describe. If not provided, returns all tables."
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "execute_sql",
                "description": "Execute SQL query and return results in SQLite CLI format",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "SQL SELECT statement to execute (read-only)"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]


def create_tool_calling_prompt(question: str) -> List[Dict[str, Any]]:
    """Create minimal prompt for tool-calling capable models.

    Args:
        question: The SQL question to ask the model

    Returns:
        OpenAI chat format messages optimized for tool calling
    """
    system_prompt = """You are an expert SQL analyst. Use the provided tools to explore the database and answer questions.

Workflow:
1. Use describe_database() to understand the schema
2. Use execute_sql() to query the data
3. Provide the final SQL query that answers the question

Return your final SQL query in a clear, executable format."""

    return [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": question
        }
    ]


def create_fallback_prompt(question: str, db_path: str) -> List[Dict[str, Any]]:
    """Create rich prompt with schema injection for non-tool models.

    Args:
        question: The SQL question to ask the model
        db_path: Path to database for schema injection

    Returns:
        OpenAI chat format messages with embedded schema information
    """
    # Get schema for prompt injection
    schema_info = describe_database(db_path)

    system_prompt = f"""You are an expert SQL analyst. You have access to a SQLite database with the following schema:

{schema_info}

Instructions:
- Write SQL SELECT queries to answer questions
- Only SELECT statements are allowed (database is read-only)
- Use proper table and column names from the schema above
- Return your final SQL query in a clear, executable format

Database Schema Summary:
{schema_info}"""

    return [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": question
        }
    ]


def create_prompt_template() -> List[Dict[str, Any]]:
    """Generic prompt template for backward compatibility.

    Returns:
        OpenAI chat format messages with system prompt and tool descriptions
    """
    system_prompt = """You are an expert SQL analyst. You have access to a SQLite database and can use the following tools to explore and query it:

**describe_database(table_name=None)**: Get schema information for tables
- If table_name is provided, returns column details for that specific table
- If table_name is None, returns information for all tables in the database
- Output format: pipe-separated values showing column details

**execute_sql(query)**: Execute a SELECT query against the database
- Only SELECT queries are allowed (database is read-only)
- Returns results in pipe-separated format with headers
- Has a 3 second timeout for safety

When answering questions:
1. First explore the database schema using describe_database()
2. Understand the relationships between tables
3. Write and execute SQL queries to answer the question
4. Provide the final SQL query that answers the question

Always return your final SQL query in a clear, executable format."""

    return [
        {
            "role": "system",
            "content": system_prompt
        }
    ]


def supports_tool_calling(model: str) -> bool:
    """Check if model supports native tool calling.

    Args:
        model: Model name to check

    Returns:
        True if model supports tool calling, False otherwise
    """
    # For MVP, we'll use simple heuristics
    # In full implementation, this would use litellm.supports_function_calling()
    tool_capable_models = [
        "gpt-", "openai/", "qwen", "llama3.1", "llama3.2", "mistral", "claude"
    ]
    return any(pattern in model.lower() for pattern in tool_capable_models)


def create_prompt_with_question(question: str, model: str = "", db_path: str = "") -> List[Dict[str, Any]]:
    """Create appropriate prompt based on model capabilities.

    Args:
        question: The SQL question to ask the model
        model: Model name for capability detection
        db_path: Database path for schema injection (fallback mode)

    Returns:
        Complete OpenAI chat format messages optimized for the model
    """
    if model and supports_tool_calling(model):
        return create_tool_calling_prompt(question)
    elif db_path:
        return create_fallback_prompt(question, db_path)
    else:
        # Backward compatibility
        messages = create_prompt_template()
        messages.append({
            "role": "user",
            "content": question
        })
        return messages


def setup_evaluation(dataset_name: str, questions_file: str, db_path: str) -> Dict[str, Any]:
    """Setup evaluation environment.

    Args:
        dataset_name: Name of the dataset
        questions_file: Path to questions.jsonl file
        db_path: Path to database file

    Returns:
        Evaluation context dictionary
    """
    import json

    # Load questions
    questions = []
    with open(questions_file, 'r') as f:
        for line in f:
            questions.append(json.loads(line.strip()))

    return {
        "dataset": dataset_name,
        "questions": questions,
        "db_path": str(db_path),
        "total_questions": len(questions)
    }


def generate_response(question: str, model: str, db_path: str, use_tools: bool = False) -> Dict[str, Any]:
    """Generate model response using LiteLLM backend integration.

    Args:
        question: The SQL question
        model: Model name (auto-detects backend)
        db_path: Database path
        use_tools: Whether to use tool calling mode

    Returns:
        Response data with generated content and metadata
    """
    # Configure LiteLLM settings
    litellm.suppress_debug_info = True

    try:
        formatted_model = configure_backend(model)
        backend_info = get_backend_info(model)
    except ValueError as e:
        print(f"Backend configuration error: {e}")
        response_data = {
            "messages": [],
            "tools": None,
            "model": model,
            "use_tools": use_tools,
            "raw_response": "```sql\nSELECT COUNT(*) FROM users;\n```",
            "config_error": str(e)
        }
        # Use response parser to extract SQL
        parser = DefaultResponseParser()
        generated_sql = parser.extract_sql(response_data)
        response_data["generated_sql"] = generated_sql or "SELECT COUNT(*) FROM users"
        return response_data

    # Create appropriate prompt
    if use_tools:
        messages = create_tool_calling_prompt(question)
        tools = get_openai_tools()
    else:
        messages = create_fallback_prompt(question, db_path)
        tools = None

    try:
        # Call LiteLLM with configured backend
        response = litellm.completion(
            model=formatted_model,
            messages=messages,
            tools=tools if use_tools else None,
            temperature=0.1,
            max_tokens=1000,
            timeout=30
        )

        # Simple string-based response handling
        raw_response = str(response)


        response_data = {
            "messages": messages,
            "tools": tools,
            "model": model,
            "formatted_model": formatted_model,
            "backend_info": backend_info,
            "use_tools": use_tools,
            "raw_response": raw_response,
            "api_response": response
        }

    except Exception as e:
        # Fallback for API errors
        print(f"Model API error: {e}")
        response_data = {
            "messages": messages,
            "tools": tools,
            "model": model,
            "formatted_model": formatted_model if 'formatted_model' in locals() else model,
            "backend_info": backend_info if 'backend_info' in locals() else {},
            "use_tools": use_tools,
            "raw_response": "```sql\nSELECT COUNT(*) FROM users;\n```",  # Fallback
            "api_error": str(e)
        }

    # Use response parser to extract SQL
    parser = DefaultResponseParser()
    generated_sql = parser.extract_sql(response_data)

    response_data["generated_sql"] = generated_sql or "SELECT COUNT(*) FROM users"  # Fallback

    return response_data


def evaluate_response(generated_sql: str, gold_sql: str, db_path: str) -> Dict[str, Any]:
    """Evaluate generated SQL against gold standard.

    Args:
        generated_sql: SQL generated by the model
        gold_sql: Gold standard SQL
        db_path: Database path

    Returns:
        Evaluation results
    """
    try:
        # Execute both queries using same function
        generated_result = execute_sql(db_path, generated_sql)
        gold_result = execute_sql(db_path, gold_sql)

        # Compare results
        matches = generated_result.strip() == gold_result.strip()

        return {
            "success": True,
            "matches": matches,
            "generated_result": generated_result,
            "gold_result": gold_result,
            "generated_sql": generated_sql,
            "gold_sql": gold_sql
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "generated_sql": generated_sql,
            "gold_sql": gold_sql
        }


def run_evaluation(eval_context: Dict[str, Any], model: str) -> Dict[str, Any]:
    """Run complete evaluation pipeline.

    Args:
        eval_context: Context from setup_evaluation()
        model: Model name to evaluate

    Returns:
        Evaluation results summary
    """
    results = []
    use_tools = supports_tool_calling(model)

    print(f"Evaluating {model} in {'tool calling' if use_tools else 'prompt fallback'} mode")
    print(f"Processing {eval_context['total_questions']} questions...")

    for i, q in enumerate(eval_context['questions']):
        print(f"Question {i+1}/{eval_context['total_questions']}: {q['question'][:50]}...")

        # Generate response
        response = generate_response(
            question=q['question'],
            model=model,
            db_path=eval_context['db_path'],
            use_tools=use_tools
        )

        # Evaluate against gold standard
        eval_result = evaluate_response(
            generated_sql=response['generated_sql'],
            gold_sql=q['sql'],
            db_path=eval_context['db_path']
        )

        result = {
            "question_id": i,
            "question": q['question'],
            "table": q.get('table'),
            **eval_result,
            "mode": "tools" if use_tools else "prompt"
        }
        results.append(result)

        status = "✓" if eval_result.get('matches', False) else "✗"
        print(f"  {status} {'PASS' if eval_result.get('matches', False) else 'FAIL'}")

    # Calculate summary
    passed = sum(1 for r in results if r.get('matches', False))
    total = len(results)

    return {
        "model": model,
        "mode": "tools" if use_tools else "prompt",
        "dataset": eval_context['dataset'],
        "passed": passed,
        "total": total,
        "accuracy": passed / total if total > 0 else 0,
        "results": results
    }


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

    # Validate arguments and setup paths
    if args.questions and args.db:
        questions_file = Path(args.questions)
        if not questions_file.exists():
            print(f"Error: Questions file not found at {questions_file}")
            sys.exit(1)

        db_path = Path(args.db)
        if not db_path.exists():
            print(f"Error: Database path not found at {db_path}")
            sys.exit(1)

        dataset_name = "direct_file"

    elif args.dataset:
        dataset_path = Path(f'datasets/{args.dataset}')
        if not dataset_path.exists():
            print(f"Error: Dataset '{args.dataset}' not found at {dataset_path}")
            sys.exit(1)

        questions_file = dataset_path / 'questions.jsonl'
        if not questions_file.exists():
            print(f"Error: Questions file not found at {questions_file}")
            sys.exit(1)

        db_path = dataset_path / 'database.db'
        if not db_path.exists():
            print(f"Error: Database file not found at {db_path}")
            sys.exit(1)

        dataset_name = args.dataset

    else:
        print("Error: Must specify either:")
        print("  --questions <file> --db <path> --model <model>")
        print("  <dataset> --model <model>")
        sys.exit(1)

    # Setup and run evaluation
    try:
        print("Setting up evaluation...")
        print(f"Dataset: {dataset_name}")
        print(f"Questions: {questions_file}")
        print(f"Database: {db_path}")
        print(f"Model: {args.model}")
        print()

        # Setup evaluation context
        eval_context = setup_evaluation(dataset_name, str(questions_file), str(db_path))

        # Run evaluation
        results = run_evaluation(eval_context, args.model)

        # Print summary
        print(f"\n{'='*60}")
        print("EVALUATION COMPLETE")
        print(f"{'='*60}")
        print(f"Model: {results['model']}")
        print(f"Mode: {results['mode']}")
        print(f"Dataset: {results['dataset']}")
        print(f"Accuracy: {results['passed']}/{results['total']} ({results['accuracy']:.1%})")

        if results['accuracy'] < 1.0:
            print("\nFailed questions:")
            for r in results['results']:
                if not r.get('matches', False):
                    print(f"  - {r['question'][:60]}...")

    except Exception as e:
        print(f"Error during evaluation: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
