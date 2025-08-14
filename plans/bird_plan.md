# BIRD Mini_dev Integration Plan

## Overview
This document analyzes the feasibility of integrating BIRD mini_dev into sqlite-llm-bench's unified .db approach and outlines the implementation strategy.

## BIRD Mini_dev Dataset Analysis

### Current Structure
- **Format**: 500 high-quality text-to-SQL pairs
- **Databases**: 11 distinct databases (SQLite version available)
- **Complexity**: Large-scale databases with extensive content (33.4 GB total in full BIRD)
- **Domains**: 37+ professional domains (blockchain, hockey, healthcare, education)
- **Evaluation**: Traditional SQL execution with efficiency metrics
- **External Knowledge**: Evidence fields for complex reasoning

### Key Characteristics
- **Real-World Data**: Derived from actual database applications with "dirty" data
- **Multi-Domain**: Covers diverse professional sectors
- **Large Content**: Emphasis on database values and content-based reasoning
- **Efficiency Focus**: First benchmark to evaluate SQL efficiency, not just correctness
- **Evidence-Based**: Questions include external knowledge hints for complex queries

### Difficulty Distribution
- **Simple**: 30% (150 examples)
- **Moderate**: 50% (250 examples) 
- **Challenging**: 20% (100 examples)

### Database Distribution
- **Debit Card Specializing**: 30 instances
- **Student Club**: 48 instances
- **Thrombosis Prediction**: 50 instances
- **European Football 2**: 51 instances
- **Formula 1**: 66 instances
- **Superhero**: 52 instances
- **Codebase Community**: 44 instances
- **Card Games**: 39 instances
- **California Schools**: 49 instances
- **Toxicology**: 36 instances
- **Formula 1 (alternate)**: 35 instances

## Compatibility Assessment with Unified .db Approach

### Major Advantages

#### 1. SQLite Version Available
- **Status**: BIRD mini_dev provides native SQLite format
- **Benefit**: No complex database conversion required
- **Source**: Available via HuggingFace datasets and official downloads

#### 2. Manageable Scale
- **Size**: Mini_dev subset is significantly smaller than full BIRD (33.4 GB)
- **Databases**: Only 11 databases vs 95 in full BIRD
- **Queries**: 500 examples vs 12,751 in full dataset

#### 3. Traditional Evaluation
- **Method**: Standard SQL execution and result comparison
- **Compatibility**: Aligns well with existing WikiSQL evaluation approach
- **Metrics**: Execution Accuracy (EX) and efficiency scoring

### Minor Challenges

#### 1. External Knowledge Integration
- **Issue**: Questions include "evidence" fields with external reasoning hints
- **Example**: "account.type = 'OWNER' can be inferred by: 'The condition requires account type should be owner'"
- **Solution**: Include evidence in metadata.json and evaluation prompt

#### 2. Efficiency Evaluation
- **Issue**: BIRD introduces efficiency scoring beyond correctness
- **Metrics**: R-VES (Reward-based Valid Efficiency Score)
- **Solution**: Extend evaluation to track query execution time and complexity

#### 3. Data Quality Considerations
- **Issue**: "Dirty" data with non-standard formats requiring preprocessing
- **Examples**: Inconsistent date formats, special characters, encoding issues
- **Solution**: Document data quirks in metadata for proper model instruction

## Implementation Strategy

### Phase 1: Data Acquisition and Setup (1 week)

#### 1.1 Download and Verify
```bash
# Download BIRD mini_dev SQLite version
wget https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip
# Verify HuggingFace version matches
python -c "from datasets import load_dataset; dataset = load_dataset('birdsql/bird_mini_dev')"
```

#### 1.2 Database Analysis
- **Schema Inspection**: Analyze all 11 databases for table structures
- **Data Quality Assessment**: Identify "dirty" data patterns
- **Size Verification**: Confirm databases fit unified .db approach

#### 1.3 Question Analysis
- **Evidence Field Mapping**: Catalog all external knowledge requirements
- **Difficulty Classification**: Verify distribution across simple/moderate/challenging
- **SQL Complexity**: Analyze query patterns and required features

### Phase 2: Dataset Standardization (1-2 weeks)

#### 2.1 Database Consolidation
```
datasets/bird_mini_dev/
├── bird_mini_dev.db           # Consolidated database with all 11 schemas
├── metadata.json              # Dataset configuration
└── external_knowledge/        # Evidence and documentation
    ├── database_descriptions.md
    ├── domain_knowledge.md
    └── evaluation_notes.md
```

#### 2.2 Schema Integration
- **Namespace Strategy**: Prefix table names with database ID (e.g., `debit_card_accounts`)
- **Cross-Database Views**: Create views for multi-database questions if needed
- **Index Creation**: Add appropriate indexes for query performance

#### 2.3 Metadata Creation
```json
{
  "dataset_name": "bird_mini_dev",
  "version": "1.0",
  "total_examples": 500,
  "databases": 11,
  "evaluation_type": "execution_with_efficiency",
  "external_knowledge_required": true,
  "difficulty_distribution": {
    "simple": 150,
    "moderate": 250,
    "challenging": 100
  },
  "domains": [
    "finance", "sports", "healthcare", "education", 
    "entertainment", "transportation", "technology"
  ],
  "special_considerations": [
    "dirty_data",
    "efficiency_scoring",
    "external_evidence",
    "large_content_focus"
  ]
}
```

### Phase 3: Evaluation Integration (1 week)

#### 3.1 Efficiency Metrics Implementation
```python
def evaluate_with_efficiency(query, expected_result, database):
    start_time = time.time()
    result = execute_sql(query, database)
    execution_time = time.time() - start_time
    
    # Standard accuracy check
    accuracy = compare_results(result, expected_result)
    
    # Efficiency scoring (R-VES implementation)
    efficiency_score = calculate_rves(query, execution_time, result_size)
    
    return {
        "accuracy": accuracy,
        "execution_time": execution_time,
        "efficiency_score": efficiency_score,
        "rves": efficiency_score
    }
```

#### 3.2 Evidence Integration
- **Prompt Enhancement**: Include evidence fields in user prompts
- **Context Management**: Handle evidence without exceeding context limits
- **Evaluation Logic**: Track evidence usage in model responses

#### 3.3 Unified Evaluation Support
- **Parameter Addition**: Add `--enable-efficiency` flag to unified_eval.py
- **Metrics Extension**: Include efficiency metrics in JSONL output
- **TUI Enhancement**: Display efficiency scores in Rich interface

### Phase 4: Testing and Validation (1 week)

#### 4.1 Accuracy Verification
- **Baseline Comparison**: Compare results against official BIRD evaluation
- **Cross-Platform Testing**: Verify results across different SQLite versions
- **Edge Case Handling**: Test with challenging examples and dirty data

#### 4.2 Performance Testing
- **Query Execution**: Ensure all 500 queries execute within reasonable time
- **Memory Usage**: Monitor memory consumption with large databases
- **Concurrent Access**: Test multi-threaded evaluation if needed

#### 4.3 Integration Testing
- **End-to-End**: Full evaluation run with unified_eval.py
- **Provider Testing**: Verify with different backends (LM Studio, OpenRouter)
- **Error Handling**: Test graceful failure modes

## Technical Implementation Details

### Database Schema Strategy
```sql
-- Example schema consolidation
CREATE TABLE debit_card_account (
    account_id INTEGER PRIMARY KEY,
    account_type TEXT,
    customer_id INTEGER,
    -- ... other columns
    db_source TEXT DEFAULT 'debit_card'
);

CREATE TABLE student_club_member (
    member_id INTEGER PRIMARY KEY,
    club_id INTEGER,
    student_id INTEGER,
    -- ... other columns
    db_source TEXT DEFAULT 'student_club'
);
```

### Evidence Field Handling
```python
def build_bird_prompt(question, evidence, table_info):
    prompt = f"""
Table Information: {table_info}

Question: {question}

Additional Context: {evidence}

Important Notes:
- This database contains real-world data that may have inconsistent formats
- Focus on the actual data values, not just schema
- Consider the provided context when interpreting the question

Generate a SQL query to answer the question:
"""
    return prompt
```

### Efficiency Scoring Implementation
```python
def calculate_rves(query, execution_time, result_accuracy):
    """
    Simplified R-VES calculation
    R-VES = accuracy * efficiency_factor
    """
    if not result_accuracy:
        return 0.0
    
    # Time-based efficiency (penalize slow queries)
    time_factor = max(0.1, 1.0 - (execution_time / 30.0))  # 30s baseline
    
    # Query complexity factor (reward simpler correct queries)
    complexity_factor = 1.0 / (1.0 + query.count('JOIN') * 0.1)
    
    return result_accuracy * time_factor * complexity_factor
```

## Evaluation Metrics Extension

### Standard Metrics (from WikiSQL)
- **Exact Match (EM)**: Query string exact match
- **Execution Accuracy (EX)**: Result correctness

### BIRD-Specific Metrics
- **R-VES**: Reward-based Valid Efficiency Score
- **Soft F1**: Fuzzy matching for complex results
- **Execution Time**: Query performance measurement
- **Evidence Usage**: Whether model leveraged external knowledge

### Implementation in JSONL Output
```json
{
  "idx": 42,
  "database": "debit_card",
  "question": "What is the total balance for OWNER type accounts?",
  "evidence": "The condition requires account type should be owner",
  "gold_sql": "SELECT SUM(balance) FROM account WHERE type = 'OWNER'",
  "pred_sql": "SELECT SUM(balance) FROM account WHERE type = 'OWNER'",
  "em": 1,
  "ex": 1,
  "execution_time": 0.025,
  "rves": 0.95,
  "soft_f1": 1.0,
  "difficulty": "simple",
  "domain": "finance",
  "used_evidence": true
}
```

## Integration with Plan.md

### Dependencies
- **Phase 1** (Backend): BIRD integration can proceed in parallel
- **Phase 4** (Rich TUI): BIRD metrics will enhance dashboard
- **Phase 5** (Output): Efficiency metrics extend JSONL structure

### Timeline Coordination
- **Week 1-2**: Implement during Phase 2-3 of main plan
- **Week 3-4**: Integration testing during Phase 4
- **Week 5+**: Production ready for Phase 6 testing

## Success Criteria
- [ ] All 500 BIRD mini_dev examples execute successfully
- [ ] Evaluation accuracy within 2% of official BIRD results
- [ ] 95% of queries execute under 10 seconds
- [ ] Efficiency metrics properly calculated and logged
- [ ] Evidence fields integrated into evaluation prompts
- [ ] Seamless integration with unified evaluation system

## Risk Assessment

### Low Risk
- **SQLite Compatibility**: Native SQLite format available
- **Dataset Size**: Manageable 11 databases, 500 examples
- **Evaluation Method**: Standard SQL execution approach

### Medium Risk
- **Efficiency Metrics**: R-VES implementation complexity
- **Data Quality**: Handling "dirty" real-world data patterns
- **Performance**: Large content databases may slow evaluation

### Mitigation Strategies
- **Gradual Implementation**: Start with simple examples, build complexity
- **Performance Monitoring**: Set execution time limits and optimize
- **Community Support**: Leverage BIRD team documentation and examples
- **Fallback Options**: Maintain ability to evaluate subsets if needed

## Conclusion

BIRD mini_dev represents an excellent second dataset for sqlite-llm-bench due to:

1. **Native Compatibility**: SQLite format already available
2. **Manageable Complexity**: Smaller scope than full BIRD or Spider2
3. **Real-World Relevance**: Actual database applications with dirty data
4. **Efficiency Focus**: Introduces important performance considerations
5. **Clear Implementation Path**: Well-defined integration steps

The integration should proceed after Spider2-lite analysis is complete, providing a complementary dataset that bridges the gap between WikiSQL's simplicity and Spider2's enterprise complexity.