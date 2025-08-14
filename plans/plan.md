# SQLite LLM Bench Refactoring Plan

## Overview
This plan outlines the transformation of sqlite-llm-bench from a dataset-specific evaluation tool to a unified, multi-provider text-to-SQL benchmark platform. The goal is to standardize datasets into self-contained SQLite databases, unify evaluation logic through SQL execution matching, improve backend abstraction, and enhance user experience while maintaining detailed logging for future analysis.

## Architecture Goals
- **Unified Evaluation**: Single evaluation script that works across all datasets
- **SQLite-Only Architecture**: All data stored in SQLite databases, no CSV or external file dependencies
- **Standardized Evaluation**: SQL execution matching across all datasets for consistency
- **Provider Abstraction**: Clean backend configuration for LM Studio, OpenRouter, and future Ollama support
- **Rich TUI**: Beautiful terminal interface using rich library
- **Future-Proof Logging**: Detailed JSONL output for custom UI development

## Dataset Architecture Comparison

### WikiSQL vs Spider2-lite: Key Differences

| Aspect | WikiSQL | Spider2-lite |
|--------|---------|--------------|
| **Database Structure** | Single .db file with 500+ tables | 30 separate .db files (35-352 tables each) |
| **Total Scale** | 500 questions, 450 tables | 24 questions, ~700 tables |
| **Query Complexity** | Single table queries | Multi-table joins within schemas |
| **Evaluation Method** | SQL execution matching (EM/EX) | **Unified: SQL execution matching** |
| **Tool Use** | `execute_sql(query)` on single DB | `execute_sql(query)` with database switching managed |
| **External Knowledge** | None required | **Embedded in master database** |
| **Schema Relationships** | Independent tables | Complex FK relationships per database |
| **Result Storage** | SQL result sets | **Gold SQL execution matching** |

### Unified Architecture Benefits
- **Consistent Evaluation**: Same SQL execution matching across all datasets
- **Human Inspectable**: Questions, gold SQL, and expected results all queryable
- **Self-Contained**: No external CSV or markdown file dependencies
- **Tool Simplicity**: Models use same execute_sql interface regardless of dataset
- **Performance**: Optimized for SQL operations, no file I/O during evaluation

## Phase 1: Backend Provider Abstraction

### 1.1 Provider Configuration System
- [ ] Create `backends/` directory structure
- [ ] Define `BACKEND_CONFIGS` dictionary with provider settings
  - [ ] LM Studio configuration (OpenAI-compatible local)
  - [ ] OpenRouter configuration (frontier models)
  - [ ] Ollama configuration (future local testing)
- [ ] Replace hardcoded LiteLLM parameters with config-driven approach
- [ ] Remove provider-specific hacks (custom_llm_provider, reasoning field extraction)

### 1.2 Unified Model Interface
- [ ] Create `call_model_unified()` function replacing `call_model_litellm()`
- [ ] Implement backend selection logic
- [ ] Add proper error handling per provider
- [ ] Update CLI to accept `--backend` parameter instead of hardcoded base URLs

### 1.3 Provider Testing
- [ ] Test LM Studio integration with new config system
- [ ] Add OpenRouter integration and test with frontier models
- [ ] Validate API key handling and environment variable support

## Phase 2: Dataset Standardization

### 2.1 Dataset Structure Redesign
- [ ] Create unified dataset directory structure:
  - [ ] **WikiSQL Pattern**: `datasets/{name}/{name}.db` - Single standardized SQLite database
  - [ ] **Spider2-lite Pattern**: `datasets/{name}/spider2_lite.db` (master) + `databases/` (schema DBs)
  - [ ] **Unified Approach**: All questions, expected results, and metadata in SQLite databases
  - [ ] Remove dataset-specific evaluation scripts
  - [ ] Eliminate CSV and external markdown file dependencies

### 2.2 WikiSQL Conversion
- [ ] Ensure existing WikiSQL database follows new standard format
- [ ] Create WikiSQL metadata.json with dataset configuration
- [ ] Validate existing evaluation logic works with new structure

### 2.3 Spider1 Integration Analysis (Ready for Implementation)
- [x] **Complete Dataset Downloaded**: 1,034 dev examples + 8,659 train examples with 100% gold SQL coverage
- [x] **Database Files Available**: All 166 SQLite databases present in spider_data/database/ directory
- [x] **SLM-Focused Strategy**: 500-example subset from dev set across all 20 databases for optimal local evaluation
- [x] **Difficulty-Based Sampling**: Official Spider1 classifications (Easy/Medium/Hard/Extra Hard) for principled selection
- [x] **Enhanced Schema Info**: spider_schema_rows_v2.json with data types and sample values
- [x] **Configurable Distribution**: Adjustable difficulty percentages in generation script for experimentation
- [x] **WikiSQL Complementarity**: Multi-table, cross-domain complexity fills single-table WikiSQL gaps

### 2.4 Spider2-lite Integration Analysis (Completed)
- [x] **Architecture**: Multi-database approach required (subset of databases for 24 instances)
- [x] **Scale**: 24 high-quality instances with gold SQL across enterprise schemas
- [x] **Critical Finding**: Only 24/135 instances have gold SQL - scope to these for quality
- [x] **Evaluation**: **Unified SQL execution matching** (same as WikiSQL pattern)
- [x] **External Knowledge**: **Embedded in master database** (no external files)
- [x] **Gold SQL**: All 24 instances have verified gold SQL for execution matching
- [x] **Tool Use**: Context-aware database switching for execute_sql tool

### 2.5 Future Dataset Preparation
- [ ] Research BIRD mini_dev dataset structure and requirements
- [ ] Document dataset conversion requirements and standards
- [ ] Plan SQLite schema conventions for additional datasets

### 2.6 Dataset Registry System
- [ ] Create `eval/dataset_registry.py` for dataset discovery
- [ ] Implement dataset metadata loading and validation
- [ ] Add dataset selection logic for unified evaluation script
- [ ] **Dataset-specific loaders**:
  - [ ] WikiSQL: Single database + questions view loader
  - [ ] Spider1: Multi-database + 500-example SLM-focused sampling loader
  - [ ] Spider2-lite: Multi-database + external knowledge loader

## Phase 3: Unified Evaluation Engine

### 3.1 Core Evaluation Logic
- [ ] Create `eval/unified_eval.py` as main evaluation script
- [ ] Extract common evaluation patterns from existing WikiSQL script
- [ ] Implement dataset-agnostic evaluation loop
- [ ] Move SQL extraction, normalization, and execution logic to shared modules

### 3.2 Tool Integration
- [ ] **Unified Tool Interface**: Standardize `execute_sql` tool across all datasets
- [ ] **WikiSQL**: Single database connection, table switching via SQL
- [ ] **Spider1**: Context-aware database selection across 20 databases with unified tool interface
- [ ] **Spider2-lite**: Context-aware database selection with same tool interface
- [ ] Implement tool choice logic (auto/required/none)
- [ ] Abstract multi-database complexity from models (transparent switching)
- [ ] Support both single-table and multi-table query patterns

### 3.3 CLI Interface Design
- [ ] Design unified CLI accepting:
  - [ ] `--backend` (lm_studio, openrouter, ollama)
  - [ ] `--dataset` (wikisql, spider1, spider2_lite, bird_mini)
  - [ ] `--model` (model identifier)
  - [ ] Standard evaluation parameters (limit, temperature, etc.)
  - [ ] **Dataset-specific parameters**:
    - [ ] WikiSQL: Single database path validation
    - [ ] Spider1: Database directory validation + 500-example sampling configuration
    - [ ] Spider2-lite: Database directory validation (all data self-contained)

### 3.4 Configuration Management
- [ ] Implement environment variable support for API keys
- [ ] Add configuration file support for default settings
- [ ] Create configuration validation and error handling
- [ ] **Dataset-specific configuration**:
  - [ ] WikiSQL: Database path validation
  - [ ] Spider1: Database directory validation + difficulty distribution configuration (15%/30%/35%/20%)
  - [ ] Spider2-lite: Database directory + external knowledge path validation

## Phase 4: Rich TUI Enhancement

### 4.1 Dependencies and Setup
- [ ] Add rich library to project dependencies
- [ ] Import required rich components (Progress, Console, Table, Panel)

### 4.2 Progress Visualization
- [ ] Replace basic print statements with rich progress bars
- [ ] Implement live metrics display during evaluation
- [ ] Add spinner and time estimation for long-running evaluations

### 4.3 Real-time Feedback
- [ ] Create live results table showing EM/EX percentages
- [ ] Implement failure highlighting for immediate debugging
- [ ] Add model and configuration info header

### 4.4 Final Summary Dashboard
- [ ] Design comprehensive results table with metrics breakdown
- [ ] Implement error categorization and display
- [ ] Add visual indicators for pass/fail thresholds
- [ ] Include log file location and next steps guidance

## Phase 5: Output Enhancement and Future Preparation

### 5.1 JSONL Structure Enhancement
- [ ] Review and standardize JSONL record structure across datasets
- [ ] Add metadata fields for future analysis (dataset name, backend, timestamps)
- [ ] **Dataset-specific fields**:
  - [ ] WikiSQL: `table_name`, `gold_sql`, `em`, `ex`
  - [ ] Spider2-lite: `db_name`, `gold_sql`, `em`, `ex`, `external_knowledge_used`
- [ ] Ensure backward compatibility with existing logs

### 5.2 Output Organization
- [ ] Implement organized output directory structure
- [ ] Create run comparison and tracking capabilities
- [ ] Add run metadata files for better organization

### 5.3 Analysis Preparation
- [ ] Document JSONL schema for future UI development
- [ ] Create sample analysis scripts using current JSONL format
- [ ] Plan integration points for future web dashboard

## Phase 6: Testing and Validation

### 6.1 Regression Testing
- [ ] Ensure WikiSQL evaluation results match existing implementation
- [ ] Validate metrics calculation accuracy
- [ ] Test edge cases and error handling

### 6.2 Multi-Provider Testing
- [ ] **WikiSQL**: Test evaluation consistency across LM Studio and OpenRouter
- [ ] **Spider1**: Validate 500-example cross-domain evaluation across providers with configurable difficulty sampling
- [ ] **Spider2-lite**: Validate complex multi-table queries work across providers (24 instances)
- [ ] Validate tool calling works across different backends
- [ ] Test database switching and embedded knowledge injection
- [ ] Test SQL execution evaluation for both datasets
- [ ] Test error handling and recovery for different providers

### 6.3 Performance and Usability
- [ ] **WikiSQL**: Benchmark evaluation speed compared to current implementation
- [ ] **Spider1**: Test 500-example evaluation performance and difficulty distribution balance for SLM iteration
- [ ] **Spider2-lite**: Test performance with enterprise-scale databases (24 instances)
- [ ] Test TUI responsiveness and user experience
- [ ] Validate CLI parameter handling and help text
- [ ] Test SQL execution performance and accuracy across all three datasets
- [ ] Benchmark database switching overhead in Spider1 (20 databases) and Spider2-lite
- [ ] Validate configurable difficulty sampling maintains evaluation quality in Spider1

## Phase 7: Documentation and Future Planning

### 7.1 Documentation Updates
- [ ] Update README with new unified evaluation approach
- [ ] Document provider configuration and setup
- [ ] Create dataset addition guide for future datasets

### 7.2 Future Enhancement Planning
- [ ] Document web UI requirements and integration points
- [ ] Plan Ollama integration requirements
- [ ] Outline additional dataset integration roadmap

## Implementation Notes

### Critical Success Factors
- **WikiSQL**: Maintain existing evaluation accuracy and results
- **Spider1**: 500-example SLM-optimized evaluation with configurable difficulty distribution
- **Spider2-lite**: Handle enterprise-scale complexity without performance degradation
- **Unified Evaluation**: Consistent SQL execution matching across all datasets
- Preserve detailed logging for future analysis
- Keep CLI interface intuitive and powerful despite architectural differences
- Ensure easy provider switching for model comparison
- Eliminate external file dependencies while maintaining evaluation quality

### Risk Mitigation
- Implement changes incrementally with testing at each phase
- **Architecture Risk**: Spider1 and Spider2-lite's multi-database complexity requires careful abstraction
- **Scope Decision**: Spider1 uses 500-example sampling for SLM focus; Spider2-lite focuses on 24 instances with gold SQL
- **Sampling Risk**: Ensure 500-example Spider1 subset maintains diagnostic value across difficulty levels
- Maintain backward compatibility where possible
- Document migration path from current to new system
- Keep rollback options available during transition
- **Performance Risk**: Test SQL execution and multi-database switching under load

### Success Metrics
- **WikiSQL**: Unified evaluation script works with WikiSQL at same accuracy
- **Spider1**: 500-example evaluation provides comprehensive SLM skill gap identification across 20 domains
- **Spider2-lite**: SQL execution evaluation produces consistent results with 24 high-quality instances
- **Unified Interface**: Same tool use pattern works across all dataset architectures
- Provider switching works seamlessly across both architectures
- TUI provides clear, actionable feedback for both single/multi-database scenarios
- JSONL output supports rich analysis workflows with consistent SQL evaluation metrics
- Human-inspectable data enables easy debugging and analysis
- Spider1 configurable sampling enables quick difficulty distribution experimentation
- System ready for additional dataset integration (BIRD, etc.)

## Dependencies and Prerequisites
- Python 3.13.6+ environment
- LiteLLM for provider abstraction
- Rich library for TUI enhancement
- SQLite3 for database operations
- **JSON handling** for structured data storage and comparison
- Existing LM Studio setup for testing
- OpenRouter API access for frontier model testing

## Dataset-Specific Implementation Notes

### WikiSQL Implementation
**WikiSQL Implementation**
- **Single database approach**: Maintain existing connection pattern
- **Table switching**: Use existing `table_name` field for query targeting
- **Evaluation**: Continue SQL execution matching (EM/EX metrics)
- **Tool use**: Simple `execute_sql(query)` against single database
- **Performance**: Lightweight, optimized for speed

**Spider1 Implementation**
- **Multi-database approach**: Context-aware database switching across 20 dev databases
- **SLM-optimized sampling**: 500 examples with configurable difficulty distribution (15%/30%/35%/20%)
- **Enhanced schema context**: Rich prompts with data types and sample values from spider_schema_rows_v2.json
- **Evaluation**: SQL execution matching (EM/EX metrics) same as WikiSQL pattern
- **Tool use**: Context-aware `execute_sql(query)` with automatic database selection
- **Performance**: Balanced for comprehensive diagnostic coverage vs local evaluation speed
- **Configuration**: Easy modification of difficulty percentages for experimentation

**Spider2-lite Implementation**
- **Multi-database approach**: Database switching per question
- **Schema complexity**: Handle 35-352 tables per database
- **Evaluation**: **SQL execution matching (same as WikiSQL)**
- **Tool use**: Context-aware `execute_sql(query)` with automatic DB selection
- **External knowledge**: **Embedded in master database, injected via queries**
- **Expected results**: **Gold SQL execution matching, no CSV dependencies**
- **Performance**: Resource management for large schemas, connection pooling
- **Error handling**: Robust handling of complex multi-table query failures
- **Quality Focus**: 24 instances with verified gold SQL for reliable evaluation
