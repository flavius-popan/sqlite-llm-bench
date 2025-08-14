"""
Dataset registry and version management for sqlite-llm-bench.

This module provides a unified interface for loading and managing versioned datasets
across different benchmark types (WikiSQL, Spider1, Spider2-lite, etc.).

Key features:
- Semantic versioning (major.minor.patch) with metadata storage
- Default to latest version with explicit override capability
- Version compatibility validation
- Dataset discovery and configuration management
"""

import json
import sqlite3
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
import shutil


@dataclass
class DatasetVersion:
    """Metadata for a dataset version."""
    dataset_name: str
    variant: str
    version: str  # semantic version: "1.0.0"
    created_at: str  # ISO format timestamp
    schema_version: int
    description: str
    checksum: str  # SHA256 of database content
    parent_version: Optional[str] = None  # for tracking lineage
    breaking_changes: bool = False  # major version indicator

    @property
    def major(self) -> int:
        return int(self.version.split('.')[0])

    @property
    def minor(self) -> int:
        return int(self.version.split('.')[1])

    @property
    def patch(self) -> int:
        return int(self.version.split('.')[2])


@dataclass
class DatasetConfig:
    """Configuration for dataset loading."""
    name: str
    variant: str = "default"
    version: str = "latest"
    require_tools: bool = True
    evaluation_mode: str = "execution_match"  # "execution_match", "exact_match"

    def __post_init__(self):
        # Normalize common variant names
        variant_aliases = {
            "top500": "top500",
            "dev": "dev",
            "test": "test",
            "mini": "mini",
            "default": self._get_default_variant()
        }
        self.variant = variant_aliases.get(self.variant, self.variant)

    def _get_default_variant(self) -> str:
        """Get default variant for each dataset."""
        defaults = {
            "wikisql": "top500",
            "spider1": "dev",
            "spider2_lite": "dev",
            "bird": "mini"
        }
        return defaults.get(self.name, "default")


class DatasetRegistry:
    """Central registry for managing versioned datasets."""

    def __init__(self, datasets_root: Path = None):
        self.datasets_root = datasets_root or Path("datasets")
        self.datasets_root.mkdir(exist_ok=True)

    def get_dataset_path(self, config: DatasetConfig) -> Path:
        """Resolve dataset path based on configuration."""
        dataset_dir = self.datasets_root / config.name

        if config.version == "latest":
            # Return the main database file (latest version)
            return dataset_dir / f"{config.name}-{config.variant}.db"
        else:
            # Return specific archived version
            versions_dir = dataset_dir / "versions"
            return versions_dir / f"{config.name}-{config.variant}-v{config.version}.db"

    def get_available_versions(self, dataset_name: str, variant: str) -> List[str]:
        """Get all available versions for a dataset variant."""
        dataset_dir = self.datasets_root / dataset_name
        versions_dir = dataset_dir / "versions"

        if not versions_dir.exists():
            return []

        versions = []
        pattern = f"{dataset_name}-{variant}-v*.db"
        for file_path in versions_dir.glob(pattern):
            # Extract version from filename
            version_part = file_path.stem.split('-v')[-1]
            versions.append(version_part)

        return sorted(versions, key=lambda v: tuple(map(int, v.split('.'))))

    def get_latest_version(self, dataset_name: str, variant: str) -> Optional[str]:
        """Get the latest version string for a dataset variant."""
        versions = self.get_available_versions(dataset_name, variant)
        return versions[-1] if versions else None

    def register_dataset(self, db_path: Path, metadata: DatasetVersion) -> None:
        """Register a new dataset version with metadata."""
        # Ensure the database has the metadata table
        self._ensure_metadata_table(db_path)

        # Insert version metadata
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO dataset_metadata
                (dataset_name, variant, version, created_at, schema_version,
                 description, checksum, parent_version, breaking_changes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.dataset_name, metadata.variant, metadata.version,
                metadata.created_at, metadata.schema_version, metadata.description,
                metadata.checksum, metadata.parent_version, metadata.breaking_changes
            ))
            conn.commit()

    def get_dataset_metadata(self, db_path: Path) -> Optional[DatasetVersion]:
        """Retrieve metadata for a dataset from its database."""
        if not db_path.exists():
            return None

        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute("SELECT * FROM dataset_metadata LIMIT 1")
                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    data = dict(zip(columns, row))
                    return DatasetVersion(**data)
        except sqlite3.OperationalError:
            # Table doesn't exist - legacy database
            return None
        return None

    def validate_version_compatibility(self, db_path: Path, min_schema_version: int = 1) -> bool:
        """Validate that dataset version is compatible with current evaluation code."""
        metadata = self.get_dataset_metadata(db_path)
        if not metadata:
            return False  # No metadata = incompatible
        return metadata.schema_version >= min_schema_version

    def create_version_archive(self, current_path: Path, new_version: str) -> Path:
        """Archive current version before creating new one."""
        metadata = self.get_dataset_metadata(current_path)
        if not metadata:
            raise ValueError(f"Cannot archive {current_path}: no metadata found")

        # Create versions directory
        versions_dir = current_path.parent / "versions"
        versions_dir.mkdir(exist_ok=True)

        # Archive current version
        archive_name = f"{metadata.dataset_name}-{metadata.variant}-v{metadata.version}.db"
        archive_path = versions_dir / archive_name

        if not archive_path.exists():
            shutil.copy2(current_path, archive_path)

        return archive_path

    def compute_database_checksum(self, db_path: Path) -> str:
        """Compute SHA256 checksum of database content (excluding metadata table)."""
        sha256_hash = hashlib.sha256()

        with sqlite3.connect(db_path) as conn:
            # Get all tables except dataset_metadata for content hashing
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name != 'dataset_metadata'
                ORDER BY name
            """)
            tables = [row[0] for row in cursor.fetchall()]

            # Hash table schemas and data
            for table_name in tables:
                # Hash table schema
                cursor = conn.execute(f"SELECT sql FROM sqlite_master WHERE name = ?", (table_name,))
                schema = cursor.fetchone()[0]
                sha256_hash.update(schema.encode('utf-8'))

                # Hash table data (sorted for consistency)
                try:
                    cursor = conn.execute(f"SELECT * FROM {table_name} ORDER BY 1")
                    for row in cursor.fetchall():
                        row_str = '|'.join(str(x) if x is not None else 'NULL' for x in row)
                        sha256_hash.update(row_str.encode('utf-8'))
                except sqlite3.OperationalError:
                    # Skip tables that can't be ordered
                    cursor = conn.execute(f"SELECT * FROM {table_name}")
                    for row in cursor.fetchall():
                        row_str = '|'.join(str(x) if x is not None else 'NULL' for x in row)
                        sha256_hash.update(row_str.encode('utf-8'))

        return sha256_hash.hexdigest()

    def _ensure_metadata_table(self, db_path: Path) -> None:
        """Ensure the database has the dataset_metadata table."""
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dataset_metadata (
                    dataset_name TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    description TEXT,
                    checksum TEXT,
                    parent_version TEXT,
                    breaking_changes BOOLEAN DEFAULT FALSE,
                    PRIMARY KEY (dataset_name, variant, version)
                )
            """)
            conn.commit()

    def list_datasets(self) -> Dict[str, Dict[str, List[str]]]:
        """List all available datasets, variants, and versions."""
        datasets = {}

        for dataset_dir in self.datasets_root.iterdir():
            if not dataset_dir.is_dir():
                continue

            dataset_name = dataset_dir.name

            # Skip internal directories
            if dataset_name.startswith('_') or dataset_name == 'scripts':
                continue

            datasets[dataset_name] = {}

            # Find all variant databases
            for db_file in dataset_dir.glob("*.db"):
                if db_file.stem.startswith(f"{dataset_name}-"):
                    variant = db_file.stem.replace(f"{dataset_name}-", "")
                    versions = self.get_available_versions(dataset_name, variant)

                    # Add current/latest version
                    if db_file.exists():
                        versions.append("latest")

                    datasets[dataset_name][variant] = versions

        return datasets


class DatasetLoader:
    """Base class for loading specific dataset types."""

    def __init__(self, db_path: Path, registry: DatasetRegistry = None):
        self.db_path = db_path
        self.registry = registry or DatasetRegistry()
        self.metadata = self.registry.get_dataset_metadata(db_path)

        if not self.metadata:
            raise ValueError(f"Dataset at {db_path} has no metadata. Run migration first.")

    def get_connection(self) -> sqlite3.Connection:
        """Get a connection to the dataset database."""
        return sqlite3.connect(self.db_path)

    def get_questions(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get questions from the dataset. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement get_questions")

    def validate_schema(self) -> bool:
        """Validate that the database schema matches expectations."""
        raise NotImplementedError("Subclasses must implement validate_schema")


# Convenience functions for common operations
def load_dataset(name: str, variant: str = None, version: str = "latest",
                datasets_root: Path = None) -> DatasetLoader:
    """
    Load a dataset with automatic type detection and version resolution.

    Args:
        name: Dataset name ("wikisql", "spider1", "spider2_lite", "bird")
        variant: Dataset variant (None = default for dataset type)
        version: Version to load ("latest" or semantic version like "1.0.0")
        datasets_root: Root directory for datasets (default: "datasets")

    Returns:
        Appropriate DatasetLoader subclass instance
    """
    # Create configuration with defaults
    config = DatasetConfig(name=name, version=version)
    if variant:
        config.variant = variant

    registry = DatasetRegistry(datasets_root)
    db_path = registry.get_dataset_path(config)

    if not db_path.exists():
        available = registry.list_datasets()
        raise FileNotFoundError(
            f"Dataset {name}-{config.variant} v{version} not found at {db_path}\n"
            f"Available datasets: {available}"
        )

    # Validate compatibility
    if not registry.validate_version_compatibility(db_path):
        raise ValueError(f"Dataset {db_path} is incompatible with current evaluation code")

    # Return appropriate loader based on dataset type
    if name == "wikisql":
        return WikiSQLLoader(db_path, registry)
    elif name == "spider1":
        return Spider1Loader(db_path, registry)
    elif name == "spider2_lite":
        return Spider2LiteLoader(db_path, registry)
    else:
        return DatasetLoader(db_path, registry)


def create_dataset_version(db_path: Path, dataset_name: str, variant: str,
                          version: str, description: str,
                          parent_version: str = None, breaking_changes: bool = False) -> DatasetVersion:
    """
    Create version metadata for a dataset.

    Args:
        db_path: Path to the database file
        dataset_name: Name of the dataset
        variant: Dataset variant (e.g., "top500", "dev")
        version: Semantic version string (e.g., "1.0.0")
        description: Human-readable description of this version
        parent_version: Previous version this is based on
        breaking_changes: Whether this version has breaking changes

    Returns:
        DatasetVersion metadata object
    """
    registry = DatasetRegistry()
    checksum = registry.compute_database_checksum(db_path)

    return DatasetVersion(
        dataset_name=dataset_name,
        variant=variant,
        version=version,
        created_at=datetime.now().isoformat(),
        schema_version=1,  # Current schema version
        description=description,
        checksum=checksum,
        parent_version=parent_version,
        breaking_changes=breaking_changes
    )


# Dataset-specific loaders
class WikiSQLLoader(DatasetLoader):
    """Loader for WikiSQL datasets."""

    def validate_schema(self) -> bool:
        """Validate WikiSQL-specific schema requirements."""
        required_tables = ["questions", "wikisql_tables", "dataset_metadata"]
        required_question_columns = [
            "uid", "question", "gold_sql", "table_name", "difficulty_score"
        ]

        with self.get_connection() as conn:
            # Check tables exist
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            for table in required_tables:
                if table not in tables:
                    return False

            # Check question table structure
            cursor = conn.execute("PRAGMA table_info(questions)")
            columns = [row[1] for row in cursor.fetchall()]

            for col in required_question_columns:
                if col not in columns:
                    return False

            return True

    def get_questions(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get questions from WikiSQL dataset."""
        query = "SELECT * FROM questions ORDER BY difficulty_score DESC"

        if limit:
            query += f" LIMIT {limit}"

        with self.get_connection() as conn:
            cursor = conn.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            questions = []
            for row in rows:
                questions.append(dict(zip(columns, row)))

            return questions


class Spider1Loader(DatasetLoader):
    """Loader for Spider1 datasets."""
    pass

class Spider2LiteLoader(DatasetLoader):
    """Loader for Spider2-lite datasets."""
    pass
