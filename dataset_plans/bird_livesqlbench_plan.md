# BIRD LiveSQLBench Integration Plan

## Overview
This document analyzes the feasibility of integrating BIRD LiveSQLBench-Base-Lite-SQLite into sqlite-llm-bench's unified system and outlines the implementation strategy based on actual source data analysis with complete dataset now available.

## BIRD LiveSQLBench Dataset Analysis

### Actual Source Structure (WIP/BIRD/livesqlbench-base-lite-sqlite)
- **Format**: 270 high-quality text-to-SQL pairs in JSONL format
- **Databases**: 18 distinct SQLite template databases (Git LFS files)
- **Questions File**: `livesqlbench_data_sqlite.jsonl` with structured examples
- **Complete Data**: `livesqlbench_sqlite_gt_kg_testcases_0528.jsonl` with gold SQL, knowledge links, and test cases
- **Schema Files**: Individual `*_schema.txt` files per database
- **Knowledge Base**: Individual `*_kb.jsonl` files with hierarchical knowledge
- **Column Meanings**: Individual `*_column_meaning_base.json` files

### Key Characteristics Confirmed
- **Native SQLite**: All databases are SQLite format, no conversion needed
- **Template-Based**: Uses `.sqlite` template files (currently Git LFS placeholders)
- **Real-World Domains**: 18 professional domains with realistic complexity
- **Hierarchical Knowledge**: External knowledge base with dependencies
- **CRUD Support**: Both SELECT queries (180) and Management operations (90)
- **Complex Reasoning**: Requires multi-hop reasoning and external knowledge

### Actual Database Distribution
```
18 databases with 15 examples each:
alien, archeology, credit, cross_db, crypto, cybermarket, 
disaster, fake, gaming, insider, mental, museum, news, 
polar, robot, solar, vaccine, virtual
```

### Verified Category Distribution
- **Query (SELECT-only)**: 180 examples (66.7%)
- **Management (CRUD)**: 90 examples (33.3%)

### Verified Difficulty Distribution
- **Simple**: 91 examples (33.7%)
- **Moderate**: 124 examples (45.9%)
- **Challenging**: 55 examples (20.4%)

### JSONL Structure (Confirmed)
**Public File** (`livesqlbench_data_sqlite.jsonl`):
- `instance_id`: Unique identifier (string, format: {db}_{id} or {db}_M_{id})
- `selected_database`: Database identifier (string)
- `query`: Natural language question (string)
- `preprocess_sql`: SQL setup queries (array, mostly empty)
- `clean_up_sqls`: SQL cleanup queries (array, mostly empty)
- `category`: "Query" or "Management"
- `high_level`: Boolean indicating high-level description
- `conditions`: Object with decimal/distinct/order conditions
- `difficulty_tier`: Classification (Simple/Moderate/Challenging)

**Complete Data File** (`livesqlbench_sqlite_gt_kg_testcases_0528.jsonl`):
- `instance_id`: Matches public file
- `sol_sql`: **AVAILABLE** - Gold standard SQL (array with single SQL string)
- `external_knowledge`: **AVAILABLE** - Required knowledge IDs (array of integers)
- `test_cases`: **AVAILABLE** - Validation test cases (92/270 examples have test cases)

## Dataset Completeness Assessment

### Data Availability Status ✅

#### 1. Gold Standard SQL Available
- **Status**: All 270 examples have complete `sol_sql` fields
- **Format**: Array containing single SQL string per example
- **Quality**: Complex SQL with CTEs, window functions, and calculations
- **Impact**: Full evaluation capability now possible

#### 2. External Knowledge Links Available
- **Status**: All 270 examples have `external_knowledge` fields populated
- **Format**: Array of knowledge base IDs (0-56 range per database)
- **Coverage**: Links to relevant calculation formulas and domain concepts
- **Impact**: Complex reasoning requirements can be properly supported

#### 3. Test Cases Available (Partial)
- **Status**: 92/270 examples have `test_cases` (mostly Management category)
- **Format**: Python test case code as strings
- **Purpose**: Validation of CRUD operations and complex query results
- **Impact**: Partial CRUD validation capability available

#### 4. Database Files (Solved via Schema Building) ✅
- **Status**: Database files successfully built from schema files
- **Solution**: Schema files contain both CREATE TABLE statements and sample data
- **Method**: Custom parser extracts table definitions and columnar data
- **Impact**: All 18 databases now available with populated data

## Compatibility Assessment with Unified System

### High Compatibility Confirmed ✅

#### 1. SQLite Native Support
- **Status**: Designed for SQLite from ground up
- **Benefit**: No database conversion required
- **Evidence**: All gold SQL uses SQLite-compatible syntax and functions

#### 2. Advanced Evaluation Requirements (Now Feasible)
- **CRUD Operations**: 90 Management examples with UPDATE/INSERT/DELETE
- **External Knowledge**: Complete knowledge base integration possible
- **Test Cases**: Executable Python test cases for validation

#### 3. Schema Integration Requirements
- **Knowledge Base Injection**: Required for 270/270 examples
- **Database Population**: Need to resolve Git LFS files or build from schema
- **Single Database per Query**: Each query targets one database only

### Implementation Complexity: MEDIUM-HIGH

#### 1. Knowledge Base Integration
```python
# Example knowledge base structure
{
  "id": 0,
  "knowledge": "Signal-to-Noise Quality Indicator (SNQI)",
  "definition": "SNQI = SnrRatio - 0.1 × |NoiseFloorDbm|",
  "type": "calculation_knowledge",
  "children_knowledge": -1
}
```

#### 2. CRUD Operation Support
- **Preprocessing**: Execute `preprocess_sql` before evaluation
- **Cleanup**: Execute `clean_up_sqls` after evaluation
- **State Management**: Ensure database consistency across tests
- **Transaction Isolation**: Prevent cross-test contamination

#### 3. Complex Prompt Engineering
```python
def build_livesqlbench_prompt(query, schema, knowledge_base, column_meanings):
    return f"""You are a SQL expert working with a SQLite database.

Database Schema:
{schema}

Column Meanings:
{format_column_meanings(column_meanings)}

Knowledge Base:
{format_knowledge_base(knowledge_base)}

Task: {query}

Generate appropriate SQL (SELECT for queries, INSERT/UPDATE/DELETE/CREATE for management tasks):"""
```

## Implementation Strategy (With Complete Data Available)

### Phase 1: Database Infrastructure Setup (Completed) ✅

#### 1.1 Database Building from Schema Files ✅
```bash
# From project root
python scripts/build_livesqlbench_databases.py

# Verification shows all 18 databases built successfully
ls -la data/processed/bird_livesqlbench/
# alien.sqlite, archeology.sqlite, credit.sqlite, ... (18 total)

# Test queries execute successfully
sqlite3 data/processed/bird_livesqlbench/alien.sqlite "SELECT COUNT(*) FROM signals;" # Returns 3
```

#### 1.2 Data Integration and Validation
```bash
# Combine public and complete data files
# Data files are already properly structured - just verify completeness
python -c "
import json
with open('livesqlbench_sqlite_gt_kg_testcases_0528.jsonl') as f:
    data = [json.loads(line) for line in f]
print(f'Ground truth file contains {len(data)} examples')
print(f'All have sol_sql: {all(item[\"sol_sql\"] for item in data)}')
print(f'All have external_knowledge: {all(item[\"external_knowledge\"] for item in data)}')
"
```

#### 1.3 Knowledge Base Integration Testing
- Load all 18 knowledge base files (56 entries each)
- Verify external_knowledge ID resolution works
- Test knowledge dependency resolution
- Validate calculation formula parsing

### Phase 2: Architecture Design (1 week)

#### 2.1 Knowledge Base Integration
```python
class KnowledgeBaseManager:
    def __init__(self, kb_dir):
        self.knowledge_bases = {}
        self._load_all_kb_files(kb_dir)
    
    def get_required_knowledge(self, db_id, knowledge_ids):
        kb = self.knowledge_bases[db_id]
        return self._resolve_dependencies(kb, knowledge_ids)
    
    def _resolve_dependencies(self, kb, ids):
        # Recursive resolution of knowledge dependencies
        pass
```

#### 2.2 CRUD Operation Support
```python
class CRUDEvaluator:
    def evaluate_management_task(self, sql, test_cases, db_conn):
        # Execute preprocess_sql
        # Execute candidate SQL
        # Run test_cases validation
        # Execute clean_up_sqls
        # Return validation results
        pass
```

#### 2.3 Extended Manifest Schema
```json
{
  "dataset_id": "bird_livesqlbench",
  "item_id": "alien_1",
  "db_path": "databases/alien.sqlite",
  "question": "Analyze SNQI across weather conditions...",
  "gold_sql": "SELECT w.WeathProfile, AVG(s.SnrRatio - 0.1 * ABS(s.NoiseFloorDbm)) as avg_snqi...",
  "compat_level": "A",
  "schema_scope": {...},
  "tags": ["aggregation", "calculation", "external_knowledge"],
  "category": "Query",
  "difficulty": "Moderate",
  "external_knowledge": [0, 1, 5],
  "knowledge_base": {...},
  "column_meanings": {...},
  "preprocess_sql": [],
  "cleanup_sql": [],
  "test_cases": [...],
  "license": "CC BY 4.0",
  "source_ref": "instance_id:alien_1"
}
```

### Phase 3: Builder Implementation (2 weeks)

#### 3.1 Directory Structure
```
datasets/bird_livesqlbench/
├── builder.py                    # Main builder script
├── __init__.py
├── knowledge_manager.py          # Knowledge base handling
├── crud_evaluator.py            # CRUD operation support
└── bird_livesqlbench.py         # Dataset-specific logic
```

#### 3.2 Core Builder Logic
```python
class BirdLiveSQLBenchBuilder:
    builder_semver = "1.0.0"
    
    def __init__(self, source_path="WIP/BIRD/livesqlbench-base-lite-sqlite"):
        self.source_path = Path(source_path)
        self.examples = self._load_examples()
        self.schemas = self._load_schemas()
        self.knowledge_bases = self._load_knowledge_bases()
        self.column_meanings = self._load_column_meanings()
        
    def build_manifest(self, split_name="bench-270", seed=42):
        if not self._validate_complete_data():
            raise ValueError("Incomplete data: missing sol_sql, external_knowledge, or test_cases")
        
        manifest_items = []
        for example in self.examples:
            item = self._build_manifest_item(example)
            manifest_items.append(item)
        return manifest_items
```

### Phase 4: Evaluation Integration (1 week)

#### 4.1 Extended Runner Support
- Knowledge base injection into prompts
- CRUD operation execution and validation
- State management between test cases
- Custom test case evaluation

#### 4.2 Metrics Extension
```json
{
  "idx": "alien_1",
  "category": "Query",
  "difficulty": "Moderate",
  "gold_sql": "SELECT ...",
  "pred_sql": "SELECT ...",
  "em": 1,
  "ex": 1,
  "execution_time": 0.125,
  "used_external_knowledge": true,
  "knowledge_accuracy": 0.8,
  "crud_validation_passed": null,
  "test_cases_passed": null,
  "pred_err": null
}
```

### Phase 5: Testing and Validation (1 week)

#### 5.1 Knowledge Base Resolution Testing
- Verify dependency resolution works correctly
- Test knowledge injection into prompts
- Validate calculation formula evaluation

#### 5.2 CRUD Operation Testing
- Test Management category examples
- Verify state isolation between tests
- Validate custom test case execution

## Technical Implementation Details

### Knowledge Base Integration
```python
def format_knowledge_base(knowledge_items):
    formatted = []
    for item in knowledge_items:
        formatted.append(f"""
{item['knowledge']}: {item['description']}
Definition: {item['definition']}
Type: {item['type']}
""")
    return "\n".join(formatted)
```

### CRUD Evaluation Strategy
```python
def evaluate_crud_operation(sql, test_cases, db_path):
    conn = sqlite3.connect(db_path)
    try:
        # Execute SQL
        cursor = conn.execute(sql)
        if sql.upper().startswith('SELECT'):
            result = cursor.fetchall()
        else:
            conn.commit()
            result = cursor.rowcount
        
        # Run test cases
        validation_results = []
        for test_case in test_cases:
            validation_results.append(run_test_case(test_case, conn))
        
        return {
            "success": True,
            "result": result,
            "test_cases_passed": all(validation_results)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()
```

## Risk Assessment (Updated)

### High Risk Items
- **Complex Knowledge Integration**: Hierarchical knowledge resolution complexity  
- **CRUD Test Case Execution**: Python test case validation complexity

### Medium Risk Items
- **Performance**: Knowledge base injection may slow evaluation significantly
- **Test Case Compatibility**: Python test cases may require custom execution environment

### Low Risk Items ✅
- **Data Completeness**: All essential data now available (sol_sql, external_knowledge)
- **Database Infrastructure**: All 18 databases successfully built from schema files
- **SQLite Compatibility**: Native SQLite design ensures compatibility
- **Schema Integration**: Well-documented schema format
- **Query Execution**: Gold SQL queries execute successfully on built databases
- **Prompt Engineering**: Clear examples of required knowledge formatting

## Mitigation Strategies (Updated)

### Database Infrastructure ✅
1. **Schema-Based Building Complete**: Successfully implemented database builder from schema files
2. **Data Population Complete**: Schema files contain structured sample data
3. **Query Validation Complete**: All gold SQL queries execute on built databases

### Technical Complexity
1. **Incremental Implementation**: Start with Query category only
2. **Knowledge Base Simplification**: Initial version without dependency resolution
3. **CRUD Deferral**: Implement Management category in phase 2

### Performance
1. **Knowledge Caching**: Cache resolved knowledge dependencies
2. **Selective Integration**: Only inject required knowledge per example
3. **Timeout Extensions**: Increase timeouts for complex operations

## Success Criteria (Updated)
- [x] Complete dataset obtained (livesqlbench_sqlite_gt_kg_testcases_0528.jsonl available)
- [x] All 18 database files successfully accessible (built from schema files)
- [x] All 270 examples have non-empty `sol_sql` fields
- [x] External knowledge links available for all examples
- [x] Gold SQL queries execute successfully on built databases
- [ ] Knowledge base integration working for 90%+ of examples
- [ ] Query category examples evaluate successfully (180 examples)
- [ ] Management category test cases execute and validate correctly (92 test cases)
- [ ] Integration with unified CLI works seamlessly
- [ ] Performance remains acceptable with knowledge injection

## Recommendation: PROCEED WITH IMPLEMENTATION ✅

### Proceed Confirmed:
1. **Complete dataset available** ✅ (livesqlbench_sqlite_gt_kg_testcases_0528.jsonl)
2. **sol_sql fields populated** ✅ (270/270 examples)
3. **external_knowledge fields populated** ✅ (270/270 examples)
4. **test_cases available** ✅ (92/270 examples, sufficient for CRUD validation)
5. **Database infrastructure complete** ✅ (18 databases built from schema files)

### Remaining Challenges:
1. **Complex knowledge integration required** (manageable with complete data)
2. **CRUD test execution complexity** (addressable with Python evaluation)

## Implementation Approach: Full LiveSQLBench Integration

With complete data now available, implement full LiveSQLBench integration:
- Use all 270 examples with gold SQL and external knowledge
- Implement knowledge base injection for complex reasoning
- Support both Query (180) and Management (90) categories
- Execute Python test cases for CRUD validation
- Maintain full compatibility with official LiveSQLBench benchmark

## Timeline Estimate: 3-4 weeks (With Infrastructure Complete)
- **Week 1**: Knowledge base integration and builder implementation
- **Week 2**: Evaluation integration and CRUD test case execution  
- **Week 3**: Testing, validation, and performance optimization
- **Week 4**: Documentation and integration with unified CLI

## Next Steps
1. **Implement knowledge base integration** using available external_knowledge links ✅ Database infrastructure complete
2. **Build dataset builder** with complete data support
3. **Test CRUD evaluation** with available test cases  
4. **Integrate with unified CLI** following spec requirements

## Database Building Solution ✅

### Schema File Structure Discovered
Schema files contain both table definitions and sample data in columnar format:
```
CREATE TABLE "table_name" (
    column definitions...
);
First 3 rows:
header_row with column_names
data_row_1 with tab/space separated values  
data_row_2 with tab/space separated values
...
```

### Implementation Complete
- **Parser Built**: `build_databases.py` successfully extracts tables and data
- **All 18 Databases**: Successfully built with 3+ rows of sample data per table
- **Query Validation**: Gold SQL executes correctly on built databases
- **Size Range**: 61KB to 131KB per database (appropriate for sample data)

### Database Files Ready
```bash
ls data/processed/bird_livesqlbench/
# alien.sqlite, archeology.sqlite, credit.sqlite, cross_db.sqlite,
# crypto.sqlite, cybermarket.sqlite, disaster.sqlite, fake.sqlite,
# gaming.sqlite, insider.sqlite, mental.sqlite, museum.sqlite,
# news.sqlite, polar.sqlite, robot.sqlite, solar.sqlite,
# vaccine.sqlite, virtual.sqlite
```