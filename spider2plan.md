# Spider2-lite SQLite Integration Plan (Unified Architecture)

## Overview
This document outlines the technical implementation for integrating Spider2-lite's SQLite dataset into sqlite-llm-bench's unified .db architecture. The plan eliminates CSV files and external markdown dependencies, creating a fully self-contained SQLite-based evaluation system similar to WikiSQL.

## Licensing and Legal Compliance

### Spider2 MIT License
Spider2-lite is released under the MIT License (Copyright (c) 2024 bird_sql), which permits:
- ✅ Commercial and non-commercial use
- ✅ Modification and derivative works (JSON-to-SQLite conversion)
- ✅ Distribution and redistribution
- ✅ Public release of converted databases

### Compliance Requirements
1. **License Attribution**: Include MIT license text with converted databases
2. **Copyright Notice**: Preserve original copyright in derivative works
3. **Documentation**: Credit Spider2 team in dataset documentation

## Spider2-lite Dataset Analysis

### Current Structure Issues
- **SQLite Examples**: 135 "local" instances from 547 total examples  
- **Database Storage Format**: JSON files per table + DDL.csv schema definitions (NOT .db files)
- **Gold SQL Coverage**: Only 24 out of 135 instances (18%) have gold SQL files
- **Scope Decision**: Focus on 24 instances with existing gold SQL to maintain evaluation quality
- **External Knowledge**: Selected instances require embedded markdown content

### Database Scale and Complexity Analysis
**Table Counts Per Database:**
- **Minimum**: 35 tables (WWE)
- **Maximum**: 352 tables (Baseball)
- **Average**: ~92 tables per database
- **Total**: ~2,760 tables across 30 databases

**Schema Complexity:**
- **Enterprise-scale relationships** with complex multi-table joins
- **Real production database schemas** (AdventureWorks, Chinook, Brazilian_E_Commerce)
- **Advanced SQL Features**: CTEs, window functions, recursive queries required

### Critical Challenge: Missing Gold SQL
**Problem**: 82% of instances lack gold SQL, making traditional SQL-based evaluation impossible.

**Solutions Evaluated:**
1. **Reverse Engineering**: Generate SQL from CSV results (too complex for enterprise queries)
2. **Data Storage**: Store expected results as structured data (breaks WikiSQL consistency)
3. **Scope Reduction**: Focus on 24 instances with existing gold SQL

**Decision**: Use 24 instances with gold SQL to maintain WikiSQL's proven evaluation pattern and ensure quality.

## Unified SQLite Architecture

### Core Design Principles
1. **Single File Format**: All data stored in SQLite databases
2. **Self-Contained**: No external CSV or markdown file dependencies
3. **Human Inspectable**: Easy comparison of questions, SQL, and expected results
4. **Consistent Evaluation**: Unified SQL execution matching across all datasets

### Architecture Overview

```
datasets/spider2_lite/
├── spider2_lite.db                 # Master questions and metadata database (24 instances)
├── databases/                      # Individual schema databases (subset needed)
│   ├── E_commerce.db              # For local003, local004 
│   ├── Baseball.db                # For local008
│   ├── WWE.db                     # For local019
│   └── ... (only databases used by 24 instances)
├── LICENSE                        # Spider2 MIT license text
└── ATTRIBUTION.md                 # Credits and source information
```

### Master Database Schema (spider2_lite.db)

```sql
CREATE TABLE questions (
    instance_id TEXT PRIMARY KEY,
    db_name TEXT NOT NULL,
    question TEXT NOT NULL,
    external_knowledge TEXT,           -- Embedded markdown content when needed
    gold_sql TEXT NOT NULL             -- All 24 instances have gold SQL
);

CREATE TABLE database_schemas (
    db_name TEXT PRIMARY KEY,
    db_file_path TEXT NOT NULL,
    table_count INTEGER NOT NULL,
    description TEXT
);

-- No longer needed - using gold SQL execution matching like WikiSQL
```

## Implementation Strategy

### Phase 1: Database Reconstruction

#### 1.1 Individual Database Creation
Convert JSON + DDL.csv format to SQLite databases:

```python
def build_database_from_json(schema_name: str) -> Path:
    """Convert JSON files + DDL.csv to SQLite database"""
    db_path = f"databases/{schema_name}.db"
    
    # Parse DDL.csv and create tables
    ddl_df = pd.read_csv(f"resource/databases/sqlite/{schema_name}/DDL.csv")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON;")
    
    for _, row in ddl_df.iterrows():
        conn.execute(row['DDL'])
    
    # Load JSON data into tables with proper type conversion
    json_files = Path(f"resource/databases/sqlite/{schema_name}").glob("*.json")
    for json_file in json_files:
        table_name = json_file.stem
        if not table_name.startswith('sqlite_'):
            load_json_to_table(conn, json_file, table_name)
    
    return Path(db_path)
```

#### 1.2 Master Database Population

```python
def populate_master_database():
    """Create master database with all questions and metadata"""
    conn = sqlite3.connect("spider2_lite.db")
    
    # Load questions from spider2-lite.jsonl  
    with open("spider2-lite.jsonl") as f:
        for line in f:
            item = json.loads(line)
            if item['instance_id'].startswith('local'):
                
                # Load external knowledge if referenced
                external_knowledge = None
                if item.get('external_knowledge'):
                    knowledge_path = f"resource/documents/{item['external_knowledge']}"
                    external_knowledge = Path(knowledge_path).read_text()
                
                # Only process instances with gold SQL
                sql_path = f"evaluation_suite/gold/sql/{item['instance_id']}.sql"
                if Path(sql_path).exists():
                    gold_sql = Path(sql_path).read_text()
                    
                    # Insert into questions table  
                    conn.execute("""
                        INSERT INTO questions 
                        (instance_id, db_name, question, external_knowledge, gold_sql)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        item['instance_id'],
                        item['db'], 
                        item['question'],
                        external_knowledge,
                        gold_sql
                    ))
```

#### 1.3 Database Creation Only
All evaluation handled through gold SQL execution - no CSV processing needed.

### Phase 2: Unified Evaluation Engine

#### 2.1 SQL-Based Evaluation

```python
def evaluate_spider2_instance(instance: Dict, predicted_sql: str) -> Dict:
    """Evaluate Spider2-lite instance using SQL execution matching (same as WikiSQL)"""
    
    # Connect to appropriate database
    db_path = f"databases/{instance['db_name']}.db"
    db_conn = sqlite3.connect(db_path)
    
    try:
        # Execute both predicted and gold SQL
        pred_result = execute_sql_query(db_conn, predicted_sql)
        gold_result = execute_sql_query(db_conn, instance['gold_sql'])
        
        return {
            'em': 1 if normalize_sql(predicted_sql) == normalize_sql(instance['gold_sql']) else 0,
            'ex': 1 if results_equal(pred_result, gold_result) else 0
        }
            
    except Exception as e:
        return {'ex': 0, 'em': 0, 'error': str(e)}
    finally:
        db_conn.close()
```

#### 2.2 Standard SQL Execution
All 24 instances use standard SQL execution matching - no multi-part handling needed.

### Phase 3: Tool Integration

#### 3.1 Context-Aware Execute SQL Tool

```python
def execute_sql_tool(query: str, context: Dict) -> Dict:
    """Execute SQL against correct database with unified interface"""
    
    db_name = context['current_db_name']
    db_path = f"databases/{db_name}.db"
    
    conn = sqlite3.connect(db_path)
    try:
        result = conn.execute(query)
        rows = result.fetchall()
        columns = [desc[0] for desc in result.description] if result.description else []
        
        return {
            'success': True,
            'columns': columns,
            'rows': rows,
            'row_count': len(rows)
        }
    except Exception as e:
        return {
            'success': False, 
            'error': str(e)
        }
    finally:
        conn.close()
```

## Addressing Missing Gold SQL Challenge

### Decision: Scope Reduction to 24 High-Quality Instances

**Why 24 instances instead of 135:**
- Reverse engineering 111 complex enterprise queries is unrealistic
- Maintains WikiSQL's proven evaluation pattern (gold SQL execution matching)
- Ensures evaluation quality and reliability  
- Still provides enterprise-scale complexity (multi-table joins, CTEs, window functions)

**Benefits:**
- Consistent evaluation methodology across all datasets
- Human-inspectable gold SQL for debugging and analysis
- No complex data comparison logic needed
- High-quality evaluation over questionable quantity

## Success Criteria

### Functional Requirements
- [x] 24 high-quality SQLite instances with gold SQL successfully converted
- [x] Only required database files constructed from JSON sources (subset of 30)
- [x] External knowledge correctly embedded for applicable instances
- [x] Traditional SQL execution matching evaluation (same as WikiSQL)
- [x] Unified SQL-based evaluation without external file dependencies
- [x] Enterprise-scale complexity maintained with multi-table joins and advanced SQL

### Technical Requirements
- [x] Individual SQLite database files maintain referential integrity
- [x] Master database provides unified question access with embedded knowledge
- [x] Expected results stored as structured data within database
- [x] Database reconstruction is deterministic and reproducible
- [x] No CSV files or external markdown dependencies
- [x] Human-inspectable data for debugging and analysis

### Integration Requirements  
- [x] Dataset loads correctly in unified evaluation system
- [x] CLI accepts spider2_lite as valid dataset parameter
- [x] Evaluation results compatible with existing JSONL logging format
- [x] SQL execution evaluation provides detailed error reporting
- [x] Performance acceptable for enterprise-scale databases

## Implementation Priority

### Phase 1: Database Reconstruction (Critical)
1. Build JSON-to-SQLite conversion pipeline for 30 databases
2. Create master database with questions, external knowledge, and expected results
3. Convert CSV results to structured data within SQLite
4. Validate data integrity and relationships across all databases

### Phase 2: Evaluation Engine Integration
1. Implement SQL execution-based evaluation (replacing CSV comparison)
2. Add multi-database support to evaluation engine  
3. Handle multi-part result validation through database queries
4. Support both gold SQL matching and data comparison evaluation

### Phase 3: Tool Integration
1. Implement context-aware execute_sql tool with automatic database selection
2. Integrate external knowledge injection through database queries
3. Test end-to-end evaluation workflow with unified SQL interface

### Phase 4: Testing and Validation
1. Validate evaluation accuracy against original CSV-based results
2. Performance testing with enterprise-scale databases (35-352 tables)
3. Integration testing with unified evaluation system
4. Human inspection and debugging capabilities

This unified architecture eliminates external file dependencies while maintaining the enterprise-grade complexity and evaluation requirements of Spider2-lite, creating a fully self-contained SQLite-based evaluation system.