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

**eval.py** (~500+ lines)
- Dual prompt templates (tool calling + fallback modes with schema injection)
- Tool functions: `describe_database`, `execute_sql` (string-based SQLite CLI format)
- OpenAI function calling definitions for tool-capable models
- Evaluation flow: setup → generate → parse → execute → evaluate
- CLI entry point with complete evaluation pipeline

**Response Parsers (Extractors)**
- Model family-based SQL response parsing logic (placeholder implementation)
- Dual-mode parsing: tool calling responses vs text responses
- String-based tool returns maintain SQLite CLI format consistency
- Auto-discovery via model name pattern matching
- Base extraction patterns for MVP validation

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

**Tools (Dual-Mode):**
- `describe_database(table_name=None)` - Schema information in SQLite CLI format
- `execute_sql(query)` - SQL execution with pipe-separated results
- OpenAI function definitions for tool-calling capable models

**Output:** Console evaluation summary with pass/fail details and accuracy metrics

## Evaluation

- Mode detection: tool calling vs prompt fallback based on model capabilities
- Execute both predicted SQL and gold SQL using same `execute_sql()` function
- Compare predicted results vs gold SQL results (string exact match)
- Basic error handling: capture parsing/SQL/API failures, continue evaluation
- Console output with detailed evaluation summary and accuracy metrics

## Model Support

**Target models:**
- `openai/gpt-oss-20b` via openai.py response parser
- `qwen/qwen3-30b-a3b-2507` via qwen.py response parser

**LiteLLM integration:**
- Model name parsing for response parser selection
- LM Studio backend for local model serving
- Automatic prompt template handling

## Success Criteria

- **Dual-mode tool validation** - Tools work in both function calling and prompt modes
- **Response parser validation** - Family-based SQL extraction works across models  
- **Backend abstraction validation** - Automatic prompt formatting works
- **Evaluation pipeline validation** - End-to-end question → response → SQL → result flow
- **Tool-first policy validation** - Function calling preferred, prompt fallback when unsupported

## Implementation Notes

- Single-file main script with functional decomposition
- Dual prompt templates: minimal for tool calling, rich for fallback
- String-based tool returns (SQLite CLI format) with OpenAI function definitions
- Response parser registry uses LiteLLM model family detection
- Tool capability detection drives prompt mode selection
- No dataset management - direct file references
- Minimal documentation - focus on technical validation

## References

See full specification in `spec.md` sections:
- 7.1 Core Tools (dual-mode tool interface with string returns)
- 9.1 Tool-First Policy (function calling preferred, prompt fallback)
- 9.3 Model Response Parser Architecture (response parser pattern)
- 6.2 Backend Auto-Detection (backend system)
- 4.3 Question File Format (questions.jsonl structure: {question, sql, table})
