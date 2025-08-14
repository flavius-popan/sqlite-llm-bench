# Dataset Versioning System

This document describes the versioning system implemented in sqlite-llm-bench for managing dataset evolution, reproducibility, and compatibility.

## Overview

The versioning system provides:
- **Semantic versioning** (major.minor.patch) for clear change communication
- **Default to latest** for ease of use with explicit version override
- **Metadata-driven** approach with version info stored in SQLite databases
- **Content-based checksums** for integrity validation (excludes metadata table)
- **Automatic archiving** of previous versions
- **Compatibility validation** between dataset versions and evaluation code

## Architecture

### Directory Structure

```
datasets/
  _core/                             # Core dataset infrastructure
    __init__.py                      # Main API exports
    registry.py                      # Version management, loading
    cli.py                           # CLI command implementations
    testing.py                       # Test utilities
    loaders/                         # Dataset-specific loaders
      __init__.py
      wikisql.py                     # WikiSQL-specific functionality
      spider1.py                     # Future: Spider1 loader
  scripts/                           # Dataset build and management scripts
    build_wikisql_top500.py          # WikiSQL builder
    manage.py                        # Main CLI entry point
    test.py                          # Test runner
    demo.py                          # Interactive demonstration
  {dataset}/                         # Dataset files
    {dataset}-{variant}.db           # Latest version (e.g., wikisql-top500.db)
    metadata.json                    # Dataset configuration
    CHANGELOG.md                     # Version history
    versions/                        # Archived versions
      {dataset}-{variant}-v{X.Y.Z}.db
```

### Database Schema

Every dataset database contains a `dataset_metadata` table:

```sql
CREATE TABLE dataset_metadata (
    dataset_name TEXT NOT NULL,
    variant TEXT NOT NULL,
    version TEXT NOT NULL,              -- semantic version: "1.0.0"
    created_at TEXT NOT NULL,           -- ISO timestamp
    schema_version INTEGER NOT NULL,    -- for compatibility checks
    description TEXT,
    checksum TEXT,                      -- SHA256 of content (excluding metadata)
    parent_version TEXT,                -- previous version for lineage tracking
    breaking_changes BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (dataset_name, variant, version)
);
```

## Semantic Versioning Rules

### Version Components: `MAJOR.MINOR.PATCH`

- **MAJOR** (X.0.0): Breaking changes
  - Schema changes affecting evaluation code
  - Question set changes that alter benchmark difficulty
  - Evaluation methodology changes
  - Incompatible database structure changes

- **MINOR** (1.X.0): Backward-compatible additions
  - Additional questions within same difficulty range
  - Enhanced metadata without schema changes
  - New optional features or views
  - Performance improvements

- **PATCH** (1.1.X): Bug fixes and maintenance
  - Corrected question text or SQL
  - Updated descriptions or documentation
  - Fixed data quality issues
  - No functional evaluation changes

### Breaking Changes Detection

The system automatically detects breaking changes by comparing major version numbers:
- If `new_major > parent_major`: sets `breaking_changes = TRUE`
- Helps evaluation code determine compatibility requirements

## Usage Examples

### Basic Loading (Defaults to Latest)

```python
from datasets import load_dataset

# Load latest version
loader = load_dataset("wikisql", "top500")
questions = loader.get_questions(limit=10)
```

### Explicit Version Loading

```python
# Load specific version for reproducibility
loader = load_dataset("wikisql", "top500", version="1.0.0")

# Or using configuration object
from datasets import DatasetConfig
config = DatasetConfig(name="wikisql", variant="top500", version="1.2.0")
loader = load_dataset(config.name, config.variant, config.version)
```

### Version-Aware Evaluation Scripts

```python
from datasets import DatasetRegistry, DatasetConfig

registry = DatasetRegistry()
config = DatasetConfig(name="wikisql", variant="top500", version="latest")

# Validate compatibility before evaluation
db_path = registry.get_dataset_path(config)
if not registry.validate_version_compatibility(db_path, min_schema_version=1):
    raise ValueError("Dataset version incompatible with evaluation code")

loader = load_dataset(config.name, config.variant, config.version)
```

## CLI Tools

### Dataset Management CLI

```bash
# List all available datasets and versions
python datasets/scripts/manage.py list

# Show detailed information about a dataset
python datasets/scripts/manage.py show wikisql top500
python datasets/scripts/manage.py show wikisql top500 --version 1.0.0

# Validate dataset integrity
python datasets/scripts/manage.py validate wikisql top500
python datasets/scripts/manage.py validate wikisql top500 --verify-checksum

# Build new version with archiving
python datasets/scripts/manage.py build wikisql top500 --version 1.1.0 --archive-existing
```

### Build Scripts with Versioning

```bash
# Build with default version increment
python datasets/scripts/build_wikisql_top500.py

# Build with explicit version
python datasets/scripts/build_wikisql_top500.py --version 1.2.0

# Build with archiving of existing version
python datasets/scripts/build_wikisql_top500.py --version 1.1.0 --archive-existing
```

## Version Management Workflows

### Creating a New Version

1. **Archive existing version** (if making significant changes):
   ```bash
   python datasets/scripts/manage.py build wikisql top500 --version 1.1.0 --archive-existing
   ```

2. **Update CHANGELOG.md** with version details

3. **Validate new version**:
   ```bash
   python datasets/scripts/manage.py validate wikisql top500 --verify-checksum
   ```

### Version Planning Guidelines

- **Patch releases** (1.0.X): For bug fixes, documentation updates
- **Minor releases** (1.X.0): For adding questions, improving metadata
- **Major releases** (X.0.0): For schema changes, new evaluation methods

### Rollback Strategy

If a new version has issues:

```bash
# Check available versions
python datasets/scripts/manage.py list

# Copy archived version back to main location
cp datasets/wikisql/versions/wikisql-top500-v1.0.0.db datasets/wikisql/wikisql-top500.db

# Validate rollback
python datasets/scripts/manage.py validate wikisql top500
```

## Integrity and Validation

### Checksum System

- **Content-based**: Excludes `dataset_metadata` table to avoid circular dependency
- **Deterministic**: Uses sorted table schemas and data for consistent hashing
- **Validation**: Compare stored vs computed checksums to detect corruption

### Schema Compatibility

- `schema_version` field tracks database structure evolution
- Evaluation code specifies minimum required schema version
- Automatic compatibility validation prevents mismatched evaluation

### Validation Commands

```bash
# Basic validation
python datasets/scripts/manage.py validate wikisql top500

# Full validation with checksum verification
python datasets/scripts/manage.py validate wikisql top500 --verify-checksum

# Test programmatically
python datasets/scripts/test.py
```

## Migration from Legacy Datasets

For existing datasets without versioning metadata:

1. **Add metadata** to existing database:
   ```python
   from datasets import DatasetRegistry, create_dataset_version
   
   registry = DatasetRegistry()
   metadata = create_dataset_version(
       db_path=Path("datasets/wikisql/wikisql-top500.db"),
       dataset_name="wikisql",
       variant="top500", 
       version="1.0.0",
       description="Initial version with metadata migration"
   )
   registry.register_dataset(db_path, metadata)
   ```

2. **Rebuild with versioning** (recommended):
   ```bash
   python datasets/scripts/build_wikisql_top500.py --version 1.0.0
   ```

## Future Dataset Integration

When adding new datasets (Spider1, Spider2-lite, BIRD):

1. **Follow naming convention**: `{dataset}-{variant}.db`
2. **Include metadata table** in build scripts
3. **Create dataset configuration** in `metadata.json`
4. **Document version semantics** in dataset-specific CHANGELOG.md
5. **Implement dataset-specific loader** extending `DatasetLoader`

### Example for Spider1

```python
# Future spider1 loader
class Spider1Loader(DatasetLoader):
    def validate_schema(self) -> bool:
        # Spider1-specific validation
        pass
    
    def get_questions(self, limit=None) -> List[Dict]:
        # Multi-database question loading
        pass
```

## Best Practices

### For Dataset Creators

1. **Always use semantic versioning** when building datasets
2. **Archive before major changes** using `--archive-existing`
3. **Update CHANGELOG.md** with meaningful descriptions
4. **Validate integrity** after building: `--verify-checksum`
5. **Test compatibility** across evaluation scripts

### For Evaluation Scripts

1. **Default to latest** for normal usage: `load_dataset("wikisql", "top500")`
2. **Pin versions** for reproducible research: `version="1.0.0"`
3. **Validate compatibility** before evaluation starts
4. **Log dataset version** in evaluation results for traceability

### For Reproducibility

1. **Always log dataset version** in evaluation outputs
2. **Pin specific versions** in published research
3. **Archive critical versions** before major changes
4. **Document evaluation methodology** changes between versions

## Error Handling

Common issues and solutions:

### Dataset Not Found
```
❌ Dataset wikisql-top500 v2.0.0 not found
Available datasets: {'wikisql': {'top500': ['latest', '1.0.0', '1.1.0']}}
```
**Solution**: Check available versions with `python manage_datasets.py list`

### Version Incompatibility
```
❌ Dataset version incompatible with current evaluation code
Schema v0 < required v1
```
**Solution**: Update dataset or use compatible evaluation code version

### Checksum Mismatch
```
❌ Checksum mismatch - file may be corrupted
Expected: a1b2c3d4...
Actual:   e5f6g7h8...
```
**Solution**: Rebuild dataset or restore from archived version

## Implementation Notes

### Content-Based Checksums

The checksum system excludes the `dataset_metadata` table to avoid circular dependencies. This means:
- Checksums reflect actual dataset content and schema
- Metadata updates don't invalidate checksums
- Content integrity is preserved across metadata changes

### Version Resolution

The loader resolves versions as follows:
1. `"latest"` → `datasets/{name}/{name}-{variant}.db` (current)
2. `"X.Y.Z"` → `datasets/{name}/versions/{name}-{variant}-vX.Y.Z.db` (archived)

### Backward Compatibility

- Legacy databases without metadata are **not supported** by default
- Use migration workflow or rebuild with versioning for legacy datasets
- Evaluation scripts should validate version compatibility before proceeding

## Testing

Run the comprehensive test suite:

```bash
python datasets/scripts/test.py
```

Or run the interactive demonstration:

```bash
python datasets/scripts/demo.py
```

The test suite validates:
- Installation and imports
- Version-agnostic loading (defaults to latest)
- Explicit version specification
- Version comparison and consistency
- Registry utility functions
- Dataset-specific features
- SQL execution capabilities
- Integrity validation
- CLI tool integration

---

*This versioning system follows best practices from ML benchmarking communities including Hugging Face Datasets, LM Evaluation Harness, and HELM, adapted for SQLite-based text-to-SQL evaluation.*