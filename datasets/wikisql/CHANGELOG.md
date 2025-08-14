# Changelog

All notable changes to the WikiSQL dataset will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2025-01-20

### Added
- Initial WikiSQL Top-500 dataset with curated high-complexity questions
- Difficulty scoring based on condition count, operator rarity, aggregation complexity
- Cleaned human-readable column names derived from original headers
- Complete table metadata with page titles, sections, and captions
- Gold SQL queries with execution validation
- Dataset versioning infrastructure with metadata table
- Single SQLite database containing 500 questions across ~450 tables

### Schema
- `questions` table: question text, gold SQL, difficulty scores, table references
- `wikisql_tables` table: table metadata, headers, types, page information
- `v_top500_questions` view: human-readable question overview
- `dataset_metadata` table: version tracking and compatibility information
- Individual data tables with sanitized column names for each WikiSQL table

### Evaluation
- SQL execution matching (EM/EX metrics)
- Tool-based evaluation using `execute_sql` function
- Single database connection model
- Normalized SQL comparison for exact matching

### Notes
- Derived from WikiSQL dataset (MIT license)
- Questions selected via difficulty ranking algorithm
- Validated against original WikiSQL split databases
- Optimized for local SLM evaluation scenarios