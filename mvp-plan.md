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
- [ ] Create `datasets/hello_world/database.db` with SQLite
- [ ] Design users table: id (PK), name, email, created_at
- [ ] Design orders table: id (PK), user_id (FK), product, amount, order_date
- [ ] Insert 8-10 sample records across both tables
- [ ] Verify foreign key relationships work correctly

### 1.3 Questions Dataset
- [ ] Create `datasets/hello_world/questions.jsonl`
- [ ] Write 3-4 basic SELECT questions with WHERE clauses
- [ ] Write 3-4 JOIN questions (users + orders)
- [ ] Write 2-3 aggregate questions (COUNT, SUM, GROUP BY)
- [ ] Write 1-2 subquery questions
- [ ] Generate and verify gold results for each question
- [ ] Validate JSONL format with question_id, question, expected_result fields

### 1.4 Basic CLI Setup
- [ ] Create `eval.py` with argument parsing
- [ ] Implement `--model` and dataset positional argument
- [ ] Add basic help text and argument validation
- [ ] Test CLI accepts: `python eval.py hello_world --model test/model`

## Phase 2: Core Pipeline

### 2.1 Tool Functions
- [ ] Implement `describe_table(table_name)` function
- [ ] Return column names, types, constraints in structured format
- [ ] Implement `execute_sql(query)` function  
- [ ] Return query results as list of dictionaries
- [ ] Add basic SQL safety checks (no DROP, DELETE, UPDATE)
- [ ] Test tools against hello_world database

### 2.2 Generic Prompt Template
- [ ] Design single prompt template for all models
- [ ] Include clear tool descriptions (`describe_table`, `execute_sql`)
- [ ] Add SQL generation instructions
- [ ] Format as standard OpenAI chat messages
- [ ] Test prompt works across different backends (LM Studio handles conversion)

### 2.3 Basic Evaluation Flow
- [ ] Implement `setup()` function - load dataset, connect to DB
- [ ] Implement `generate()` function - placeholder for model calls
- [ ] Implement `execute()` function - run generated SQL via tools
- [ ] Implement `evaluate()` function - compare results
- [ ] Connect functions in main() with error boundaries

### 2.4 Result Comparison Logic
- [ ] Implement exact match comparison for query results
- [ ] Handle different result ordering (sort before compare)
- [ ] Add support for numeric precision tolerance
- [ ] Return pass/fail with detailed diff information
- [ ] Test with known good/bad SQL examples

### 2.5 Response Parsing Infrastructure
- [ ] Create base response parser class
- [ ] Implement common SQL extraction patterns (markdown, plain text)
- [ ] Add tool calling response parsing
- [ ] Test parsing various response formats

## Phase 3: Model Integration

### 3.1 Base Response Parser Class
- [ ] Create `extractors/base.py` with abstract interface
- [ ] Define `extract_sql()` method signature for response parsing
- [ ] Implement SQL extraction from markdown code blocks (```sql, ```SQL)
- [ ] Add regex patterns for plain text SQL detection
- [ ] Handle tool calling vs text response parsing
- [ ] Parse multiple SQL statements from single response

### 3.2 LiteLLM Backend Integration
- [ ] Install and configure LiteLLM dependency
- [ ] Create model client wrapper (handles all backends)
- [ ] Implement chat completions interface
- [ ] Test backend auto-detection (LM Studio, Ollama, OpenRouter)
- [ ] Verify automatic prompt template conversion works

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

- [ ] **Foundation Complete**: Database and questions load successfully
- [ ] **Pipeline Functional**: Tools work and evaluation logic runs
- [ ] **Backend Integration**: LiteLLM handles multiple backends automatically
- [ ] **Response Parsing**: Both model families parse SQL responses correctly
- [ ] **Generic Prompting**: Single prompt works across all models
- [ ] **MVP Complete**: Full evaluation runs end-to-end successfully

## Final Deliverable

- [ ] Single command runs complete evaluation: `python eval.py hello_world --model qwen/qwen3-30b-a3b-2507`
- [ ] Console output shows clear results for all questions
- [ ] Both target models (OpenAI OSS, Qwen3) work with their response parsers
- [ ] Generic prompt template works across different backends
- [ ] Architecture validates response parser pattern from full spec
- [ ] Demonstrates backend abstraction (same prompt, different template conversion)