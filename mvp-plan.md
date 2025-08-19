# sqlite-llm-bench MVP Build Plan

## Updated Architecture Focus

**Key Insight**: Backends (LM Studio, Ollama, OpenRouter) handle input formatting automatically. Our extractors are **response parsers** that handle output parsing only.

**Responsibility Split**:
- **Backends**: Convert OpenAI chat format → model-specific templates
- **LiteLLM**: Unified API across backends
- **Response Parsers**: Parse model responses → clean SQL
- **Generic Prompt**: Works across all models (backends handle specialization)

## Phase 1: Foundation & Data

### 1.1 Project Structure Setup
- [x] Create directory structure as specified in mvp.md
- [x] Add `__init__.py` files to extractors/ and backends/
- [x] Verify all directories exist and are properly organized

### 1.2 Hello World Database Creation
- [x] Create `datasets/hello_world/database.db` with SQLite
- [x] Design users table: id (PK), name, email, created_at
- [x] Design orders table: id (PK), user_id (FK), product, amount, order_date
- [x] Insert 8-10 sample records across both tables
- [x] Verify foreign key relationships work correctly

### 1.3 Questions Dataset
- [x] Create `datasets/hello_world/questions.jsonl`
- [x] Write 3-4 basic SELECT questions with WHERE clauses
- [x] Write 3-4 JOIN questions (users + orders)
- [x] Write 2-3 aggregate questions (COUNT, SUM, GROUP BY)
- [x] Write 1-2 subquery questions
- [x] Create gold SQL statements for each question
- [x] Validate JSONL format with question, sql, table fields (per spec.md 4.3)
- [x] Simplify questions for small model success (business tone, reduced complexity)
- [x] Update database to use single names (Alice, Bob, Carol, Dave, Eve)
- [x] Ensure all questions are context-independent (no hardcoded assumptions)

### 1.4 Basic CLI Setup
- [x] Create `eval.py` with argument parsing
- [x] Implement `--model` and dataset positional argument
- [x] Add basic help text and argument validation
- [x] Test CLI accepts: `python eval.py hello_world --model test/model`

## Phase 2: Core Pipeline

### 2.1 Tool Functions
- [x] Implement `describe_database(table_name=None)` function
- [x] Return schema information in SQLite CLI format (pipe-separated PRAGMA output)
- [x] Implement `execute_sql(query)` function with read-only connections and timeouts
- [x] Return query results in SQLite CLI format (headers + pipe-separated values)
- [x] Use SQLite read-only mode for automatic safety (no manual SQL parsing needed)
- [x] Test tools against hello_world database with comprehensive test suite (29 tests)

### 2.2 Generic Prompt Template
- [x] Design dual prompt templates (tool calling + fallback modes)
- [x] Include clear tool descriptions (`describe_database`, `execute_sql`)
- [x] Add SQL generation instructions
- [x] Format as standard OpenAI chat messages
- [x] Test prompt works across different backends (LM Studio handles conversion)
- [x] Add OpenAI function calling definitions for tool registration
- [x] Add model capability detection for tool vs prompt mode selection

### 2.3 Basic Evaluation Flow
- [x] Implement `setup_evaluation()` function - load dataset, connect to DB
- [x] Implement `generate_response()` function - placeholder for model calls
- [x] Implement `evaluate_response()` function - compare results against gold SQL execution
- [x] Connect functions in main() with error boundaries
- [x] Add dual-mode support (tool calling vs prompt fallback)
- [x] Add complete evaluation pipeline with summary reporting

### 2.4 Result Comparison Logic
- [x] Execute both predicted SQL and gold SQL against database
- [x] Implement exact match comparison for query results
- [x] Handle different result ordering (string comparison)
- [x] Return pass/fail with detailed execution information
- [x] Test with known good/bad SQL examples
- [x] Use same `execute_sql()` function for consistency

### 2.5 Response Parsing Infrastructure
- [x] Create dual-mode response handling (tool calls vs text)
- [x] Implement SQL extraction patterns (placeholder for full implementation)
- [x] Add tool calling response parsing support
- [x] Test parsing various response formats (via evaluation pipeline)

## Phase 3: Model Integration

### 3.1 Base Response Parser Class
- [x] Create `extractors/base.py` with abstract interface
- [x] Define `extract_sql()` method signature for response parsing
- [x] Implement SQL extraction from markdown code blocks (```sql, ```SQL)
- [x] Add regex patterns for plain text SQL detection
- [x] Handle tool calling vs text response parsing
- [x] Parse multiple SQL statements from single response

### 3.2 LiteLLM Backend Integration
- [x] Install and configure LiteLLM dependency
- [x] Create model client wrapper (handles all backends)
- [x] Implement chat completions interface
- [x] Test backend auto-detection (LM Studio, Ollama, OpenRouter)
- [x] Verify automatic prompt template conversion works

### 3.3 LM Studio Backend Configuration
- [ ] Create `backends/lmstudio.py` configuration
- [ ] Set default endpoint (http://localhost:1234)
- [ ] Configure model parameters (temperature, max_tokens)
- [ ] Add environment variable overrides
- [ ] Verify LM Studio handles prompt templating automatically

### 3.4 Response Parser Registry
- [ ] Create `extractors/__init__.py` registry system
- [ ] Implement model name → parser family mapping
- [ ] Map model families to response parser classes
- [ ] Add fallback to base parser for unknown models
- [ ] Test registry with target model names

## Phase 4: Model Extractors

### 4.1 OpenAI Family Response Parser
- [ ] Create `extractors/openai.py`
- [ ] Inherit from base response parser
- [ ] Implement OpenAI-specific response parsing (gpt-oss Harmony format)
- [ ] Handle tool calling responses vs text responses
- [ ] Parse multi-channel responses (final, analysis, commentary)
- [ ] Test with sample OpenAI model responses

### 4.2 Qwen Family Response Parser
- [ ] Create `extractors/qwen.py`
- [ ] Inherit from base response parser
- [ ] Implement Qwen3-specific response parsing patterns
- [ ] Handle Qwen response formatting quirks (code block variations)
- [ ] Parse both tool calling and text-based SQL responses
- [ ] Test with sample Qwen model responses

### 4.3 End-to-End Integration
- [ ] Connect response parser registry to evaluation pipeline
- [ ] Wire LiteLLM to handle all backend communication
- [ ] Test complete flow: question → model → response → parsing → SQL → evaluation
- [ ] Verify both target models work with their response parsers
- [ ] Confirm generic prompt works across models via backend conversion

## Phase 5: Polish

### 5.1 Error Handling Integration
- [ ] Add try/catch blocks around model API calls
- [ ] Handle SQL execution errors gracefully
- [ ] Log errors but continue evaluation
- [ ] Add timeout handling for model calls
- [ ] Test error scenarios with invalid inputs

### 5.2 Console Output Formatting
- [ ] Design clear pass/fail output format
- [ ] Show question text, parsed SQL, and result status
- [ ] Add summary statistics (X/Y passed)
- [ ] Include parsing/execution error details for failed questions
- [ ] Display response parser used for each model
- [ ] Test output readability with sample runs

### 5.3 Final Validation
- [ ] Run complete evaluation with both target models
- [ ] Verify all 10-12 questions execute properly
- [ ] Confirm response parser patterns work correctly
- [ ] Test automatic backend detection (LM Studio/Ollama/OpenRouter)
- [ ] Validate generic prompt works across different backends
- [ ] Test error handling with invalid model names

## Success Checkpoints

- [x] **Foundation Complete**: Database and questions load successfully
- [x] **Pipeline Functional**: Tools work and evaluation logic runs with gold SQL comparison
- [x] **Tool Interface Complete**: Dual-mode tools work for both function calling and prompt fallback
- [x] **Prompt Templates Complete**: Tool calling and fallback prompts implemented
- [x] **Evaluation Pipeline Complete**: Full end-to-end evaluation with mode detection
- [ ] **Backend Integration**: LiteLLM handles multiple backends automatically
- [ ] **Response Parsing**: Both model families parse SQL responses correctly
- [ ] **MVP Complete**: Full evaluation runs end-to-end with actual model calls

## Final Deliverable

- [x] Single command runs complete evaluation: `python eval.py hello_world --model qwen/qwen3-30b-a3b-2507`
- [x] Console output shows clear results for all questions with gold SQL comparison
- [x] Dual-mode prompt templates work across different model capabilities
- [x] Architecture validates tool-first policy with fallback from full spec
- [x] Questions use correct format: {question, sql, table} per spec.md section 4.3
- [x] String-based tool returns maintain SQLite CLI format consistency
- [ ] Both target models (OpenAI OSS, Qwen3) work with their response parsers
- [ ] Demonstrates backend abstraction via LiteLLM integration
