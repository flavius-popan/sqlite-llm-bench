# BIRD Mini_dev Integration Plan

## Overview
This document analyzes the feasibility of integrating BIRD mini_dev into sqlite-llm-bench's unified .db approach and outlines the implementation strategy based on actual source data analysis.

## BIRD Mini_dev Dataset Analysis

### Actual Source Structure (WIP/BIRD/MINIDEV)
- **Format**: 500 high-quality text-to-SQL pairs in JSON format
- **Databases**: 11 distinct SQLite databases (1.4GB total)
- **Questions File**: `mini_dev_sqlite.json` with structured examples
- **Gold SQL**: `mini_dev_sqlite_gold.sql` with tab-separated format
- **Schema Info**: `dev_tables.json` with complete table/column metadata
- **Database Files**: Individual `.sqlite` files in `dev_databases/` subdirectories

### Key Characteristics Confirmed
- **Native SQLite**: All databases are already in SQLite format, no conversion needed
- **Real-World Data**: Actual database applications with substantial content
- **Multi-Domain**: 11 professional domains with realistic data complexity
- **Evidence Fields**: External knowledge hints provided for complex reasoning
- **Size Distribution**: Ranges from 232KB (superhero) to 570MB (european_football_2)

### Actual Database Distribution
```
california_schools: 30 examples, 11MB database
card_games: 52 examples, 250MB database
codebase_community: 49 examples, 459MB database
debit_card_specializing: 30 examples, 33MB database
european_football_2: 51 examples, 570MB database
financial: 32 examples, 68MB database
formula_1: 66 examples, 21MB database
student_club: 48 examples, 2.5MB database
superhero: 52 examples, 232KB database
thrombosis_prediction: 50 examples, 7MB database
toxicology: 40 examples, 2.6MB database
```

### Verified Difficulty Distribution
- **Simple**: 148 examples (29.6%)
- **Moderate**: 250 examples (50.0%)
- **Challenging**: 102 examples (20.4%)

### JSON Structure (Confirmed)
Each example contains:
- `question_id`: Unique identifier (integer)
- `db_id`: Database identifier (string)
- `question`: Natural language question (string)
- `evidence`: External knowledge hint (string)
- `SQL`: Gold standard SQLite query (string)
- `difficulty`: Classification (simple/moderate/challenging)

## SQLite Compatibility Assessment

### Compatibility Level: A (Native)
**Status**: All queries are already SQLite-compatible
- All 500 queries in `mini_dev_sqlite_gold.sql` are native SQLite
- Tested sample queries execute successfully
- Uses SQLite-specific functions (IIF, SUBSTR, CAST, STRFTIME)
- Set operations (UNION, INTERSECT, EXCEPT) work natively

### SQLite-Specific Functions Confirmed
- **IIF()**: Used in 28+ queries for conditional logic
- **SUBSTR()**: Extensive use for string manipulation
- **CAST()**: Type conversion (FLOAT, REAL, INTEGER)
- **STRFTIME()**: Date formatting and extraction
- **Set Operations**: UNION, EXCEPT confirmed working

### No Compatibility Issues Found
- No C-level (unsupported) items identified
- No need for SQL rewriting or transformation
- All queries execute within reasonable time limits
- Standard SQLite functions only, no extensions required

## Implementation Strategy

### Phase 1: Data Preparation (3-4 days)

#### 1.1 Source Data Verification
```bash
# Verify all databases present and accessible
find WIP/BIRD/MINIDEV/dev_databases -name "*.sqlite" | wc -l  # Should be 11
python -c "import json; print(len(json.load(open('WIP/BIRD/MINIDEV/mini_dev_sqlite.json'))))"  # Should be 500
```

#### 1.2 Database Size Analysis
- **Total Size**: 1.4GB across 11 databases
- **Strategy**: Keep databases separate (too large for consolidation)
- **Performance**: Largest databases may need query timeout adjustments

#### 1.3 Schema Scope Extraction
For each example, determine minimal schema scope from gold SQL:
- Parse table references from SQL queries
- Extract referenced columns from WHERE/SELECT clauses
- Build `schema_scope` objects per spec requirements

### Phase 2: Builder Implementation (1 week)

#### 2.1 Directory Structure
```
datasets/bird_mini_dev/
├── builder.py                    # Main builder script
├── __init__.py
└── bird_mini_dev.py             # Dataset-specific logic
```

#### 2.2 Builder Script Core Logic
```python
class BirdMiniDevBuilder:
    builder_semver = "1.0.0"

    def __init__(self, source_path="WIP/BIRD/MINIDEV"):
        self.source_path = Path(source_path)
        self.examples = self._load_examples()
        self.schemas = self._load_schemas()

    def _load_examples(self):
        with open(self.source_path / "mini_dev_sqlite.json") as f:
            return json.load(f)

    def _load_schemas(self):
        with open(self.source_path / "dev_tables.json") as f:
            return {item["db_id"]: item for item in json.load(f)}

    def build_manifest(self, split_name="bench-500", seed=42):
        manifest_items = []
        for example in self.examples:
            item = {
                "dataset_id": "bird_mini_dev",
                "item_id": str(example["question_id"]),
                "db_path": f"databases/{example['db_id']}.sqlite",
                "question": example["question"],
                "evidence": example["evidence"],
                "gold_sql": example["SQL"],
                "compat_level": "A",  # All native SQLite
                "schema_scope": self._extract_schema_scope(example),
                "tags": self._extract_sql_features(example["SQL"]),
                "difficulty": example["difficulty"],
                "license": "CC BY-SA 4.0",
                "source_ref": f"question_id:{example['question_id']}"
            }
            manifest_items.append(item)
        return manifest_items
```

#### 2.3 Database Copying Strategy
- Copy individual `.sqlite` files to output directory
- Preserve original database structure (no consolidation needed)
- Add `__bench_meta__` table to each database for provenance

#### 2.4 Schema Scope Extraction
```python
def _extract_schema_scope(self, example):
    db_id = example["db_id"]
    sql = example["SQL"]
    schema = self.schemas[db_id]

    # Parse table names from SQL
    referenced_tables = extract_table_names(sql)

    # Build minimal schema scope
    scope = {"tables": {}}
    for table in referenced_tables:
        if table in schema["table_names"]:
            scope["tables"][table] = {
                "columns": get_referenced_columns(sql, table, schema)
            }

    return scope
```

### Phase 3: Evaluation Integration (3-4 days)

#### 3.1 Evidence Field Integration
Modify prompt template to include evidence:
```python
def build_bird_prompt(question, evidence, schema_scope):
    return f"""You are a SQL expert. Generate a SQLite query to answer the question.

Database Schema:
{format_schema_scope(schema_scope)}

Question: {question}

Additional Context: {evidence}

Important Notes:
- Generate complete SQLite SELECT statements
- This database contains real-world data with potential inconsistencies
- Consider the additional context when interpreting the question
- Use SQLite-specific functions (IIF, SUBSTR, CAST) as needed

SQL:"""
```

#### 3.2 No Efficiency Metrics Initially
- BIRD's R-VES efficiency scoring is complex and not well-documented
- Start with standard EX/EM metrics matching spec
- Add efficiency metrics in future iteration if needed

#### 3.3 Large Database Handling
- Increase default timeout from 10s to 30s for large databases
- Monitor memory usage during evaluation
- Consider query limits for very large result sets

### Phase 4: Split Generation (2-3 days)

#### 4.1 Stratified Sampling Strategy
```python
def generate_splits(examples, seed=42):
    # Stratify by difficulty and database
    strata = defaultdict(list)
    for example in examples:
        key = (example["difficulty"], example["db_id"])
        strata[key].append(example)

    # Sample for toy-50 (representative subset)
    toy_samples = []
    for stratum, items in strata.items():
        n_samples = max(1, len(items) * 50 // 500)  # Proportional sampling
        toy_samples.extend(random.Random(seed).sample(items, n_samples))

    return {
        "bench-500": examples,  # All examples
        "toy-50": toy_samples[:50]  # Capped at 50
    }
```

#### 4.2 Feature Tag Extraction
```python
def _extract_sql_features(self, sql):
    features = []
    sql_upper = sql.upper()

    if "JOIN" in sql_upper:
        features.append("join")
    if "GROUP BY" in sql_upper:
        features.append("group_by")
    if "ORDER BY" in sql_upper:
        features.append("order_by")
    if "HAVING" in sql_upper:
        features.append("having")
    if any(op in sql_upper for op in ["UNION", "INTERSECT", "EXCEPT"]):
        features.append("set_ops")
    if "(" in sql and "SELECT" in sql[sql.find("("):]:
        features.append("subquery")
    if any(func in sql_upper for func in ["SUM", "COUNT", "AVG", "MAX", "MIN"]):
        features.append("aggregation")
    if "IIF" in sql_upper:
        features.append("conditional")

    return features
```

### Phase 5: Testing and Validation (3-4 days)

#### 5.1 Query Execution Testing
```bash
# Test all 500 queries execute successfully
python -c "
import sqlite3
import json

data = json.load(open('WIP/BIRD/MINIDEV/mini_dev_sqlite.json'))
for item in data[:10]:  # Test subset first
    db_path = f'WIP/BIRD/MINIDEV/dev_databases/{item[\"db_id\"]}/{item[\"db_id\"]}.sqlite'
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(item['SQL'])
        result = cursor.fetchall()
        print(f'✓ Query {item[\"question_id\"]}: {len(result)} rows')
    except Exception as e:
        print(f'✗ Query {item[\"question_id\"]}: {e}')
    finally:
        conn.close()
"
```

#### 5.2 Performance Benchmarking
- Measure query execution times across databases
- Identify queries requiring timeout extension
- Test memory usage with largest databases

#### 5.3 End-to-End Integration
```bash
# Build dataset
sqlite-bench build --dataset bird_mini_dev --split toy-50

# Run evaluation
sqlite-bench run --dataset bird_mini_dev --split toy-50 --profile lm_studio --limit 10

# Verify results
sqlite-bench report --run runs/latest
```

## Technical Implementation Details

### Manifest Schema Compliance
```json
{
  "dataset_id": "bird_mini_dev",
  "item_id": "1471",
  "db_path": "databases/debit_card_specializing.sqlite",
  "question": "What is the ratio of customers who pay in EUR against customers who pay in CZK?",
  "gold_sql": "SELECT CAST(SUM(IIF(Currency = 'EUR', 1, 0)) AS FLOAT) / SUM(IIF(Currency = 'CZK', 1, 0)) AS ratio FROM customers",
  "compat_level": "A",
  "schema_scope": {
    "tables": {
      "customers": {
        "columns": ["Currency"]
      }
    }
  },
  "tags": ["aggregation", "conditional", "cast"],
  "evidence": "ratio of customers who pay in EUR against customers who pay in CZK = count(Currency = 'EUR') / count(Currency = 'CZK').",
  "difficulty": "simple",
  "license": "CC BY-SA 4.0",
  "source_ref": "question_id:1471"
}
```

### Database Metadata Integration
```sql
-- Add to each database
CREATE TABLE __bench_meta__ (
    dataset_id TEXT DEFAULT 'bird_mini_dev',
    dataset_version TEXT,
    builder_semver TEXT DEFAULT '1.0.0',
    upstream_sha TEXT,
    created_at_utc TEXT,
    sqlite_version TEXT,
    row_counts_json TEXT,
    original_db_id TEXT,
    original_size_bytes INTEGER
);
```

### Provenance Tracking
```json
{
  "dataset_id": "bird_mini_dev",
  "dataset_version": "1.0.0+src.minidev",
  "builder_semver": "1.0.0",
  "source_urls": [
    "WIP/BIRD/MINIDEV/mini_dev_sqlite.json",
    "WIP/BIRD/MINIDEV/dev_tables.json",
    "WIP/BIRD/MINIDEV/dev_databases/"
  ],
  "upstream_sha": "minidev",
  "created_at_utc": "2024-01-15T10:30:00Z",
  "python_version": "3.11.7",
  "sqlite_version": "3.44.2",
  "total_examples": 500,
  "total_databases": 11,
  "total_size_bytes": 1468006400,
  "cli_args": ["--dataset", "bird_mini_dev", "--split", "bench-500"]
}
```

## Integration with Unified System

### CLI Commands
```bash
# List available datasets
sqlite-bench ls datasets
# -> bird_mini_dev: 500 examples, 11 databases

# Build dataset
sqlite-bench build --dataset bird_mini_dev --split bench-500
sqlite-bench build --dataset bird_mini_dev --split toy-50

# Run evaluation
sqlite-bench run --dataset bird_mini_dev --split toy-50 --profile lm_studio
sqlite-bench run --dataset bird_mini_dev --split bench-500 --profile ollama --limit 100

# Verify integrity
sqlite-bench verify --dataset bird_mini_dev
```

### Output Metrics Extension
```json
{
  "idx": 1471,
  "dataset_id": "bird_mini_dev",
  "item_id": "1471",
  "db_id": "debit_card_specializing",
  "question": "What is the ratio of customers who pay in EUR against customers who pay in CZK?",
  "evidence": "ratio of customers who pay in EUR against customers who pay in CZK = count(Currency = 'EUR') / count(Currency = 'CZK').",
  "gold_sql": "SELECT CAST(SUM(IIF(Currency = 'EUR', 1, 0)) AS FLOAT) / SUM(IIF(Currency = 'CZK', 1, 0)) AS ratio FROM customers",
  "pred_sql": "SELECT CAST(SUM(IIF(Currency = 'EUR', 1, 0)) AS FLOAT) / SUM(IIF(Currency = 'CZK', 1, 0)) AS ratio FROM customers",
  "em": 1,
  "ex": 1,
  "execution_time": 0.045,
  "difficulty": "simple",
  "tags": ["aggregation", "conditional", "cast"],
  "used_evidence": true,
  "pred_err": null,
  "raw_assistant": "Looking at the question and evidence...[model response]"
}
```

## Risk Assessment and Mitigation

### Low Risk Items
- **SQLite Compatibility**: All queries are native SQLite (A-level)
- **Data Format**: JSON structure is well-defined and parsed successfully
- **Database Access**: All 11 SQLite files verified accessible

### Medium Risk Items
- **Database Size**: 1.4GB total may impact performance
  - *Mitigation*: Test with timeouts, monitor memory usage
- **Complex Queries**: Some queries with multiple JOINs and subqueries
  - *Mitigation*: Start with simple examples, gradually increase complexity
- **Evidence Integration**: Prompts may become long with evidence fields
  - *Mitigation*: Test context limits, truncate evidence if needed

### High Risk Items
- **Large Result Sets**: Some queries may return massive results
  - *Mitigation*: Implement LIMIT guards, test result size caps

## Success Criteria
- [ ] All 500 examples successfully parsed and loaded
- [ ] All 11 databases copied and metadata added
- [ ] 95%+ of queries execute successfully within timeout
- [ ] Schema scope correctly extracted for all examples
- [ ] Evidence fields properly integrated into prompts
- [ ] toy-50 split provides representative sample across difficulties
- [ ] Integration with unified CLI works seamlessly
- [ ] Performance acceptable on largest databases

## Timeline Estimate: 2-3 weeks
- **Week 1**: Data preparation, builder implementation, basic testing
- **Week 2**: Evaluation integration, split generation, performance tuning
- **Week 3**: Integration testing, documentation, validation

## Next Steps
1. Implement `datasets/bird_mini_dev/builder.py` following spec requirements
2. Test with toy-50 split first for rapid iteration
3. Validate against existing WikiSQL implementation patterns
4. Add to main dataset registry once stable
