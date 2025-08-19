# sqlite-llm-bench MVP Specification

## Overview
Single-afternoon proof of concept implementing core evaluation pipeline with hello_world dataset and two response parsers.

## Architecture

### File Structure
```
sqlite-llm-bench/
├── eval.py                   # Main evaluation script
├── extractors/
│   ├── __init__.py          # Extractor registry
│   ├── base.py              # Base extractor class
│   ├── openai.py            # OpenAI family extractor
│   └── qwen.py              # Qwen family extractor
├── backends/
│   ├── __init__.py          # Backend registry
│   └── lmstudio.py          # LM Studio backend configuration
└── datasets/
    └── hello_world/
        ├── database.db      # Two-table SQLite database
        └── questions.jsonl  # 10-12 questions with gold results
```

### Core Components

**eval.py** (~150-200 lines)
- Generic prompt template (works across all models - backends handle conversion)
- Tool functions: `describe_table`, `execute_sql`
- Evaluation flow: setup → generate → parse → execute → evaluate
- CLI entry point

**Response Parsers (Extractors)**
- Model family-based SQL response parsing logic
- Base extractor handles common response patterns (markdown, plain text)
- Family-specific extractors handle unique response formats
- Parse tool calling responses vs text responses
- Auto-discovery via LiteLLM model name parsing

**Backends**
- LM Studio configuration (temperature, endpoints)
- Automatic prompt template conversion (handled by backend)
- Backend-specific parameter handling

## Dataset

**hello_world database:**
- Two tables: `users`, `orders` with foreign key relationship
- Sufficient data for meaningful queries

**questions.jsonl:**
- 10-12 questions with graduated complexity
- Basic SELECT → joins → subqueries progression
- Gold SQL statements for execution comparison (per spec.md 4.3 format)

## Interface

**CLI:** `python eval.py hello_world --model qwen/qwen3-30b-a3b-2507`

**Tools:**
- `describe_table(table_name)` - Schema information
- `execute_sql(query)` - SQL execution with results

**Output:** Console-only, human-readable pass/fail with details

## Evaluation

- Parse SQL from model responses using extractors
- Execute both predicted SQL and gold SQL against database
- Compare predicted results vs gold SQL results (exact match)
- Basic error handling: capture parsing/SQL/API failures, continue evaluation
- No file output - ephemeral runs for rapid iteration

## Model Support

**Target models:**
- `openai/gpt-oss-20b` via openai.py response parser
- `qwen/qwen3-30b-a3b-2507` via qwen.py response parser

**LiteLLM integration:**
- Model name parsing for response parser selection
- LM Studio backend for local model serving
- Automatic prompt template handling

## Success Criteria

1. **Tool interface validation** - Models can discover schema and execute SQL
2. **Response parser validation** - Family-based SQL extraction works across models
3. **Backend abstraction validation** - Automatic prompt formatting works
4. **Evaluation pipeline validation** - End-to-end question → response → SQL → result flow

## Implementation Notes

- Single-file main script with functional decomposition
- Generic prompt template works across models (backends handle specialization)
- Response parser registry uses LiteLLM model family detection
- No dataset management - direct file references
- Minimal documentation - focus on technical validation

## References

See full specification in `spec.md` sections:
- 7.1 Core Tools (tool interface)
- 9.3 Model Response Parser Architecture (response parser pattern)
- 6.2 Backend Auto-Detection (backend system)
- 4.3 Question File Format (questions.jsonl structure: {question, sql, table})
