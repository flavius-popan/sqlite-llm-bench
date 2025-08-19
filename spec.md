# sqlite-llm-workbench (v0.4)

> **Primary Goal**: Systematically test any LLM's ability to understand natural language and generate working SQL queries, helping you identify exactly where models succeed and fail in real-world data tasks.

> **Secondary Goal**: Standardized benchmarking framework for comparing models with reproducible scores across industry-standard datasets.

**For developers building**: SQL agents, BI tools, data analysis workflows, or any system that needs reliable natural language → SQL conversion.

**For researchers studying**: LLM capabilities in structured reasoning, tool usage, and domain-specific tasks.

**For enthusiasts**: Easy model comparison tools that run on local hardware with common models.

---

## 1. Mission & Research Focus

**Current MVP Status**: Core evaluation engine implemented with basic dataset support and backend auto-detection.


**Core Question**: *How good is this model at using SQLite's features, functions, and advantages for real-world data tasks?*

This workbench exists to **systematically identify weak spots** in language models' SQL capabilities using well-established industry text-to-SQL datasets. Rather than chasing leaderboard positions, we focus on **precise capability assessment** to further research and development of BI/data analyst workflows and agents.

**Primary Use Cases**:
- **Capability Discovery**: Find exactly where your chosen model fails on specific SQL patterns
- **Production Readiness**: Test models against real-world SQL features before deployment
- **Research Validation**: Systematic assessment of structured reasoning capabilities
- **Model Selection**: Data-driven comparison for SQL agent development

**Secondary Use Cases**:
- **Standardized Benchmarking**: Reproducible scores across models and datasets
- **Performance Tracking**: Monitor improvements across model versions
- **Community Comparison**: Share results with standardized metrics

## 2. Core Design Principles

### 2.1 SQLite-First Research Philosophy

**Principle**: Leverage SQLite's unique strengths to reveal model capabilities that other engines can't test.

* **Real-World Features**: Test JSON operations, window functions, CTEs, and other modern SQL features
* **Tool Integration**: Models must use `execute_sql` tools, not just generate text
* **Production Patterns**: Evaluate patterns developers actually encounter in BI/analytics workflows
* **Human Inspectable**: All evaluation data queryable via standard SQL tools for analysis

### 2.2 Capability Discovery Over Benchmarking

**Principle**: Detailed failure analysis trumps aggregate scores.

* **Granular Tagging**: Automatically tag queries by SQL features, complexity, and patterns
* **Targeted Testing**: Use SQLite views to test specific capabilities (JOINs, aggregations, subqueries)
* **Failure Pattern Analysis**: Identify systematic weaknesses rather than just overall accuracy
* **Model-Agnostic Standards**: Same clear instructions for every model - no special accommodations

### 2.3 Evidence-Based Design from Leading Evaluations

**Principle**: Learn from proven evaluation frameworks while maintaining our broader mission.

Drawing from OpenAI's [gpt-oss evaluation approach](https://cookbook.openai.com/articles/gpt-oss/verifying-implementations) and [Simon Willison's implementation experience](https://til.simonwillison.net/llms/gpt-oss-evals), we adopt:

* **Two-Tier Testing**: Quick smoke tests for immediate feedback + comprehensive evaluations
* **Rich Output Formats**: HTML reports, detailed JSON, and summary statistics for actionable insights
* **Radical Simplicity**: Individual evaluation scripts should be ~100 lines, focused and debuggable
* **Backend Agnostic**: Work with any LLM provider through standardized interfaces (via LiteLLM)
* **Core Metrics Focus**: Start with execution accuracy (EX) and add secondary metrics incrementally
* **Reproducible Results**: Clear dependency management and deterministic evaluation conditions

**Key Insight**: *Simplicity and focus trump architectural elegance in evaluation systems* - but our multi-model mission requires abstraction layers that single-model evals don't need.

### 2.4 Practical Developer Focus

**Principle**: Serve developers building real systems, not just researchers publishing papers.

* **Local-First**: Run on common hardware with local models (LM Studio, Ollama)
* **Three-Tier Complexity**: Match tool complexity to use case complexity
* **Actionable Results**: Clear identification of which SQL patterns work vs. fail
* **Production Relevance**: Test scenarios developers actually encounter

### 2.5 Three-Tier Architecture Overview

**Core Design**: Start simple, scale complexity as needed through three distinct tiers.

#### **Tier 1: Instant Setup (Zero-Config)**
```bash
python eval.py --questions questions.jsonl --db mydata.db
```
* **Purpose**: Immediate testing with minimal setup
* **Input**: JSONL/CSV questions + database file(s)
* **Features**: Default prompt, direct file access, basic evaluation
* **Use Case**: Quick model testing, proof of concept, simple datasets

#### **Tier 2: Templated Datasets (Organized)**
```bash
python create_dataset.py  # Interactive setup
python eval.py mydataset   # CLI infers datasets/mydataset/
```
* **Purpose**: Organized project structure with custom prompts
* **Input**: Structured dataset directories with questions.jsonl + databases/
* **Features**: Custom prompts, organized files, easier CLI usage
* **Use Case**: Ongoing projects, custom datasets, learning examples

#### **Tier 3: Full Upgrade (Advanced Features)**
```bash
python build_dataset.py --input datasets/mydataset/
python eval.py mydataset --view v_questions_joins
```
* **Purpose**: Sophisticated analysis with rich metadata
* **Input**: Tier 2 datasets converted to SQLite questions tables
* **Features**: Auto-generated tags, subset views, cross-dataset analysis
* **Use Case**: Research workflows, comprehensive benchmarking, publication

#### **Dataset Classifications**
* **hello-world**: Tier 2 (learning example, simple structure, easy to understand)
* **wikisql, spider1, bird**: Tier 3 (full advanced features, tags, views, analysis)

#### **CLI Interface Design**
```bash
# Tier 1: Direct file evaluation
python eval.py --questions my_questions.jsonl --db my_database.db

# Tier 2 & 3: Dataset evaluation (CLI infers datasets/ directory)
python eval.py hello-world
python eval.py wikisql --view v_questions_joins_only
python eval.py bird --limit 50
```

---

## 3. Scope & Constraints

**In‑scope**

* Convert upstream text‑to‑SQL datasets into SQLite DBs with unified metadata storage
* Run evaluations via LiteLLM across openai‑compatible backends (LM Studio, Ollama, OpenRouter)
* Support both single-database and multi-database datasets as first-class citizens
* Leverage SQLite views for flexible dataset subsetting and capability targeting
* Report execution‑based metrics with deterministic, serial runs
* Detailed failure analysis and capability gap identification
* Standardized benchmarking scores for model comparison

**Out‑of‑scope**

* Shipping prebuilt `.db` artifacts (we build locally from pinned sources)
* Non‑SQLite engines or custom SQLite extensions
* Model-specific prompt optimizations or hints
* Real-time evaluation or streaming inference
* Multi-turn conversations or query refinement

---

## 4. Three-Tier Data Architecture

**MVP Status**: Tier 1 fully implemented, basic Tier 2 with hello_world dataset. Tier 3 features planned for future releases.


### 4.1 Tier Structure Overview

The workbench supports three tiers of complexity, allowing users to start simple and scale as needed:

**Tier 1 (Instant Setup)**: Direct file evaluation with minimal setup
**Tier 2 (Templated Datasets)**: Organized project structure with custom prompts
**Tier 3 (Advanced Features)**: Full SQLite integration with rich metadata and analysis

### 4.2 Directory Structure by Tier

**Current MVP Implementation**:
```
datasets/
├── hello_world/           # Basic Tier 2 dataset (13 questions)
│   ├── questions.jsonl    # Question/answer pairs
│   └── sample.db         # SQLite database
└── wikisql/              # Partial implementation
    ├── metadata.json     # Dataset metadata
    └── wikisql-top500.db # Database file
```

**Full Architecture (Future)**:


#### **Tier 1: Direct File Mode**
```
# No specific directory structure required
questions.jsonl                    # User's question file
mydata.db                         # User's database file
# OR
databases/                        # Directory of database files
├── sales.db
├── inventory.db
└── customers.db
```

#### **Tier 2: Templated Datasets**
```
datasets/                         # All datasets live here
├── hello-world/                  # Tier 2 example (learning)
│   ├── questions.jsonl          # Questions in standard format
│   ├── databases/               # Database files
│   │   ├── customers.db
│   │   ├── orders.db
│   │   └── products.db
│   ├── prompt_template.txt      # Optional custom prompt
│   └── README.md               # Auto-generated instructions
├── mydataset/                   # User-created Tier 2 dataset
│   ├── questions.jsonl
│   ├── databases/
│   │   └── mydata.db
│   └── README.md
└── ...
```

#### **Tier 3: Advanced Features**
```
datasets/                         # Advanced datasets with full features
├── wikisql/                     # Tier 3 curated dataset
│   ├── questions.jsonl          # Standard format questions
│   ├── wikisql_gold.db         # SQLite questions table with metadata
│   ├── databases/              # Source databases
│   │   └── wikisql_tables.db
│   ├── prompt_template.txt     # Custom WikiSQL prompt
│   ├── views.sql              # Predefined evaluation views
│   └── LICENSE
├── spider1/                     # Tier 3 curated dataset
│   ├── questions.jsonl
│   ├── spider1_gold.db         # Rich metadata and tags
│   ├── databases/              # 20 domain databases
│   │   ├── concert_singer.db
│   │   ├── car_1.db
│   │   └── ... (18 more)
│   ├── prompt_template.txt
│   ├── views.sql
│   └── LICENSE
└── bird/                        # Tier 3 curated dataset
    ├── questions.jsonl
    ├── bird_gold.db
    ├── databases/               # 11 domain databases
    ├── prompt_template.txt
    ├── views.sql
    └── LICENSE
```

### 4.3 Question File Format (Universal)

All tiers use the same question format for consistency:

#### **Single Database Mode**
```jsonl
{"question": "How many users are active?", "sql": "SELECT COUNT(*) FROM users WHERE active = 1", "table": "users"}
{"question": "Top selling products?", "sql": "SELECT name, sales FROM products ORDER BY sales DESC LIMIT 10", "table": "products"}
```

#### **Multi-Database Mode**
```jsonl
{"question": "Concert attendance?", "sql": "SELECT COUNT(*) FROM attendees", "db": "concert.db", "table": "attendees"}
{"question": "Car sales by year?", "sql": "SELECT year, COUNT(*) FROM sales GROUP BY year", "db": "automotive.db", "table": "sales"}
```

### 4.4 Auto-Detection Logic

The evaluation system automatically detects the appropriate mode:

1. **CLI with explicit flags**: `--questions` + `--db` → Tier 1 (direct file mode)
2. **CLI with dataset name**: `mydataset` → Tier 2/3 (infers `datasets/mydataset/`)
3. **Question format detection**: Single vs multi-database based on presence of `"db"` field
4. **Database path detection**: File vs directory determines connection logic

---

## 5. Database Schema Standards

### 5.1 Gold Database Schema

Every `{dataset}_gold.db` contains:

```sql
-- Core evaluation data
CREATE TABLE questions (
    item_id TEXT PRIMARY KEY,
    target_db TEXT NOT NULL,          -- Filename in databases/ subdirectory
    question TEXT NOT NULL,
    gold_sql TEXT NOT NULL,
    tags JSON,                        -- Auto-generated: {"sql": ["join"], "complexity": ["multi_table"], "difficulty": "hard"}
    dataset_metadata JSON            -- Dataset-specific fields
);

-- Predefined evaluation views (always include v_questions_default)
CREATE VIEW v_questions_default AS
  SELECT * FROM questions LIMIT 500;  -- Example - actual logic varies per dataset

-- Example auto-generated tag-based views
CREATE VIEW v_questions_joins AS
  SELECT * FROM questions WHERE json_extract(tags, '$.sql') LIKE '%"join"%';

CREATE VIEW v_questions_aggregation AS
  SELECT * FROM questions WHERE json_extract(tags, '$.sql') LIKE '%"aggregation"%';

CREATE VIEW v_questions_single_table AS
  SELECT * FROM questions WHERE json_extract(tags, '$.complexity') LIKE '%"single_table"%';

CREATE VIEW v_questions_hard AS
  SELECT * FROM questions WHERE json_extract(tags, '$.difficulty') = 'hard';

-- Provenance and versioning
CREATE TABLE __bench_meta__ (
    dataset_id TEXT,
    dataset_version TEXT,
    builder_semver TEXT,
    upstream_sha TEXT,
    created_at_utc TEXT,
    sqlite_version TEXT,
    python_version TEXT,
    row_counts_json TEXT
);
```

### 5.2 Auto-Generated Tags System

**SQL Analysis Module**: Uniform tag generation across all datasets via `datasets/shared/sql_analyzer.py`:

```python
def generate_tags(gold_sql: str, difficulty: str = None) -> Dict:
    """Generate standardized tags from SQL analysis"""
    tags = {
        "sql": _detect_sql_features(gold_sql),        # ["join", "aggregation", "subquery"]
        "complexity": _detect_complexity(gold_sql),   # ["single_table", "multi_table"]
    }
    if difficulty:
        tags["difficulty"] = difficulty              # Original dataset difficulty preserved
    return tags
```

**Build Process**: Dataset builders create complete databases with auto-generated tags:
1. Populate full `questions` table with all available examples
2. Generate tags for each question using shared SQL analyzer (preserving original difficulty)
3. Apply predefined views from `datasets/{name}/views.sql` based on dataset-specific characteristics
4. Always include `v_questions_default` as the canonical evaluation set

### 5.3 Views-Based Subsetting System

**Evaluation Process**:
```bash
# Use default view (canonical evaluation set)
python eval.py --dataset wikisql

# Use specific view for targeted evaluation
python eval.py --dataset wikisql --view v_questions_joins
python eval.py --dataset bird_mini_dev --view v_questions_financial_db
```

**View Examples by Use Case**:
* **Difficulty**: `v_questions_easy`, `v_questions_hard` (using original dataset difficulty values)
* **SQL Features**: `v_questions_joins`, `v_questions_aggregation`, `v_questions_subquery`
* **Complexity**: `v_questions_single_table`, `v_questions_multi_table`
* **Database-Specific**: `v_questions_financial_db`, `v_questions_concert_singer_db` (target specific source databases)
* **Combined**: `v_questions_hard_joins`, `v_questions_single_table_aggregation`
* **Size**: `v_questions_tiny` (10 examples), `v_questions_small` (50 examples)

### 5.4 Schema Scope (Dynamic)

Schema scope is determined dynamically by parsing `gold_sql` to identify referenced tables and columns. Tools (`list_tables`, `describe_table`) respect this scope by default, showing only relevant schema elements to the model.

### 5.5 Source Database Standards

Databases in `databases/` subdirectory:
* Must be SQLite format with `.db` extension
* Opened read-only during evaluation
* Contain actual data tables that tools query against
* Include `__bench_meta__` table for provenance

---

## 6. Evaluation Pipeline

### 6.1 Complete Dataset Building with View-Based Subsetting

Each dataset build script creates complete datasets with predefined evaluation views:

* **WikiSQL**: ~80K examples (complete) → `v_questions_default` (500 hardest)
* **Spider1**: ~1K examples (full dev set) → `v_questions_default` (all dev)
* **BIRD mini_dev**: 500 examples (complete) → `v_questions_default` (all 500)
* **Spider2-lite**: 24 examples (all with gold SQL) → `v_questions_default` (all 24)
* **BIRD LiveSQLBench**: 270 examples (complete) → `v_questions_default` (all 270)

**Flexible Evaluation**: Users specify views instead of hardcoded splits:
```bash
# Default canonical sets
python eval.py --dataset wikisql  # Uses v_questions_default (500 hardest)

# Targeted evaluation via views
python eval.py --dataset wikisql --view v_questions_easy        # Easy examples only
python eval.py --dataset wikisql --view v_questions_joins       # Join queries only
python eval.py --dataset wikisql --view v_questions_tiny        # 10 examples for testing

# Still support --limit for ad-hoc testing
python eval.py --dataset wikisql --view v_questions_joins --limit 5
```

### 6.2 Backend Auto-Detection

**MVP Status**: Backend auto-detection fully implemented with endpoint availability checking.

```python
BACKENDS = {
    "lm_studio": {
        "base_url": "http://localhost:1234",
        "provider": "openai",
        "api_key": "lm-studio",  # Pre-filled dummy key
        "default_params": {"temperature": 0, "max_tokens": 1000}
    },
    "ollama": {
        "base_url": "http://localhost:11434",
        "provider": "ollama",
        "api_key": "ollama",  # Pre-filled dummy key
        "default_params": {"temperature": 0, "max_tokens": 1000}
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "provider": "openai",
        "api_key": None,  # Requires OPENROUTER_API_KEY env var
        "default_params": {"temperature": 0, "max_tokens": 1000}
    }
}
```

**Auto-detection order**: LM Studio → Ollama → OpenRouter (local first, then remote)

**CLI parameter overrides**: Users can override default_params via command line.

---

## 7. Tool Interface Specification

**MVP Status**: Core tool functions fully implemented and tested.


### 7.1 Core Tools (Dual-Mode Implementation)

**Implementation Philosophy**: Tools return string data in SQLite CLI format for consistency across tool calling and prompt modes. OpenAI function definitions provide schema for tool-calling capable models.

```python
def describe_database(table_name: Optional[str] = None) -> str:
    """Get database schema information in SQLite CLI format.

    Dual-mode tool that works for both function calling and direct execution.
    Returns pipe-separated values matching native SQLite PRAGMA output.

    Args:
        table_name: Optional table name to describe, or None for all tables

    Returns:
        Schema information as pipe-separated text (SQLite CLI format)

    OpenAI Function Definition:
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
                            "description": "Optional table name to describe"
                        }
                    }
                }
            }
        }
    """

def execute_sql(query: str) -> str:
    """Execute SELECT query and return results in SQLite CLI format.

    Dual-mode tool that works for both function calling and direct execution.
    Uses same function for model tool calls and evaluation comparison.

    Args:
        query: SQL SELECT statement (read-only, 3 second timeout)

    Returns:
        Query results as pipe-separated text with headers (SQLite CLI format)

    OpenAI Function Definition:
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
    """
```

### 7.2 Tool Behavior

**Dual-mode operation**: Tools work in both function calling mode (for tool-capable models) and prompt fallback mode (for text-only models).

**String-based returns**: All tools return string data in SQLite CLI format for consistency. Tool calling models receive these strings as function responses.

**Database targeting**: Tools automatically use the database from current evaluation context. Models don't specify database paths explicitly.

**Safety constraints**: Read-only SQLite connections with query_only pragma. Only SELECT statements allowed with 3-second timeout.

**Evaluation consistency**: Same `execute_sql()` function used for both model tool calls and gold SQL comparison, ensuring identical execution environment.

---

## 8. Runtime & Safety Constraints

**MVP Status**: All safety constraints implemented and enforced.

* **SQLite engine:** Python stdlib `sqlite3` only (no extension loading). DBs opened `mode=ro`.
* **Statement gate:** Only `SELECT` allowed. No CTEs with side effects, no PRAGMAs, no ATTACH/DETACH, no triggers, no writes.
* **Row cap:** Default `LIMIT 1000` applied if absent (configurable per query).
* **Timeout:** Default 10s per execution (configurable per query).
* **Determinism:** Serial execution; `concurrency=1` always.
* **JSON support:** Uses SQLite's built-in JSON functions (available since SQLite 3.8.0).

---

## 9. Prompting & Tooling

### 9.1 Tool-First Policy

* **Default mode**: Use function calling when supported. Available tools: `describe_database()`, `execute_sql()`.
* **Tool-capable models** (Qwen, Llama 3.1+, GPT, Mistral) use OpenAI-compatible function calling via LiteLLM.
* **Automatic detection**: Model name patterns determine tool calling capability, fallback to prompt mode otherwise.
* **Consistent execution**: Same tool functions used in both modes, returning SQLite CLI format strings.

### 9.2 Prompt-Only Fallback

* **Conditions**: Model doesn't support function calling (detected by model name patterns).
* **Fallback behavior**: Rich prompt with embedded schema information; extract SQL from text responses.
* **Schema injection**: Full database schema automatically injected into system prompt using `describe_database()` output.
* **Same safety**: Extracted SQL executed using identical `execute_sql()` function with same read-only constraints.

---

### 9.3 Model Response Parser Architecture

**MVP Status**: Parser architecture implemented with base parser and model family detection for gpt-oss and qwen families.


#### 9.3.1 Goal

Parse SQL responses from different model families reliably, while maintaining consistent prompt content across all models.

**Core Principle**: All models receive identical prompt content. Backends (LM Studio, Ollama, OpenRouter) handle input formatting automatically. Our extractors handle output parsing only.

#### 9.3.2 Responsibility Separation

**Backend Layer** (LM Studio/Ollama/OpenRouter):
- Convert standard OpenAI chat format to model-specific templates
- Handle role formatting (system/user/assistant)
- Manage tool calling structure and parameter mapping
- Apply model-specific prompt templates automatically

**LiteLLM Layer**:
- Unified API across all backends
- Automatic parameter mapping and authentication
- Response format normalization
- Backend-specific endpoint management

**Response Parser Layer** (`extractors/{family}.py`):
- Parse model responses to extract clean SQL
- Handle model-specific response formatting quirks
- Extract SQL from various formats (markdown, tool calls, plain text)
- Manage error handling and retry patterns
- **Do not modify input prompts** - only parse output responses

#### 9.3.3 Input/Output Boundary

**Input Handling (Automatic)**:
- Prompt templating handled by backends
- Tool definition formatting handled by backends
- Role and message structure conversion handled by backends

**Output Handling (Our Responsibility)**:
- SQL extraction from markdown code blocks (```sql, ```SQL, plain text)
- Tool calling response parsing
- Multi-statement SQL handling
- Response cleaning and validation
- Model-specific failure mode detection

**Test Principle**: All models get identical information content. Measure SQL reasoning ability, not prompt engineering effectiveness.

#### 9.3.4 Extractor Grouping

Group by response parsing patterns, not model vendors:
- Same extractor for models with similar response formats
- Split extractors when parsing logic becomes incompatible
- Model name → extractor mapping via family detection
- Version handling within extractor when response formats change

#### 9.3.5 Backend Integration Strategy

**Generic Prompt Template**: Single template works across all models since backends handle conversion
**LiteLLM Integration**: Abstracts backend differences for API calls
**Response Parsing**: Family-specific extractors handle output variety
**Error Handling**: Extractor-specific retry and fallback logic

---

## 10. CLI Design

**MVP Status**: Basic CLI implemented with direct file mode and simple dataset mode.


### 10.1 CLI Interface (Current MVP)

**Implemented Commands**:
```bash
# Direct file mode (Tier 1)
python eval.py --questions questions.jsonl --db database.db --model MODEL

# Basic dataset mode (Tier 2)
python eval.py hello_world --model MODEL

# Options
--verbose, -v     # Enable debugging output
--workflow        # Use multi-step tool calling
```

### 10.2 Future Three-Tier CLI Interface


The CLI supports three tiers of complexity with automatic detection and inference:

#### **Tier 1: Instant Setup (Direct File Mode)**
```bash
# Single database mode
python eval.py --questions questions.jsonl --db mydata.db

# Multi-database mode
python eval.py --questions questions.jsonl --db databases/

# With model specification
python eval.py --questions questions.jsonl --db mydata.db --model "llama3:8b"
```

#### **Tier 2 & 3: Dataset Mode (Organized)**
```bash
# Basic dataset evaluation (CLI infers datasets/ directory)
python eval.py hello-world
python eval.py mydataset
python eval.py wikisql

# Tier 3 advanced features (views, limits, targeting)
python eval.py wikisql --view v_questions_joins
python eval.py bird --view v_questions_financial_db --limit 50
python eval.py spider1 --view v_questions_hard

# Backend and model specification
python eval.py wikisql --model "gpt-4" --backend openrouter
python eval.py hello-world --model "llama3:8b" --backend ollama
```

#### **CLI Auto-Detection Logic**
1. **Explicit flags**: `--questions` + `--db` → Tier 1 (direct file mode)
2. **Dataset name**: `mydataset` → Infers `datasets/mydataset/` (Tier 2/3)
3. **Question format**: Auto-detects single vs multi-database from JSONL content
4. **Feature availability**: Views and advanced options only available for Tier 3 datasets

### 10.3 Dataset Creation and Management (Future)

#### **Interactive Dataset Creation**
```bash
# Create new dataset with guided prompts
python create_dataset.py

# Non-interactive dataset creation
python create_dataset.py --name mydataset --type single-db --prompt default

# List available datasets
python eval.py --list

# Show dataset information
python eval.py mydataset --info
```

#### **Dataset Upgrade System**
```bash
# Upgrade Tier 2 to Tier 3 (adds SQLite tables, tags, views)
python build_dataset.py --input datasets/mydataset/

# Upgrade with custom options
python build_dataset.py --input datasets/mydataset/ --generate-views --add-tags
```

#### **Build Process Overview**
1. **Raw Data Processing**: Convert upstream datasets to standard JSONL format
2. **Dataset Creation**: Use `create_dataset.py` to build Tier 2 structure
3. **Advanced Upgrade**: Use `build_dataset.py` to add Tier 3 features (tags, views, metadata)
4. **Validation**: Automatic testing of dataset integrity and evaluation pipeline
4. Validation ensures `v_questions_default` exists

---

## 11. Metrics & Evaluation

### 11.1 Primary Metrics

* **Execution Accuracy (EX@1)**: Whether model SQL returns same results as gold SQL.
  - **Comparison**: Order-insensitive set comparison (unless both have ORDER BY)
  - **Type-aware**: Numeric tolerance 1e-6, NULL-safe equality
  - **Implementation**: Execute both queries, compare result sets

* **Exact Match (EM)**: Whether model SQL exactly matches gold SQL after normalization.
  - **Normalization**: Whitespace, case, and keyword standardization
  - **Purpose**: Secondary metric for SQL structure analysis

### 11.2 Secondary Metrics

* **Non-error rate**: Fraction of attempts that parse and execute without exceptions
* **Latency**: Prompt→first token; total generation time
* **Feature-stratified EX**: Breakdown by SQL features from `tags` field
* **Error taxonomy**: Parse errors, blocked statements, timeouts, execution errors

### 11.3 Output Format

* **JSONL logs**: Per-item attempts with raw responses, extracted SQL, results, timings
* **Summary metrics**: Aggregated results with stratified breakdowns
* **Human-readable reports**: Markdown/text summaries for quick analysis

---

## 12. Error Handling & Safety

### 12.1 SQL Safety

* **Read-only connections**: `mode=ro` prevents any data modification
* **Statement validation**: Strict parser allowing only SELECT with safe functions
* **Resource limits**: Enforced LIMIT and timeout guards on all queries
* **No extensions**: No PRAGMA, ATTACH, or extension loading allowed

### 12.2 Evaluation Robustness

* **Parse errors**: Extract first valid SELECT from model response; log parse failures
* **Execution errors**: Capture SQL errors without stopping evaluation; report error types
* **Backend failures**: Surface connection/API errors clearly; support backend switching
* **Timeout handling**: Single retry with reduced LIMIT if query times out

---

## 13. Extensibility

### 13.1 Adding Datasets

1. Create dataset builder script in `data/{dataset}/build.py`
2. Implement conversion to standard database schema
3. Generate `{dataset}_gold.db` with questions table
4. Populate `databases/` subdirectory with source data
5. Create `datasets/{dataset}/prompt_builder.py` for dataset-specific prompting logic
6. Add dataset to evaluation registry

### 13.2 Adding Model Families

1. Determine if new model fits existing response parser (group by response format, not vendor)
2. If new parsing needed, create `model_adapters/{family}.py` with ResponseParser interface
3. Add model name patterns to adapter factory function
4. Test with dataset prompt builders to ensure optimal formatting
5. Validate prompt content boundary compliance (data format vs SQL reasoning)

### 13.3 Adding Backends

1. Add backend configuration to BACKENDS dictionary
2. Test LiteLLM compatibility and tool support
3. Validate auto-detection and parameter handling
4. Add backend-specific documentation

---

## 14. Versioning & Reproducibility

### 14.1 Dataset Versioning

* **Builder versioning**: Each dataset builder declares semantic version
* **Source pinning**: Builders pin exact upstream commits/tags/downloads
* **Provenance tracking**: `__bench_meta__` table records build environment and sources

### 14.2 Evaluation Reproducibility

* **Deterministic evaluation**: Serial execution with fixed parameters
* **Environment logging**: Python/SQLite versions, backend configurations recorded
* **Result verification**: Checksums and row counts for data integrity validation

---

## 15. Implementation Plan

**MVP Checkpoint (Current Status)**:
✅ Core evaluation engine with tool calling support
✅ Backend auto-detection (LM Studio → Ollama → OpenRouter)
✅ Response parser architecture with model family detection
✅ Direct file mode evaluation
✅ Basic dataset support (hello_world)
✅ Comprehensive test suite
✅ Read-only SQL execution with safety constraints

**Remaining Implementation**:


### Phase 1: Three-Tier Architecture Foundation

#### 15.1 Tier 1: Direct File Evaluation (Zero-Config)
- [ ] Implement CLI flags: `--questions` and `--db` for direct file mode
- [ ] Auto-detect single vs multi-database mode from question format
- [ ] Create default prompt template for universal compatibility
- [ ] Build basic evaluation pipeline: load questions → connect DB → evaluate
- [ ] Support JSONL/CSV question file parsing
- [ ] Implement simple database targeting logic (file vs directory)

#### 15.2 Tier 2: Dataset Templates and Organization
- [ ] Create `create_dataset.py` with interactive prompts
- [ ] Build template generation: questions.jsonl, databases/, README.md
- [ ] Implement CLI dataset inference: `mydataset` → `datasets/mydataset/`
- [ ] Add custom prompt template support via `prompt_template.txt`
- [ ] Create hello-world dataset (Tier 2 example):
  - Synthetic data (customers, orders, products tables)
  - 10 examples covering 5 SQL features (2 examples each)
  - Educational README and simple structure
- [ ] Implement dataset listing and info commands

#### 15.3 Tier 3: Advanced Features and Metadata
- [ ] Create `build_dataset.py` utility for Tier 2 → Tier 3 upgrades
- [ ] Implement shared SQL analyzer for auto-generated tags
- [ ] Build SQLite questions table creation with metadata
- [ ] Add view generation system (tag-based, feature-based)
- [ ] Create unified upgrade process for all dataset types
- [ ] Add provenance tracking in __bench_meta__ tables

#### 15.4 Backend Auto-Detection System
- [ ] Implement BACKENDS configuration dictionary
- [ ] Create backend auto-detection with local-first ordering
- [ ] Add CLI parameter override support
- [ ] Test LM Studio, Ollama, OpenRouter integration

#### 15.5 Tool Interface Implementation
- [ ] Implement standardized tool signatures
- [ ] Add automatic database targeting (simplified - questions specify table/db)
- [ ] Remove complex schema scope filtering (show full schema)
- [ ] Build SQL safety validation

### Phase 2: Dataset Integration (Tier 3 Conversions)

#### 15.6 WikiSQL Complete Dataset Building (High Priority)
- [ ] Convert WikiSQL raw data to standard questions.jsonl format
- [ ] Use build_dataset.py to create Tier 3 dataset with full features
- [ ] Create tag-based views: joins, aggregation, complexity levels
- [ ] Ensure v_questions_default selects canonical 500 examples
- [ ] Preserve existing WikiSQL difficulty classification in tags
- [ ] Validate metrics match existing 500-example implementation

#### 15.7 Spider1 Complete Dataset Integration (Ready for Implementation)
- [ ] Convert Spider1 raw data to standard questions.jsonl format
- [ ] Use build_dataset.py to create Tier 3 dataset
- [ ] Preserve Spider1 original difficulty values (Easy/Medium/Hard/Extra Hard) in tags
- [ ] Create multi-database views and domain-specific views
- [ ] Copy 20 domain databases to databases/ subdirectory
- [ ] Test multi-database evaluation across all domains

#### 15.8 BIRD mini_dev Complete Integration (High Quality)
- [ ] Convert BIRD raw data to standard questions.jsonl format (with evidence fields)
- [ ] Use build_dataset.py to create Tier 3 dataset
- [ ] Preserve BIRD original difficulty values (Simple/Moderate/Challenging) in tags
- [ ] Create database-specific views for 11 domain databases
- [ ] Integrate evidence field into prompt templates
- [ ] Test view-based evaluation with large databases (up to 570MB)

#### 15.9 Spider2-lite Complete Integration (Limited by Gold SQL Availability)
- [ ] Convert Spider2-lite data (24 high-quality instances) to standard format
- [ ] Use build_dataset.py to create Tier 3 dataset
- [ ] Create minimal views.sql due to small dataset size
- [ ] Copy required subset of 30+ databases
- [ ] Embed external knowledge in metadata JSON field

### Phase 3: Unified Evaluation Engine

#### 15.10 Core Evaluation Script
- [ ] Implement three-tier evaluation logic in eval.py
- [ ] Add automatic tier detection and feature availability
- [ ] Build unified evaluation loop supporting all tiers
- [ ] Add rich TUI progress reporting

#### 15.11 Simplified Database Handling
- [ ] Remove complex database targeting - questions specify database directly
- [ ] Implement simple connection logic: file vs directory detection
- [ ] Remove schema scope filtering - show full schema always
- [ ] Add basic connection pooling for performance

#### 15.12 Prompt System Integration
- [ ] Load default prompt or custom prompt_template.txt
- [ ] Remove dataset-specific prompt builders (use templates instead)
- [ ] Maintain compatibility with existing model adapters
- [ ] Support prompt overrides only for complex datasets (Spider, BIRD)

### Phase 4: User Experience and Tooling

#### 15.13 CLI Interface Design
- [ ] Implement three-tier CLI with auto-detection
- [ ] Add dataset creation and management commands
- [ ] Progress reporting with rich TUI enhancements
- [ ] Clear error messaging and debugging support

#### 15.14 Dataset Management System
- [ ] Interactive dataset creation workflow
- [ ] Dataset upgrade system (Tier 2 → Tier 3)
- [ ] Validation and testing of dataset integrity
- [ ] Template system for consistent dataset structure

#### 15.15 Output and Logging
- [ ] **JSONL Logs**: Streaming output during evaluation with detailed per-item logs and raw responses
- [ ] **HTML Reports**: Generated from JSONL at completion with rich templated output and full prompt/response pairs
- [ ] **Template System**: Pure HTML generation with filtering/summary capabilities, no web framework needed
- [ ] **Summary Metrics**: EX/EM rates with feature stratification embedded in HTML
- [ ] **Error Categorization**: Parse, execution, timeout, and blocked statement tracking
- [ ] **Future SQLite Results**: Database schema design for cross-run analysis and SQL agent querying (Phase 5+)

### Phase 5: Testing and Validation

#### 15.16 Three-Tier Testing
- [ ] Test Tier 1: Direct file evaluation with various question formats
- [ ] Test Tier 2: Dataset template creation and organization
- [ ] Test Tier 3: Advanced features and upgrade processes
- [ ] Validate consistent behavior across all tiers

#### 15.17 Dataset Integration Testing
- [ ] Test WikiSQL, Spider1, BIRD conversions and evaluations
- [ ] Validate cross-database and multi-database scenarios
- [ ] Test large database performance (BIRD's 570MB databases)
- [ ] Verify upgrade processes work correctly

#### 15.18 Backend Integration Testing
- [ ] Test LM Studio integration with tool calling
- [ ] Validate Ollama compatibility and performance
- [ ] Test OpenRouter integration with API key handling
- [ ] Verify auto-detection fallback chain

#### 15.19 Error Handling and Edge Cases
- [ ] Test SQL parsing and extraction robustness
- [ ] Validate timeout and resource limit enforcement
- [ ] Test malformed query handling and recovery
- [ ] Verify safety constraint enforcement across all tiers
- [ ] Verify backend failure handling and switching

---

## 16. Technical Implementation Details

### 16.1 SQL Analyzer Module

**Location**: `datasets/shared/sql_analyzer.py`

```python
import re
import json
from typing import Dict, List

def generate_tags(gold_sql: str, difficulty: str = None) -> Dict:
    """Generate standardized tags from SQL analysis"""
    tags = {
        "sql": _detect_sql_features(gold_sql),
        "complexity": _detect_complexity(gold_sql)
    }
    if difficulty:
        tags["difficulty"] = difficulty
    return tags

def _detect_sql_features(sql: str) -> List[str]:
    """Detect basic SQL features"""
    sql_upper = sql.upper()
    features = []

    if "JOIN" in sql_upper:
        features.append("join")
    if any(agg in sql_upper for agg in ["COUNT(", "SUM(", "AVG(", "MAX(", "MIN("]):
        features.append("aggregation")
    if "GROUP BY" in sql_upper:
        features.append("group_by")
    if "ORDER BY" in sql_upper:
        features.append("order_by")
    if "(" in sql_upper and "SELECT" in sql_upper[sql_upper.find("("):]:
        features.append("subquery")

    return features

def _detect_complexity(sql: str) -> List[str]:
    """Detect basic complexity patterns"""
    sql_upper = sql.upper()
    complexity = []

    # Simple table count
    table_indicators = sql_upper.count("FROM") + sql_upper.count("JOIN")
    if table_indicators <= 1:
        complexity.append("single_table")
    else:
        complexity.append("multi_table")

    return complexity


```

**Usage in Build Scripts**:
```python
from datasets.shared.sql_analyzer import generate_tags

tags = generate_tags(question['gold_sql'], question.get('difficulty'))
# Returns: {"sql": ["aggregation"], "complexity": ["single_table"], "difficulty": "hard"}
```

### 16.2 Multi-Database Context Management

```python
def get_database_context(item_id: str, dataset: str) -> Dict[str, Any]:
    """Get database context for evaluation item"""
    gold_db = f"datasets/{dataset}/{dataset}_gold.db"
    conn = sqlite3.connect(gold_db)

    item = conn.execute(
        "SELECT target_db, question, gold_sql, metadata FROM questions WHERE item_id = ?",
        (item_id,)
    ).fetchone()

    return {
        "target_db_path": f"datasets/{dataset}/databases/{item['target_db']}",
        "question": item["question"],
        "gold_sql": item["gold_sql"],
        "schema_scope": extract_schema_scope(item["gold_sql"]),
        "metadata": json.loads(item["metadata"] or "{}")
    }
```

### 16.3 Schema Scope Detection

```python
def extract_schema_scope(gold_sql: str) -> Dict[str, List[str]]:
    """Extract referenced tables and columns from gold SQL"""
    # Parse SQL to identify table references
    # Extract column references from SELECT and WHERE clauses
    # Return minimal schema scope for tool filtering
    pass
```

### 16.4 Tool Interface with Auto-Targeting

```python
def execute_sql_tool(query: str, context: Dict, limit: int = 1000) -> Dict[str, Any]:
    """Execute SQL against correct database automatically"""
    db_path = context["target_db_path"]
    conn = sqlite3.connect(db_path, uri=True)

    try:
        # Validate query safety
        if not is_safe_query(query):
            return {"success": False, "error": "Unsafe query blocked"}

        # Execute with timeout and limits
        result = execute_with_limits(conn, query, limit, timeout=10)
        return {"success": True, **result}

    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()
```

---

## 17. Dataset-Specific Implementation Notes

### 17.1 WikiSQL Implementation
- **Architecture**: Complete dataset (~80K) in gold.db, data in databases/wikisql_tables.db
- **Views Strategy**: Default view selects canonical 500 examples; additional views for features/subsets
- **Tool Use**: Simple single-database targeting
- **Performance**: Full dataset enables flexible evaluation; default view maintains speed
- **Migration**: Expand from 500 to complete dataset with view-based canonical subset

### 17.2 Spider1 Implementation
- **Architecture**: Complete dev set (~1K) in gold.db, 20 domain databases in databases/
- **Views Strategy**: Default view includes all examples; database-specific views enable targeted evaluation
- **Scale**: ~1000 examples across all domains with flexible database/difficulty subsetting
- **Tool Use**: Context-aware database targeting per question
- **Advantage**: Complete gold SQL coverage + database-specific evaluation capabilities

### 17.3 BIRD mini_dev Implementation
- **Architecture**: Complete dataset (500) in gold.db, 11 domain databases in databases/
- **Views Strategy**: Default view includes all examples; database-specific views for targeted evaluation
- **Scale**: 500 examples with evidence field integration and database subsetting
- **Tool Use**: Context-aware targeting with large database optimization
- **Features**: Evidence field in metadata JSON, database-specific views, handles databases up to 570MB

### 17.4 Spider2-lite Implementation
- **Architecture**: Complete available dataset (24) in gold.db, subset of 30+ databases as needed
- **Views Strategy**: Minimal views due to small dataset size; default view includes all examples
- **Scale**: 24 high-quality examples (all available with gold SQL)
- **Tool Use**: Context-aware targeting with external knowledge injection
- **Focus**: Quality over quantity due to limited gold SQL availability

---

## 18. Success Criteria

### 18.1 Functional Requirements
- [ ] **Unified Evaluation**: Single script works across all dataset architectures
- [ ] **Database-Only Metadata**: No external JSONL or CSV file dependencies
- [ ] **Multi-Database Support**: Seamless handling of both single and multi-database datasets
- [ ] **Backend Auto-Detection**: Local backends tried before remote with fallback
- [ ] **Schema Scope Filtering**: Dynamic schema filtering based on gold SQL analysis
- [ ] **Tool Interface Consistency**: Same tool signatures work across all datasets

### 18.2 Performance Requirements
- [ ] **WikiSQL**: Maintain existing evaluation speed and accuracy
- [ ] **Spider1**: Handle 1000+ examples with 20-database switching efficiently
- [ ] **BIRD**: Handle large databases (570MB) without performance degradation
- [ ] **Spider2-lite**: Process 24 complex enterprise queries reliably

### 18.3 Integration Requirements
- [ ] **CLI Simplicity**: Single command interface with parameter overrides
- [ ] **Build System**: Clean separation of build scripts from evaluation
- [ ] **Error Handling**: Robust handling of SQL errors, timeouts, and backend failures
- [ ] **Logging**: Detailed JSONL output for analysis and debugging
- [ ] **Extensibility**: Clear patterns for adding new datasets and backends

---

## 19. Risk Mitigation

### 19.1 Technical Complexity Risks
- **Multi-Database Architecture**: Start with WikiSQL single-database, then expand
- **Schema Scope Detection**: Begin with simple parsing, enhance iteratively
- **Backend Integration**: Test each backend individually before auto-detection
- **Performance**: Profile large database operations early

### 19.2 Dataset Integration Risks
- **WikiSQL Migration**: Validate metrics match existing implementation exactly
- **Spider1 Scale**: Test database switching performance with subset first
- **BIRD Complexity**: Start with mini_dev before attempting LiveSQLBench
- **External Dependencies**: Eliminate CSV/JSONL dependencies systematically

### 19.3 User Experience Risks
- **CLI Complexity**: Keep interface simple, add features incrementally
- **Error Messages**: Provide clear debugging information for common failures
- **Backend Detection**: Ensure fallback chain works reliably across environments
- **Documentation**: Maintain clear setup and usage instructions

---

## 20. Current MVP Implementation Status

### 20.1 MVP Capabilities

**Core Evaluation Engine**:
- ✅ Tool calling interface with `describe_database()` and `execute_sql()`
- ✅ Fallback prompt mode for non-tool-calling models
- ✅ Read-only SQL execution with 30-second timeouts
- ✅ SQLite CLI format output for consistency

**Backend Integration**:
- ✅ Auto-detection: LM Studio → Ollama → OpenRouter
- ✅ Uniform parameters across all backends
- ✅ Environment variable overrides for backend-specific settings
- ✅ LiteLLM integration with proper provider routing

**Response Parsing**:
- ✅ Model family-based parser architecture
- ✅ Tool calling and text extraction methods
- ✅ Support for markdown code blocks and plain text SQL
- ✅ Parser registry with gpt-oss and qwen family detection

**CLI Interface**:
- ✅ Direct file mode: `--questions file.jsonl --db path.db --model MODEL`
- ✅ Dataset mode: `hello_world --model MODEL`
- ✅ Verbose debugging and workflow options

**Testing**:
- ✅ Comprehensive test suite with pytest
- ✅ Tool function testing, CLI testing, backend testing
- ✅ Response parser testing and prompt testing

### 20.2 Supported Datasets

**Currently Available**:
* **hello_world**: 13 basic examples for testing and validation
* **wikisql**: Partial implementation with metadata structure

**Planned Datasets**:
* **WikiSQL**: 500 curated examples, single-database architecture
* **Spider1**: ~1000 examples, multi-database architecture (20 domains)
* **BIRD mini_dev**: 500 examples, multi-database with external knowledge
* **Spider2-lite**: 24 high-quality examples, multi-database architecture
* **BIRD LiveSQLBench**: 270 examples, multi-database with external knowledge

### 20.3 Supported Backends

* **LM Studio**: Local OpenAI-compatible server
* **Ollama**: Local model serving
* **OpenRouter**: Remote frontier model access

---

### 20.4 Current Limitations

**Dataset Architecture**: Only basic dataset support implemented. No templating system, versioning, or build scripts.

**Multi-Database**: Current implementation focuses on single-database evaluation. Multi-database context management not implemented.

**Advanced Analysis**: Schema scope detection, auto-generated tags, and views-based subsetting not yet implemented.

**Dataset Management**: No interactive creation, upgrade system, or sophisticated metadata handling.

**Complex Workflows**: Basic evaluation only. No multi-step analysis, error recovery, or advanced debugging features.

## 21. Glossary

* **Gold database**: `{dataset}_gold.db` containing questions, gold SQL, and metadata
* **Target database**: Specific database file in `databases/` subdirectory for current question
* **Schema scope**: Minimal set of tables/columns exposed to model, derived from gold SQL
* **Tool-first**: Attempt tool calls before any prompt-only SQL generation
* **Backend auto-detection**: Try local backends (LM Studio, Ollama) before remote (OpenRouter)
* **Canonical evaluation set**: Single curated set of examples per dataset, no splits

---

## 22. Side Quest: Javascript Question Builder

### 22.1 Project Overview

**Goal**: Create a pure Javascript + HTML + CSS single file .html page that allows for easy generation of `questions.jsonl` files through a user-friendly interface.

**Purpose**: Simplify the process of creating custom datasets by providing a visual tool for writing questions and SQL statements, eliminating the need to manually format JSONL files and handle multi-line SQL complexities.

### 22.2 Core Features

#### **Question Management Interface**
- Add/edit/delete questions in a clean UI
- Multi-line SQL editor with syntax highlighting
- Auto-formatting and validation of SQL statements
- Real-time preview of generated JSONL output

#### **Database Integration**
- File picker UI for selecting .db files from local filesystem
- Automatic database schema inspection and display
- Table/column browser for reference while writing SQL
- Path handling for single vs multi-database modes

#### **SQL Validation and Testing**
- Client-side SQL syntax validation
- Optional SQL execution against selected database (via sql.js)
- Results preview to verify SQL correctness
- Error highlighting and helpful error messages

#### **Export and Integration**
- Generate properly formatted questions.jsonl file
- Download functionality for completed question sets
- Proper escaping of multi-line SQL and special characters
- Integration hooks for dataset builder scripts

### 22.3 Technical Implementation

#### **Single File Architecture**
```html
<!DOCTYPE html>
<html>
<head>
    <!-- CSS: Modern, clean interface with syntax highlighting -->
    <!-- SQL.js library for client-side SQLite execution -->
</head>
<body>
    <!-- Question builder interface -->
    <!-- Database browser panel -->
    <!-- SQL editor with validation -->
    <!-- Export controls -->

    <script>
        // Pure Javascript implementation
        // No external dependencies except sql.js
        // Local file handling and JSONL generation
    </script>
</body>
</html>
```

#### **User Workflow**
1. **Load Database**: Select .db file(s) via file picker
2. **Browse Schema**: Inspect tables and columns in sidebar
3. **Write Questions**: Add natural language questions with corresponding SQL
4. **Validate SQL**: Real-time syntax checking and optional execution
5. **Preview Output**: See generated JSONL format
6. **Export**: Download questions.jsonl file ready for evaluation

#### **Dataset Builder Integration**
```bash
# Can be invoked during dataset creation process
python create_dataset.py --interactive-questions
# Opens question builder tool in browser
# Saves questions.jsonl directly to dataset directory
```

### 22.4 Implementation Priorities

#### **Phase 1: Core Editor**
- [ ] HTML/CSS interface layout
- [ ] Question list management (add/edit/delete)
- [ ] Basic SQL text area with multi-line support
- [ ] JSONL generation and download

#### **Phase 2: Database Integration**
- [ ] File picker for .db selection
- [ ] sql.js integration for schema inspection
- [ ] Table/column browser sidebar
- [ ] Database path handling for question format

#### **Phase 3: Validation and Testing**
- [ ] SQL syntax highlighting and validation
- [ ] Optional SQL execution and results preview
- [ ] Error handling and user feedback
- [ ] Real-time JSONL preview

#### **Phase 4: Polish and Integration**
- [ ] Responsive design and accessibility
- [ ] Integration with dataset builder scripts
- [ ] Documentation and usage examples
- [ ] Testing across different browsers

### 22.5 Benefits

**Developer Experience**: Eliminates manual JSONL formatting and reduces errors in question creation

**Accessibility**: Non-technical users can contribute questions without understanding JSON syntax

**Validation**: Immediate feedback on SQL correctness prevents evaluation failures

**Integration**: Seamless workflow from question creation to dataset building

**Reusability**: Can be used across all dataset types and complexity tiers

---

## 23. Next Steps

1. Implement backend auto-detection system
2. Create unified tool interface with schema scope filtering
3. Align WikiSQL with new database standards
4. Integrate Spider1 multi-database architecture
5. Test end-to-end evaluation with multiple backends
6. Add BIRD mini_dev for evidence field testing
7. Polish CLI interface and error handling
