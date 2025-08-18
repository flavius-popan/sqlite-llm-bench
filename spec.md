# sqlite-llm-workbench (v0.3)

> **Primary Goal**: Systematically test any LLM's ability to understand natural language and generate working SQL queries, helping you identify exactly where models succeed and fail in real-world data tasks.

> **Secondary Goal**: Standardized benchmarking framework for comparing models with reproducible scores across industry-standard datasets.

**For developers building**: SQL agents, BI tools, data analysis workflows, or any system that needs reliable natural language → SQL conversion.

**For researchers studying**: LLM capabilities in structured reasoning, tool usage, and domain-specific tasks.

**For enthusiasts**: Easy model comparison tools that run on local hardware with common models.

---

## 1. Mission & Research Focus

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

### 2.3 Practical Developer Focus

**Principle**: Serve developers building real systems, not just researchers publishing papers.

* **Local-First**: Run on common hardware with local models (LM Studio, Ollama)
* **Single CLI**: One command to test everything or focus on specific capabilities
* **Actionable Results**: Clear identification of which SQL patterns work vs. fail
* **Production Relevance**: Test scenarios developers actually encounter

### 2.4 System Architecture Overview

Three integrated subsystems support both discovery and benchmarking:

1. **Build** – Convert industry datasets into SQLite DBs with rich metadata and capability-focused views
2. **Test** – Execute targeted evaluations using tools-first approach with prompt fallback
3. **Analyze** – Generate both detailed failure analysis and standardized benchmark scores

**Views-Based Testing**: Target specific capabilities without code complexity:

```sql
CREATE VIEW v_questions_joins_only AS
  SELECT * FROM questions WHERE json_extract(tags, '$') LIKE '%join%';

CREATE VIEW v_questions_aggregation AS
  SELECT * FROM questions WHERE json_extract(tags, '$') LIKE '%aggregation%';
```

**CLI Integration**: Test specific capabilities or run comprehensive benchmarks:
```bash
# Test specific SQL features
python eval.py --dataset wikisql --view v_questions_joins_only

# Full benchmark across all datasets
python eval.py --comprehensive --model "your-model"
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

## 4. Data Architecture

### 4.1 Directory Structure

```
data/                               # Raw source data (git clones, downloads)
├── spider1/                       # Raw Spider1 data
├── wikisql/                       # Raw WikiSQL data
└── bird_mini_dev/                 # Raw BIRD mini_dev data

datasets/                          # Built/processed datasets
├── spider1/
│   ├── spider1_gold.db           # Questions, gold SQL, metadata
│   ├── prompt_builder.py         # Dataset-specific prompting logic
│   ├── databases/                # Source databases for tool queries
│   │   ├── concert_singer.db
│   │   ├── car_1.db
│   │   └── ... (20 total)
│   └── LICENSE                   # Dataset license file
├── wikisql/
│   ├── wikisql_gold.db           # Questions, gold SQL, metadata
│   ├── prompt_builder.py         # Dataset-specific prompting logic
│   ├── databases/
│   │   └── wikisql_tables.db     # Actual data tables
│   └── LICENSE
└── ...

model_adapters/                    # Model-specific response parsing
├── __init__.py                    # Parser registry & factory
├── base.py                        # Abstract base classes
├── harmony.py                     # OpenAI Harmony format (gpt-oss)
├── anthropic.py                   # Claude-specific parsing
├── traditional.py                 # Standard OpenAI/LM Studio
└── utils.py                       # Shared SQL extraction patterns
```

### 4.2 Multi-Database Support

**Core principle**: Each dataset has a "gold" database containing questions/metadata and a `databases/` subdirectory containing source data for tool queries.

**Manifest fields** (stored in database, not separate files):
* `db_path`: Directory path containing the dataset (e.g., `"datasets/spider1/"`)
* `target_db`: Specific database filename within `databases/` subdirectory (e.g., `"concert_singer.db"`)

**Single vs Multi-database**:
* **WikiSQL**: Questions in `wikisql_gold.db`, data tables in `databases/wikisql_tables.db`
* **Spider1**: Questions in `spider1_gold.db`, 20 domain databases in `databases/`
* **BIRD**: Questions in `bird_mini_dev_gold.db`, 11 domain databases in `databases/`

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

### 7.1 Core Tools

```python
def list_tables() -> List[str]:
    """Returns table names in target_db, filtered by schema scope.

    Only shows tables referenced in the gold SQL for current question
    to prevent schema distraction and maintain focused context.
    """

def describe_table(table_name: str) -> Dict[str, Any]:
    """Returns column information for table, filtered by schema scope.

    Args:
        table_name: Must be one of the tables from list_tables()

    Returns:
        {
            "columns": [
                {"name": "id", "type": "INTEGER", "primary_key": True},
                {"name": "name", "type": "TEXT", "nullable": False}
            ],
            "foreign_keys": [...],
            "description": "Optional table description"
        }
    """

def execute_sql(query: str, limit: int = 1000, timeout: int = 10) -> Dict[str, Any]:
    """Executes query against target_db with safety limits.

    Args:
        query: SQL SELECT statement (other statements blocked)
        limit: Maximum rows returned (default 1000)
        timeout: Query timeout in seconds (default 10)

    Returns:
        {
            "success": True,
            "columns": ["col1", "col2"],
            "rows": [["val1", "val2"], ...],
            "row_count": 42,
            "execution_time": 0.123
        }

    Or on error:
        {
            "success": False,
            "error": "Error message",
            "error_type": "syntax|timeout|blocked"
        }
    """
```

### 7.2 Tool Behavior

**Database targeting**: Tools automatically use the `target_db` from current evaluation item. Models don't specify database explicitly.

**Schema filtering**: Tools show only tables/columns referenced in gold SQL by default. Future enhancement may add `--full-schema` evaluation option.

**Safety constraints**: Only SELECT statements allowed. PRAGMA, ATTACH, CTEs with side effects blocked.

---

## 8. Runtime & Safety Constraints

* **SQLite engine:** Python stdlib `sqlite3` only (no extension loading). DBs opened `mode=ro`.
* **Statement gate:** Only `SELECT` allowed. No CTEs with side effects, no PRAGMAs, no ATTACH/DETACH, no triggers, no writes.
* **Row cap:** Default `LIMIT 1000` applied if absent (configurable per query).
* **Timeout:** Default 10s per execution (configurable per query).
* **Determinism:** Serial execution; `concurrency=1` always.
* **JSON support:** Uses SQLite's built-in JSON functions (available since SQLite 3.8.0).

---

## 9. Prompting & Tooling

### 9.1 Tool-First Policy

* **Default mode**: Use tools. Available tools: `list_tables()`, `describe_table()`, `execute_sql()`.
* **Backends with OpenAI-style tool calling** (LM Studio/Ollama with compatible models) use tools directly.
* **Schema exposure**: Tools inject minimal schema scope (tables/columns from gold SQL only).

### 9.2 Prompt-Only Fallback

* **Conditions**: Backend doesn't support tools OR N consecutive tool failures.
* **Fallback behavior**: Request single SQLite `SELECT` statement as plain text; extract and execute under same safety constraints.
* **Schema injection**: Include schema scope summary in prompt when tools unavailable.

---

### 9.3 Model Adapter Architecture

#### 9.3.1 Goal

Evaluate each model's SQLite capabilities using optimal prompting for that model, without compromising evaluation validity.

**Core Principle**: All models receive the same information content, but formatted optimally for their architecture.

#### 9.3.2 Two-Layer Design

**Dataset Prompt Builders** (`datasets/{dataset}/prompt_builder.py`):
- Create information content: table schema, dataset-specific hints, task instructions
- Handle data format clarifications (WikiSQL comma-formatted TEXT columns)

**Model Response Adapters** (`model_adapters/{family}.py`):
- Format content into optimal message structure for each model family (roles, message order)
- Handle model-specific response parsing and SQL extraction
- Manage tool calling mechanics (OpenAI standard vs Harmony vs prompt-only)
- **Do not modify prompt content** - only structural formatting and response processing

#### 9.3.3 Prompt Content Boundary

**Adjust for data format issues (Permitted)**:
- Data representation facts: "Column contains comma-formatted numbers stored as TEXT"
- Schema presentation clarity: Column types, constraints, available tables
- Dataset-specific data quirks that affect query validity

**Do not adjust for SQL reasoning difficulties (Prohibited)**:
- SQL concept hints: "Use GROUP BY for aggregation"
- Solution guidance: "For averages, use AVG() function"
- SQL syntax teaching: Examples of aggregate functions or WHERE clauses

**Test Principle**: Evaluate SQL reasoning ability given clear data information, not prompt engineering skill.

#### 9.3.4 Model Grouping

Group by response parsing needs, not vendor names:
- Same adapter for similar response formats (version handling within adapter)
- Split adapters when parsing logic becomes incompatible
- Model name parsing determines adapter selection via factory pattern

#### 9.3.5 LiteLLM Integration

LiteLLM handles communication layer (API calls, provider detection), model adapters handle SQL-specific parsing and formatting.

---

## 10. CLI Design

### 10.1 View-Based Evaluation Interface

```bash
# Default evaluation (uses v_questions_default view)
python eval.py --dataset spider1 --backend lm_studio --model "qwen/qwen3-30b"

# Targeted evaluation via views
python eval.py --dataset wikisql --view v_questions_joins       # Only join queries
python eval.py --dataset bird_mini_dev --view v_questions_financial_db  # Financial database only
python eval.py --dataset wikisql --view v_questions_tiny        # Quick testing (10 examples)

# Backend auto-detection (tries LM Studio, Ollama, OpenRouter)
python eval.py --dataset bird_mini_dev --view v_questions_financial_db

# Parameter overrides
python eval.py --dataset spider1 --view v_questions_hard --temperature 0.7 --max-tokens 2000

# Legacy limit support (applies after view selection)
python eval.py --dataset wikisql --view v_questions_joins --limit 5

# Backend specification (skip auto-detection)
python eval.py --dataset spider2_lite --backend openrouter
```

### 10.2 Build Scripts with Views Integration

Dataset building handled separately via Make or individual scripts:

```bash
# Build individual datasets (includes views.sql application)
make build-wikisql        # Builds complete WikiSQL + predefined views
make build-spider1        # Builds complete Spider1 + predefined views
make build-bird-mini-dev  # Builds complete BIRD mini_dev + predefined views

# Build all datasets
make build-all
```

**Build Process with Views**:
1. Dataset builder populates complete `questions` table
2. Builder computes tags, features, complexity scores
3. Builder applies `datasets/{name}/views.sql` to create predefined views
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

### Phase 1: Core Infrastructure

#### 15.1 Backend Auto-Detection System
- [ ] Implement BACKENDS configuration dictionary
- [ ] Create backend auto-detection with local-first ordering
- [ ] Add CLI parameter override support
- [ ] Test LM Studio, Ollama, OpenRouter integration

#### 15.2 Tool Interface Implementation
- [ ] Implement standardized tool signatures
- [ ] Add automatic database targeting (hidden from models)
- [ ] Create schema scope filtering system
- [ ] Build SQL safety validation

#### 15.3 Database-Only Metadata System
- [ ] Create unified database schema standards
- [ ] Implement dynamic schema scope detection from gold SQL
- [ ] Build database loading and validation utilities
- [ ] Add provenance tracking in __bench_meta__ tables

### Phase 2: Dataset Integration

#### 15.4 WikiSQL Complete Dataset Building (High Priority)
- [ ] Build complete WikiSQL dataset (~80K examples) with new schema standards
- [ ] Implement shared SQL analyzer for auto-generated tags
- [ ] Create `datasets/wikisql/views.sql` with tag-based predefined evaluation views
- [ ] Ensure `v_questions_default` selects canonical 500 examples
- [ ] Preserve existing WikiSQL difficulty classification in tags (if available)
- [ ] Move data tables to databases/wikisql_tables.db
- [ ] Test view-based evaluation system
- [ ] Validate metrics match existing 500-example implementation

#### 15.5 Spider1 Complete Dataset Integration (Ready for Implementation)
- [ ] **Complete Dataset Available**: 1,034 dev examples with 100% gold SQL coverage
- [ ] Build spider1_gold.db with complete questions table and auto-generated tags
- [ ] Preserve Spider1 original difficulty values (Easy/Medium/Hard/Extra Hard) in tags
- [ ] Create `datasets/spider1/views.sql` with tag-based and database-specific views
- [ ] Ensure `v_questions_default` includes all dev examples
- [ ] Add database-specific views (e.g., `v_questions_concert_singer_db`, `v_questions_car_db`)
- [ ] Copy 20 domain databases to databases/ subdirectory
- [ ] Implement multi-database context management
- [ ] Test view-based evaluation across all domains

**Spider1 Advantages**:
- Complete gold SQL coverage (vs Spider2-lite's 24/135)
- Cross-domain evaluation (20 databases) enables domain-specific views
- Established benchmark with difficulty classifications
- ~1000 examples for comprehensive evaluation with flexible subsetting

#### 15.6 BIRD mini_dev Complete Integration (High Quality)
- [ ] **Native SQLite**: 500 examples, 11 databases, no conversion needed
- [ ] Build bird_mini_dev_gold.db with complete dataset, evidence field support, and auto-generated tags
- [ ] Preserve BIRD original difficulty values (Simple/Moderate/Challenging) in tags
- [ ] Create `datasets/bird_mini_dev/views.sql` with tag-based and database-specific views
- [ ] Add database-specific views (e.g., `v_questions_financial_db`, `v_questions_european_football_db`)
- [ ] Ensure `v_questions_default` includes all 500 examples
- [ ] Copy 11 domain databases to databases/ subdirectory
- [ ] Integrate evidence field into prompt templates
- [ ] Test view-based evaluation with large databases (up to 570MB)

#### 15.7 Spider2-lite Complete Integration (Limited by Gold SQL Availability)
- [ ] **Focus on 24 high-quality instances** with gold SQL (scope limited by data availability)
- [ ] Build spider2_lite_gold.db with complete available dataset
- [ ] Create `datasets/spider2_lite/views.sql` (may be minimal due to small dataset)
- [ ] Ensure `v_questions_default` includes all 24 examples
- [ ] Copy required subset of 30+ databases
- [ ] Embed external knowledge in metadata JSON field
- [ ] Validate enterprise-scale query execution

#### 15.8 BIRD LiveSQLBench Integration (Future)
- [ ] **Most Complex**: 270 examples with external knowledge requirements
- [ ] Requires CRUD operation support and knowledge base integration
- [ ] Advanced prompt engineering for management tasks
- [ ] Deferred to later phase due to complexity

### Phase 3: Unified Evaluation Engine

#### 15.9 Core Evaluation Script
- [ ] Create `eval.py` as main evaluation interface
- [ ] Implement dataset auto-detection and loading
- [ ] Build unified evaluation loop with database-agnostic logic
- [ ] Add rich TUI progress reporting

#### 15.10 Multi-Database Support
- [ ] **Context-Aware Database Switching**: Automatic target_db selection per question
- [ ] **Unified Tool Interface**: Same execute_sql interface across all architectures
- [ ] **Performance Optimization**: Connection pooling for multi-database scenarios
- [ ] **Error Handling**: Robust handling of complex multi-table query failures

#### 15.11 Schema Scope System
- [ ] **Dynamic Scope Detection**: Parse gold SQL to identify referenced tables/columns
- [ ] **Tool Filtering**: list_tables/describe_table respect scope by default
- [ ] **Optional Full Schema**: --full-schema flag for future enhancement
- [ ] **Scope Caching**: Cache parsed scopes for performance

### Phase 4: Rich User Experience

#### 15.12 CLI Interface Design
- [ ] Simple evaluation interface with parameter overrides
- [ ] Backend auto-detection with manual override capability
- [ ] Progress reporting with rich TUI enhancements
- [ ] Clear error messaging and debugging support

#### 15.13 Build System Integration
- [ ] Individual dataset build scripts (not CLI commands)
- [ ] Makefile integration for dataset building
- [ ] Automated testing of build outputs
- [ ] Provenance tracking and reproducibility

#### 15.14 Output and Logging
- [ ] **JSONL Logs**: Detailed per-item logs with raw responses and extracted SQL
- [ ] **Summary Metrics**: EX/EM rates with feature stratification
- [ ] **Human-Readable Reports**: Quick analysis and debugging information
- [ ] **Error Categorization**: Parse, execution, timeout, and blocked statement tracking

### Phase 5: Testing and Validation

#### 15.15 Single-Database Testing (WikiSQL)
- [ ] Validate WikiSQL evaluation matches existing implementation
- [ ] Test schema scope filtering accuracy
- [ ] Verify tool interface consistency
- [ ] Benchmark evaluation performance

#### 15.16 Multi-Database Testing (Spider1, BIRD)
- [ ] Test database switching and context management
- [ ] Validate cross-domain query execution
- [ ] Test large database performance (BIRD's 570MB databases)
- [ ] Verify external knowledge integration (BIRD)

#### 15.17 Backend Integration Testing
- [ ] Test LM Studio integration with tool calling
- [ ] Validate Ollama compatibility and performance
- [ ] Test OpenRouter integration with API key handling
- [ ] Verify auto-detection fallback chain

#### 15.18 Error Handling and Edge Cases
- [ ] Test SQL parsing and extraction robustness
- [ ] Validate timeout and resource limit enforcement
- [ ] Test malformed query handling and recovery
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

## 20. Current Implementation Status

### 20.1 Supported Datasets

* **WikiSQL**: 500 curated examples, single-database architecture
* **Spider1**: ~1000 examples, multi-database architecture (20 domains)
* **BIRD mini_dev**: 500 examples, multi-database architecture (11 domains)
* **Spider2-lite**: 24 high-quality examples, multi-database architecture
* **BIRD LiveSQLBench**: 270 examples, multi-database with external knowledge

### 20.2 Supported Backends

* **LM Studio**: Local OpenAI-compatible server
* **Ollama**: Local model serving
* **OpenRouter**: Remote frontier model access

---

## 21. Glossary

* **Gold database**: `{dataset}_gold.db` containing questions, gold SQL, and metadata
* **Target database**: Specific database file in `databases/` subdirectory for current question
* **Schema scope**: Minimal set of tables/columns exposed to model, derived from gold SQL
* **Tool-first**: Attempt tool calls before any prompt-only SQL generation
* **Backend auto-detection**: Try local backends (LM Studio, Ollama) before remote (OpenRouter)
* **Canonical evaluation set**: Single curated set of examples per dataset, no splits

---

## 22. Next Steps

1. Implement backend auto-detection system
2. Create unified tool interface with schema scope filtering
3. Align WikiSQL with new database standards
4. Integrate Spider1 multi-database architecture
5. Test end-to-end evaluation with multiple backends
6. Add BIRD mini_dev for evidence field testing
7. Polish CLI interface and error handling
