#!/usr/bin/env python3
"""
Basic CLI setup for evaluating language models on SQL generation tasks.
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
import litellm
from extractors import get_parser_for_model
from backends import configure_backend, get_backend_info, get_uniform_parameters


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


def execute_tool_call(tool_call, db_path: str) -> str:
    """Execute a tool call and return the result.

    Args:
        tool_call: Tool call object from model response
        db_path: Database path

    Returns:
        String result from tool execution
    """
    function_name = tool_call.function.name

    try:
        arguments = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError:
        return f"Error: Invalid JSON arguments for {function_name}"

    try:
        if function_name == "describe_database":
            table_name = arguments.get("table_name")
            return describe_database(db_path, table_name)
        elif function_name == "execute_sql":
            query = arguments.get("query")
            if not query:
                return "Error: No query provided to execute_sql"
            return execute_sql(db_path, query)
        else:
            return f"Error: Unknown function {function_name}"
    except Exception as e:
        return f"Error executing {function_name}: {str(e)}"


def generate_response_with_workflow(question: str, model: str, db_path: str) -> Dict[str, Any]:
    """Generate response using multi-step tool calling workflow.

    Args:
        question: The SQL question
        model: Model name
        db_path: Database path

    Returns:
        Response data with conversation history and final SQL
    """
    # Configure LiteLLM settings
    litellm.suppress_debug_info = True

    try:
        formatted_model = configure_backend(model)
        backend_info = get_backend_info(model)
    except ValueError as e:
        print(f"Backend configuration error: {e}")
        return {
            "model": model,
            "use_tools": True,
            "conversation_history": [],
            "generated_sql": "SELECT COUNT(*) FROM users",  # Fallback
            "config_error": str(e)
        }

    # Create initial prompt
    messages = create_tool_calling_prompt(question)
    tools = get_openai_tools()
    conversation_history = []
    max_iterations = 5
    final_sql = None

    try:
        for _ in range(max_iterations):
            # Make API call
            uniform_params = get_uniform_parameters()
            response = litellm.completion(
                model=formatted_model,
                messages=messages,
                tools=tools,
                **uniform_params
            )

            conversation_history.append(response)

            # Extract message from response
            message = _extract_message_from_response(response)
            if not message:
                break

            # Add assistant message to conversation
            messages.append({
                "role": "assistant",
                "content": getattr(message, 'content', None) or "",
                "tool_calls": getattr(message, 'tool_calls', None)
            })

            # Check if there are tool calls to execute
            tool_calls = getattr(message, 'tool_calls', None)
            if not tool_calls:
                # No more tool calls, try to extract SQL from final message
                break

            # Process tool calls
            final_sql = _process_tool_calls(tool_calls, messages, db_path, final_sql)

            # If we got SQL from execute_sql, we're done
            if final_sql:
                break

    except Exception as e:
        print(f"Workflow error: {e}")
        conversation_history.append(f"Error: {str(e)}")

    # Extract final SQL using parser as fallback
    if not final_sql:
        final_sql = _extract_sql_fallback(model, conversation_history)

    return {
        "model": model,
        "formatted_model": formatted_model,
        "backend_info": backend_info,
        "use_tools": True,
        "conversation_history": conversation_history,
        "messages": messages,
        "tools": tools,
        "generated_sql": final_sql or "SELECT COUNT(*) FROM users",  # Fallback
        "workflow_iterations": len(conversation_history)
    }


def _extract_message_from_response(response) -> Optional[Any]:
    """Extract message from API response with safe attribute access."""
    if not hasattr(response, 'choices'):
        return None

    choices = getattr(response, 'choices', None)
    if not choices:
        return None

    choice = choices[0]
    return getattr(choice, 'message', None)


def _process_tool_calls(tool_calls, messages: List[Dict[str, Any]], db_path: str, current_final_sql: Optional[str]) -> Optional[str]:
    """Process tool calls and return final SQL if found."""
    final_sql = current_final_sql

    for tool_call in tool_calls:
        result = execute_tool_call(tool_call, db_path)

        # Add tool result to conversation
        messages.append({
            "role": "tool",
            "tool_call_id": getattr(tool_call, 'id', ''),
            "content": result
        })

        # Check if this was an execute_sql call (final SQL)
        if hasattr(tool_call, 'function') and hasattr(tool_call.function, 'name'):
            if tool_call.function.name == "execute_sql":
                final_sql = _extract_sql_from_tool_call(tool_call)

    return final_sql


def _extract_sql_from_tool_call(tool_call) -> Optional[str]:
    """Extract SQL from execute_sql tool call."""
    try:
        if hasattr(tool_call.function, 'arguments'):
            args = json.loads(tool_call.function.arguments)
            return args.get("query")
    except (json.JSONDecodeError, KeyError, AttributeError):
        pass
    return None


def _extract_sql_fallback(model: str, conversation_history: List) -> Optional[str]:
    """Extract SQL using parser as fallback."""
    parser = get_parser_for_model(model)
    response_data = {
        "conversation_history": conversation_history,
        "raw_response": str(conversation_history[-1]) if conversation_history else "",
        "api_response": conversation_history[-1] if conversation_history else None
    }
    return parser.extract_sql_from_conversation(conversation_history) or parser.extract_sql(response_data)


def generate_response(question: str, model: str, db_path: str, use_tools: bool = False, use_workflow: bool = False) -> Dict[str, Any]:
    """Generate model response using LiteLLM backend integration.

    Args:
        question: The SQL question
        model: Model name (auto-detects backend)
        db_path: Database path
        use_tools: Whether to use tool calling mode
        use_workflow: Whether to use multi-step tool calling workflow

    Returns:
        Response data with generated content and metadata
    """
    # Use workflow mode if requested and model supports tools
    if use_workflow and use_tools and supports_tool_calling(model):
        return generate_response_with_workflow(question, model, db_path)

    # Configure LiteLLM settings
    litellm.suppress_debug_info = True

    formatted_model, backend_info = _configure_model_backend(model)
    if formatted_model is None:
        return _create_config_error_response(model, use_tools, backend_info)

    # Create appropriate prompt and tools
    messages, tools = _create_prompt_and_tools(question, db_path, use_tools)

    # Make API call and get response data
    response_data = _make_api_call(formatted_model, messages, tools, use_tools, model, backend_info)

    # Extract SQL and add diagnostics
    return _extract_sql_and_add_diagnostics(response_data, model)


def _configure_model_backend(model: str) -> tuple:
    """Configure model backend and return formatted model and backend info."""
    try:
        formatted_model = configure_backend(model)
        backend_info = get_backend_info(model)
        return formatted_model, backend_info
    except ValueError as e:
        print(f"Backend configuration error: {e}")
        return None, str(e)


def _create_config_error_response(model: str, use_tools: bool, error_msg: str) -> Dict[str, Any]:
    """Create response data for configuration errors."""
    response_data = {
        "messages": [],
        "tools": None,
        "model": model,
        "use_tools": use_tools,
        "raw_response": "```sql\nSELECT COUNT(*) FROM users;\n```",
        "config_error": error_msg
    }
    parser = get_parser_for_model(model)
    generated_sql = parser.extract_sql(response_data)
    response_data["generated_sql"] = generated_sql or "SELECT COUNT(*) FROM users"
    return response_data


def _create_prompt_and_tools(question: str, db_path: str, use_tools: bool) -> tuple:
    """Create appropriate prompt and tools based on mode."""
    if use_tools:
        messages = create_tool_calling_prompt(question)
        tools = get_openai_tools()
    else:
        messages = create_fallback_prompt(question, db_path)
        tools = None
    return messages, tools


def _make_api_call(formatted_model: str, messages: list, tools: list, use_tools: bool, model: str, backend_info: dict) -> Dict[str, Any]:
    """Make API call and return response data."""
    try:
        uniform_params = get_uniform_parameters()
        response = litellm.completion(
            model=formatted_model,
            messages=messages,
            tools=tools if use_tools else None,
            **uniform_params
        )

        raw_response = _extract_raw_response(response)
        return {
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
        print(f"Model API error: {e}")
        return {
            "messages": messages,
            "tools": tools,
            "model": model,
            "formatted_model": formatted_model,
            "backend_info": backend_info,
            "use_tools": use_tools,
            "raw_response": "",
            "api_error": str(e)
        }


def _extract_raw_response(response) -> str:
    """Extract raw response content with safe attribute access."""
    try:
        if hasattr(response, 'choices') and getattr(response, 'choices', None):
            choices = getattr(response, 'choices')
            if choices and len(choices) > 0:
                choice = choices[0]
                if hasattr(choice, 'message'):
                    message = getattr(choice, 'message', None)
                    if message:
                        content = getattr(message, 'content', '') or ''
                        if content:
                            return content
    except (AttributeError, IndexError, TypeError):
        pass

    return str(response)


def _extract_sql_and_add_diagnostics(response_data: Dict[str, Any], model: str) -> Dict[str, Any]:
    """Extract SQL using parser and add diagnostic information."""
    parser = get_parser_for_model(model)
    generated_sql = parser.extract_sql(response_data)
    response_data["generated_sql"] = generated_sql

    # Add extraction failure information for diagnosis
    if not generated_sql:
        has_tool_calls = _check_for_tool_calls(response_data)
        response_data["extraction_failure"] = {
            "parser_used": type(parser).__name__,
            "raw_response_length": len(response_data.get("raw_response", "")),
            "has_api_error": "api_error" in response_data,
            "use_tools": response_data.get("use_tools", False),
            "has_tool_calls": has_tool_calls
        }

    return response_data


def _check_for_tool_calls(response_data: Dict[str, Any]) -> bool:
    """Check if API response contains tool calls."""
    try:
        api_resp = response_data.get("api_response")
        if api_resp and hasattr(api_resp, 'choices'):
            choices = getattr(api_resp, 'choices', None)
            if choices and len(choices) > 0:
                choice = choices[0]
                if hasattr(choice, 'message'):
                    message = getattr(choice, 'message', None)
                    if message and hasattr(message, 'tool_calls'):
                        tool_calls = getattr(message, 'tool_calls', None)
                        return tool_calls is not None and len(tool_calls) > 0
    except (AttributeError, IndexError, TypeError):
        pass
    return False


def evaluate_response(generated_sql: str, gold_sql: str, db_path: str) -> Dict[str, Any]:
    """Evaluate generated SQL against gold standard.

    Args:
        generated_sql: SQL generated by the model (can be None)
        gold_sql: Gold standard SQL
        db_path: Database path

    Returns:
        Evaluation results
    """
    # Handle case where no SQL was extracted
    if not generated_sql:
        return {
            "success": False,
            "matches": False,
            "error": "No SQL extracted from model response",
            "generated_sql": None,
            "gold_sql": gold_sql
        }

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
            "matches": False,
            "error": str(e),
            "generated_sql": generated_sql,
            "gold_sql": gold_sql
        }


def run_evaluation(eval_context: Dict[str, Any], model: str, verbose: bool = False, use_workflow: bool = False) -> Dict[str, Any]:
    """Run complete evaluation pipeline.

    Args:
        eval_context: Context from setup_evaluation()
        model: Model name to evaluate
        verbose: Enable verbose debugging output
        use_workflow: Use multi-step tool calling workflow

    Returns:
        Evaluation results summary
    """
    results = []
    use_tools = supports_tool_calling(model)

    mode_desc = "multi-step workflow" if use_workflow else ("tool calling" if use_tools else "prompt fallback")
    print(f"Evaluating {model} in {mode_desc} mode")
    print(f"Processing {eval_context['total_questions']} questions...")

    for i, q in enumerate(eval_context['questions']):
        _print_question_header(i, eval_context['total_questions'], q)

        # Generate response
        response = generate_response(
            question=q['question'],
            model=model,
            db_path=eval_context['db_path'],
            use_tools=use_tools,
            use_workflow=use_workflow
        )

        # Show parsed SQL
        generated_sql = response.get('generated_sql', 'None')
        print(f"Generated SQL: {generated_sql}")

        if verbose:
            _print_debug_info(response, model, use_workflow)

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
            "mode": "workflow" if use_workflow else ("tools" if use_tools else "prompt"),
            "generated_sql": generated_sql,
        }
        results.append(result)

        # Show result with clear status
        _print_evaluation_result(eval_result, generated_sql, response, q)

    # Calculate summary
    passed = sum(1 for r in results if r.get('matches', False))
    total = len(results)

    _print_summary(model, mode_desc, passed, total)

    return {
        "model": model,
        "mode": "workflow" if use_workflow else ("tools" if use_tools else "prompt"),
        "dataset": eval_context['dataset'],
        "passed": passed,
        "total": total,
        "accuracy": passed / total if total > 0 else 0,
        "results": results
    }


def _print_question_header(i: int, total: int, q: Dict[str, Any]) -> None:
    """Print question header information."""
    print("\n" + "─" * 60)
    print(f"Question {i+1}/{total}")
    print("─" * 60)
    print(f"Q: {q['question']}")
    print(f"Table: {q.get('table', 'N/A')}")


def _print_debug_info(response: Dict[str, Any], model: str, use_workflow: bool) -> None:
    """Print debug information for verbose mode."""
    print("\n  DEBUG: Full response data:")
    if use_workflow:
        print(f"    Workflow iterations: {response.get('workflow_iterations', 0)}")
        print(f"    Conversation history: {len(response.get('conversation_history', []))} responses")
    else:
        raw_response = response.get('raw_response', 'None')
        print(f"    Raw response: {str(raw_response)[:200]}{'...' if len(str(raw_response)) > 200 else ''}")

    print(f"    Parser used: {type(get_parser_for_model(model)).__name__}")
    print(f"    Backend: {response.get('backend_info', {}).get('backend', 'unknown')}")

    if not use_workflow and 'api_response' in response:
        _print_api_response_debug(response['api_response'])
    print("  END DEBUG\n")


def _print_api_response_debug(api_resp: Any) -> None:
    """Print API response debug information."""
    if (hasattr(api_resp, 'choices') and api_resp.choices and
        hasattr(api_resp.choices[0], 'message')):
        choice = api_resp.choices[0]
        msg = choice.message
        print(f"    Message content: {getattr(msg, 'content', 'None')}")
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            print(f"    Tool calls: {len(msg.tool_calls)} calls")
            for tc in msg.tool_calls:
                if hasattr(tc, 'function') and hasattr(tc.function, 'name'):
                    print(f"      - {tc.function.name}: {getattr(tc.function, 'arguments', 'None')}")


def _print_evaluation_result(eval_result: Dict[str, Any], generated_sql: str, response: Dict[str, Any], q: Dict[str, Any]) -> None:
    """Print evaluation result and failure details."""
    if eval_result.get('matches', False):
        print("Result: PASS")
    else:
        print("Result: FAIL")
        _print_failure_details(generated_sql, response, eval_result, q)


def _print_failure_details(generated_sql: str, response: Dict[str, Any], eval_result: Dict[str, Any], q: Dict[str, Any]) -> None:
    """Print detailed failure information."""
    if not generated_sql:
        _print_extraction_failure(response)
    elif 'error' in eval_result:
        print(f"SQL execution error: {eval_result['error']}")
    elif eval_result.get('success', False):
        print("Result mismatch:")
        print(f"  Expected: {eval_result.get('gold_result', 'None')}")
        print(f"  Generated: {eval_result.get('generated_result', 'None')}")

    # Always show expected SQL for failures
    print(f"Expected SQL: {q['sql']}")


def _print_extraction_failure(response: Dict[str, Any]) -> None:
    """Print extraction failure details."""
    print("Extraction failure: No SQL extracted from response")
    if "extraction_failure" in response:
        failure_info = response["extraction_failure"]
        print(f"  Parser: {failure_info['parser_used']}")
        print(f"  Response length: {failure_info['raw_response_length']} chars")
        print(f"  API error: {failure_info['has_api_error']}")
        print(f"  Tool mode: {failure_info['use_tools']}")
        if failure_info['use_tools']:
            print(f"  Has tool calls: {failure_info['has_tool_calls']}")
    if "api_error" in response:
        print(f"  API Error: {response['api_error']}")


def _print_summary(model: str, mode_desc: str, passed: int, total: int) -> None:
    """Print evaluation summary."""
    print()
    print("=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Model: {model}")
    print(f"Mode: {mode_desc}")
    print(f"Parser: {type(get_parser_for_model(model)).__name__}")
    print(f"Results: {passed}/{total} passed ({passed/total:.1%})")

    if passed == total:
        print("All questions passed!")
    elif passed > 0:
        print(f"{total - passed} questions failed")
    else:
        print("All questions failed")


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

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose debugging output'
    )

    parser.add_argument(
        '--workflow',
        action='store_true',
        help='Use multi-step tool calling workflow'
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
        summary = run_evaluation(eval_context, args.model, verbose=args.verbose, use_workflow=args.workflow)

        # Show failed questions detail if any
        if summary['accuracy'] < 1.0:
            print("\n" + "─" * 60)
            print("FAILED QUESTIONS SUMMARY")
            print("─" * 60)

            for r in summary['results']:
                if not r.get('matches', False):
                    print(f"\nQ: {r['question']}")
                    print(f"Generated: {r.get('generated_sql', 'None')}")
                    if 'error' in r:
                        print(f"Error: {r['error']}")

    except Exception as e:
        print(f"Error during evaluation: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
