# SQL Evaluation Methods Comparison

A comprehensive analysis of evaluation approaches across different SQL benchmarking systems: Spider1, BIRD benchmark, and sqlite-llm-bench (WikiSQL).

## Overview

This document compares four distinct evaluation philosophies for SQL generation tasks:

1. **Spider1**: Comprehensive structural and execution evaluation
2. **Spider2**: Multi-database execution evaluation with flexible comparison criteria
3. **BIRD**: Multi-metric execution-focused evaluation with efficiency scoring
4. **sqlite-llm-bench**: Simple dual-metric evaluation for single-table queries

## Detailed Comparison

### 1. Spider1 Evaluation (WIP/Spider1/evaluation.py)

**Philosophy**: Deep structural analysis with fine-grained component scoring

#### Key Features
- **Comprehensive Metrics**:
  - Exact Match (EM): Structural SQL comparison
  - Execution Accuracy (EX): Result set comparison
  - 10+ Partial Component Scores: Individual SQL clause analysis
- **Difficulty Classification**: Easy, Medium, Hard, Extra
- **Advanced SQL Parsing**: Converts SQL to structured intermediate representation
- **Component-wise Analysis**:
  - SELECT (with/without aggregation)
  - WHERE (with/without operators)
  - GROUP BY (with/without HAVING)
  - ORDER BY
  - AND/OR logic
  - Set operations (UNION, INTERSECT, EXCEPT)
  - Nested queries (IUEN)
  - Keywords analysis

#### Technical Implementation
```python
class Evaluator:
    def eval_exact_match(p_sql, g_sql)      # Structural comparison
    def eval_partial_match(p_sql, g_sql)    # Component-wise analysis
    def eval_hardness(g_sql)                # Difficulty classification
```

#### Strengths
- **Diagnostic Power**: Identifies specific SQL component weaknesses
- **Research Value**: Enables fine-grained model capability analysis
- **Partial Credit**: Rewards partially correct solutions
- **Complex Query Support**: Handles multi-table joins, subqueries, set operations

#### Limitations
- **Single-threaded**: No parallel processing
- **SQLite Only**: Limited database engine support
- **Parsing Dependency**: Requires sophisticated SQL parser
- **Computational Overhead**: Detailed analysis is time-intensive

### 2. Spider2 Evaluation (WIP/Spider2/spider2-lite/evaluation_suite/evaluate.py)

**Philosophy**: Real-world multi-database execution evaluation with flexible comparison criteria

#### Key Features
- **Multi-Database Support**: BigQuery, Snowflake, SQLite
- **Flexible Result Comparison**: Configurable column subsets and ordering requirements
- **Production-Scale Evaluation**: Real cloud database systems
- **Dual Submission Modes**: SQL files or pre-computed CSV results
- **Advanced Result Matching**: Multi-gold standard support and conditional evaluation

#### Technical Implementation
```python
def compare_pandas_table(pred, gold, condition_cols=[], ignore_order=False):
    # Flexible column-based comparison
    # Supports numerical tolerance (1e-2)
    # Configurable order sensitivity
    # Vector-based matching with type awareness

def compare_multi_pandas_table(pred, multi_gold, multi_condition_cols=[]):
    # Multiple gold standard support
    # OR-based evaluation (any gold standard matches)
    # Per-gold configuration support
```

#### Advanced Features
- **Conditional Column Evaluation**: Focus on specific columns for comparison
- **Order Sensitivity Control**: Per-query ignore_order configuration
- **Numerical Tolerance**: Built-in floating-point comparison (1e-2 tolerance)
- **Multi-Gold Standards**: Support for multiple valid answers per query
- **Database Prefixes**: Automatic routing based on query ID (bq*, sf*, local*)
- **Cost Tracking**: BigQuery data processing volume monitoring
- **Robust Error Handling**: Database-specific error classification

#### Database-Specific Features
- **BigQuery Integration**: Cloud-scale data processing with cost tracking
- **Snowflake Support**: Enterprise data warehouse evaluation
- **SQLite Local**: Fast local database evaluation with memory optimization
- **Credential Management**: Secure cloud database authentication

#### Evaluation Configuration
```json
{"instance_id": "bq003", "condition_cols": [1, 2], "ignore_order": true, "toks": "113"}
{"instance_id": "bq269", "condition_cols": [[1, 2], [3]], "ignore_order": true, "toks": "91"}
```

#### Strengths
- **Real-World Relevance**: Uses actual production database systems
- **Scalability**: Handles enterprise-scale data volumes
- **Flexibility**: Configurable evaluation criteria per query
- **Multi-Standard Support**: Handles ambiguous queries with multiple valid answers
- **Database Diversity**: Tests cross-platform SQL compatibility
- **Cost Awareness**: Tracks computational resource usage

#### Limitations
- **Infrastructure Dependency**: Requires cloud database access and credentials
- **Cost Implications**: BigQuery evaluation incurs actual usage costs
- **Setup Complexity**: Multi-database credential and access management
- **No Structural Analysis**: Pure execution-based evaluation
- **Binary Scoring**: No partial credit for near-correct results

### 3. BIRD Benchmark Evaluation

**Philosophy**: Multi-faceted execution evaluation with efficiency and partial correctness

#### 3.1 Execution Accuracy (evaluation_ex.py)

**Core Metric**: Binary execution correctness (EX)

```python
def calculate_ex(predicted_res, ground_truth_res):
    res = 0
    if set(predicted_res) == set(ground_truth_res):
        res = 1
    return res
```

**Features**:
- Simple set-based result comparison
- Timeout handling (30s default)
- Multi-database support (SQLite, MySQL, PostgreSQL)
- Parallel processing with multiprocessing

#### 3.2 Soft F1 Score (evaluation_f1.py)

**Core Metric**: Row-level partial matching with F1 scoring

```python
def calculate_f1_score(predicted, ground_truth):
    # Element-wise row comparison
    # Calculates precision, recall, F1 for partial matches
    match_scores = []
    for gt_row in ground_truth:
        match_score = calculate_row_match(pred_row, gt_row)
        match_scores.append(match_score)

    tp = sum(match_scores)
    fp = sum(pred_only_scores)
    fn = sum(truth_only_scores)

    f1_score = 2 * precision * recall / (precision + recall)
```

**Features**:
- **Granular Scoring**: Element-level comparison within rows
- **Partial Credit**: Rewards partially correct results
- **Duplicate Handling**: Automatically deduplicates results
- **Robustness**: Handles mismatched result set sizes

#### 3.3 Execution Efficiency (evaluation_ves.py)

**Core Metric**: Reward-based VES (Valid Efficiency Score)

```python
def iterated_execute_sql(predicted_sql, ground_truth, db_path, iterate_num):
    # Execute both queries multiple times
    # Compare execution times with statistical cleaning
    time_ratio = ground_truth_time / predicted_time

    # Reward tiers based on efficiency
    if time_ratio >= 2:    reward = 1.25    # Much faster
    elif time_ratio >= 1:  reward = 1.0     # Comparable
    elif time_ratio >= 0.5: reward = 0.75   # Slower
    elif time_ratio >= 0.25: reward = 0.5   # Much slower
    else:                  reward = 0.25    # Very slow
```

**Features**:
- **Performance Evaluation**: Measures query execution efficiency
- **Statistical Robustness**: Outlier removal with 3-sigma filtering
- **Iterative Sampling**: Multiple executions (100 iterations default)
- **Reward System**: Tiered scoring based on relative performance
- **Only for Correct Queries**: Efficiency only measured when results match

#### BIRD Common Features
- **Difficulty Stratification**: Simple, Moderate, Challenging categories
- **Parallel Processing**: Multi-CPU support for scalability
- **Multi-Database**: SQLite, MySQL, PostgreSQL compatibility
- **Timeout Management**: Configurable execution limits
- **JSON-based Configuration**: External difficulty annotations

#### BIRD Strengths
- **Scalability**: Efficient parallel evaluation
- **Real-world Relevance**: Focuses on practical correctness and efficiency
- **Database Agnostic**: Cross-platform compatibility
- **Multiple Perspectives**: Execution, partial correctness, and efficiency
- **Robustness**: Comprehensive error and timeout handling

#### BIRD Limitations
- **No Structural Analysis**: Cannot diagnose specific SQL syntax issues
- **Limited Diagnostic Value**: Binary/scalar metrics provide less insight
- **Efficiency Measurement Complexity**: VES requires careful statistical handling

### 4. sqlite-llm-bench Evaluation (eval.py)

**Philosophy**: Simple dual-metric evaluation for conversational SQL generation

#### Key Features
- **Exact Match (EM)**: Normalized SQL string comparison
- **Execution Accuracy (EX)**: Result set comparison
- **Tool Integration**: Tracks LLM function calling usage
- **Conversation Logging**: Complete interaction tracking
- **WikiSQL Focus**: Single-table query optimization

#### Technical Implementation
```python
def evaluate():
    # Simple string normalization for EM
    em = int(normalize_sql(pred_sql) == normalize_sql(gold_sql))

    # Basic execution comparison for EX
    pred_rows = exec_sql(conn, pred_sql)
    gold_rows = exec_sql(conn, gold_sql)
    ex = int(execution_equal(pred_rows, gold_rows))
```

#### Strengths
- **Simplicity**: Easy to understand and implement
- **LLM Integration**: Native support for conversational AI workflows
- **Function Calling**: Tracks tool usage patterns
- **Fast Execution**: Minimal computational overhead
- **Conversation Context**: Full dialog logging for analysis

#### Limitations
- **Limited Scope**: WikiSQL single-table queries only
- **No Partial Scoring**: Binary success/failure only
- **No Difficulty Stratification**: Flat evaluation approach
- **SQLite Only**: Single database engine
- **Basic Error Handling**: Simple exception catching

## Metric Comparison Matrix

| Aspect | Spider1 | Spider2 | BIRD EX | BIRD F1 | BIRD VES | sqlite-llm-bench |
|--------|---------|---------|---------|---------|-----------|------------------|
| **Primary Metric** | EM + Partial | Flexible EX | Binary EX | Soft F1 | Efficiency | EM + EX |
| **Granularity** | Component-level | Column-level | Query-level | Row-level | Query-level | Query-level |
| **Partial Credit** | ✅ Extensive | ✅ Column-wise | ❌ None | ✅ Row-wise | ❌ None | ❌ None |
| **Structural Analysis** | ✅ Deep | ❌ None | ❌ None | ❌ None | ❌ None | ❌ None |
| **Performance Eval** | ❌ None | ✅ Cost Tracking | ❌ None | ❌ None | ✅ Core | ❌ None |
| **Parallel Processing** | ❌ Single | ❌ Single | ✅ Multi-CPU | ✅ Multi-CPU | ✅ Multi-CPU | ❌ Single |
| **Database Support** | SQLite | Multi-Cloud | Multi-DB | Multi-DB | Multi-DB | SQLite |
| **Query Complexity** | Complex | Production | Complex | Complex | Complex | Simple |
| **Difficulty Levels** | 4 levels | Token-based | 3 levels | 3 levels | 3 levels | None |
| **Error Handling** | Graceful | DB-specific | Timeout | Timeout | Timeout | Basic |

## Use Case Recommendations

### Choose Spider1 When:
- **Research Focus**: Need detailed component-wise analysis
- **Model Development**: Debugging specific SQL generation weaknesses
- **Academic Evaluation**: Comprehensive metric reporting required
- **Complex Queries**: Multi-table joins, subqueries, set operations
- **Diagnostic Depth**: Understanding partial correctness patterns

### Choose Spider2 When:
- **Production Environment**: Need real-world database system validation
- **Multi-Database Testing**: Cross-platform SQL compatibility required
- **Enterprise Scale**: Large-scale data processing evaluation
- **Flexible Criteria**: Different evaluation standards per query
- **Cost Monitoring**: Resource usage tracking important
- **Cloud Integration**: Using BigQuery, Snowflake, or similar systems

### Choose BIRD EX When:
- **Production Readiness**: Real-world correctness is primary concern
- **Large-scale Evaluation**: Need efficient parallel processing
- **Cross-database**: Testing across multiple SQL engines
- **Simple Metrics**: Binary success/failure sufficient
- **Performance Critical**: Fast evaluation pipeline needed

### Choose BIRD F1 When:
- **Partial Credit Important**: Value near-correct solutions
- **Result Analysis**: Need row-level correctness understanding
- **Ranking Systems**: Continuous scoring for model comparison
- **Nuanced Evaluation**: Binary metrics too coarse

### Choose BIRD VES When:
- **Efficiency Matters**: Query performance is critical
- **Production Deployment**: Real-world performance evaluation
- **Optimization Research**: Studying query efficiency patterns
- **Resource Constraints**: Measuring computational efficiency

### Choose sqlite-llm-bench When:
- **Conversational AI**: LLM integration primary focus
- **Simple Queries**: Single-table operations sufficient
- **Rapid Prototyping**: Quick evaluation setup needed
- **Tool Usage Analysis**: Function calling behavior important
- **Educational**: Learning SQL evaluation basics

## Integration Opportunities

### Hybrid Approach Benefits
Combining multiple evaluation methods can provide comprehensive insights:

1. **Spider1 + Spider2**: Structural analysis with production-scale validation
2. **Spider2 + BIRD**: Real-world execution with efficiency measurement
3. **BIRD F1 + VES**: Partial correctness with efficiency measurement
4. **All Methods**: Complete evaluation suite for research

### Implementation Strategy
```python
def comprehensive_evaluate(pred_sql, gold_sql, db_path, eval_config=None):
    results = {}

    # Spider1-style structural analysis
    results['components'] = analyze_sql_components(pred_sql, gold_sql)

    # Spider2-style flexible execution
    if eval_config:
        results['flexible_ex'] = compare_pandas_table(
            pred_results, gold_results,
            eval_config.get('condition_cols', []),
            eval_config.get('ignore_order', False)
        )

    # BIRD-style execution metrics
    results['execution'] = calculate_ex(pred_sql, gold_sql, db_path)
    results['soft_f1'] = calculate_f1_score(pred_sql, gold_sql, db_path)
    results['efficiency'] = calculate_ves(pred_sql, gold_sql, db_path)

    # sqlite-llm-bench style simplicity
    results['exact_match'] = normalize_sql(pred_sql) == normalize_sql(gold_sql)

    return results
```

## Future Directions

### Emerging Evaluation Needs
- **Multi-modal Queries**: Text + SQL + Data visualization
- **Contextual Evaluation**: Multi-turn conversation assessment
- **Semantic Similarity**: Beyond exact string/result matching
- **Human Preference**: Incorporating user satisfaction metrics
- **Explainability**: Evaluating query reasoning and explanation quality

### Technical Improvements
- **Unified Framework**: Single evaluation system supporting all metrics
- **Real-time Evaluation**: Streaming assessment for interactive systems
- **Adaptive Difficulty**: Dynamic complexity adjustment based on model performance
- **Cross-language Support**: Evaluation across different SQL dialects
- **Automated Error Analysis**: AI-powered failure mode classification

## Conclusion

Each evaluation approach reflects different priorities in SQL generation assessment:

- **Spider1** prioritizes comprehensive structural understanding
- **Spider2** emphasizes production-scale multi-database execution
- **BIRD** focuses on practical execution correctness and efficiency
- **sqlite-llm-bench** targets conversational AI integration

The choice depends on your specific goals: research depth, production readiness, or rapid prototyping. For comprehensive evaluation, consider implementing multiple approaches to capture different aspects of SQL generation quality.

The evolution from simple correctness (Spider1) to flexible criteria (Spider2) to multi-metric assessment (BIRD) suggests the field is moving toward more nuanced evaluation that considers real-world deployment scenarios, efficiency, partial correctness, and practical applicability. Spider2's introduction of configurable evaluation criteria and multi-database support represents a significant step toward production-ready SQL evaluation systems.
