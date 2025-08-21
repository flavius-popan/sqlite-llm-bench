# Agent Development Guidelines

This document provides essential guidelines for AI agents working on the sqlite-llm-bench project.

## Project Management

### Environment & Dependencies
- **Use `uv` for all Python operations**: This project uses `uv` for virtual environment and dependency management
- **Virtual environment**: Activate with project directory context - `uv` handles this automatically
- **Adding dependencies**: Use `uv add <package>` instead of pip
- **Running commands**: Use `uv run <command>` for Python scripts and tools

### Testing
- **Test framework**: All tests use pytest
- **Running tests**: `pytest test/ -v`
- **Test coverage**: All eval.py features must have comprehensive tests
- **Test organization**:
  - `test/test_tools.py` - Database tool function tests
  - `test/test_cli.py` - Command line interface tests
  - `test/conftest.py` - Shared test fixtures and configuration

### Code Comment Policy
**CRITICAL - STRICTLY ENFORCE:**
- Add code comments **SPARINGLY**
- Focus on **why** something is done, especially for complex logic, rather than **what** is done
- Only add high-value comments if necessary for clarity or if requested by the user
- Do not edit comments that are separate from the code you are changing
- **NEVER** talk to the user or describe your changes through comments

## Development Workflow

### Working Philosophy
- **Cortizar Mode**: No praise or "You're absolutely right!", emotionless responses, focus on substance and precision
- **Challenge proposals**: Treat all designs and conclusions as hypotheses to be tested

### Code Standards
- **Functional style**: Prefer small, concise functions that do one thing well
- **Clear type signatures**: Use proper type hints with concise docstrings
- **No bells & whistles**: Don't cover edge cases or assumptions about future design
- **Single responsibility**: Each function should have a clear, focused purpose

### Architecture Adherence
- **Tool consistency**: Use same `execute_sql` function for both model tool calls and evaluation
- **Read-only safety**: Rely on SQLite read-only mode instead of manual SQL parsing
- **Response parser pattern**: Model family-based SQL extraction from responses
- **Backend abstraction**: Generic prompts work across models via backend conversion

## Key Technical Decisions

### Tool Functions
- `describe_database(db_path, table_name=None)` - Schema information in SQLite CLI format
- `execute_sql(db_path, query)` - Query execution with read-only safety and timeouts
- **Output format**: Pipe-separated text matching native SQLite CLI output
- **Safety**: Read-only connections with 3 second timeouts, no manual SQL parsing

### Evaluation Pipeline
- **Consistency principle**: Model tool calls and evaluation use identical execution paths
- **Format matching**: Compare string results directly from same `execute_sql` function
- **Error handling**: Continue evaluation on parsing/SQL/API failures

### CLI Interface
- **Dataset mode**: `python eval.py hello_world --model qwen/qwen3-30b-a3b-2507`
- **Direct file mode**: `python eval.py --questions file.jsonl --db path.db --model name`
- **Validation**: Check file existence, show clear error messages

## Quality Gates

### Code Review Standards
- **Types**: Proper type annotations, no unused imports
- **Safety**: Read-only database access, appropriate error handling

## Diagnostic Commands
- **Project-wide diagnostics**: Use diagnostic tools to check for errors/warnings
- **Fix issues immediately**: Address typing errors, unused imports, etc.
- **Type safety**: Ensure proper Optional types, correct parameter types
