"""
SQLite LLM Bench Datasets Module

This module provides a unified interface for loading and managing versioned datasets
across different benchmark types (WikiSQL, Spider1, Spider2-lite, etc.).

Main API:
    load_dataset(name, variant="default", version="latest") -> DatasetLoader
    DatasetConfig(name, variant, version)
    DatasetRegistry() for advanced version management

Example usage:
    from datasets import load_dataset

    # Load latest version (typical usage)
    loader = load_dataset("wikisql", "top500")
    questions = loader.get_questions(limit=10)

    # Load specific version (reproducible research)
    loader = load_dataset("wikisql", "top500", version="1.0.0")

    # Advanced configuration
    from datasets import DatasetConfig
    config = DatasetConfig(name="wikisql", variant="top500", version="latest")
    loader = load_dataset(config.name, config.variant, config.version)
"""

from ._core.registry import (
    DatasetRegistry,
    DatasetConfig,
    DatasetVersion,
    DatasetLoader,
    load_dataset,
    create_dataset_version
)

from ._core.loaders.wikisql import (
    WikiSQLLoader,
    WikiSQLQuestion,
    WikiSQLTable,
    load_wikisql
)

# Main API exports
__all__ = [
    # Core loading functions (most commonly used)
    "load_dataset",

    # Configuration classes
    "DatasetConfig",
    "DatasetVersion",

    # Advanced registry management
    "DatasetRegistry",
    "DatasetLoader",
    "create_dataset_version",

    # WikiSQL-specific functionality
    "WikiSQLLoader",
    "WikiSQLQuestion",
    "WikiSQLTable",
    "load_wikisql"
]

# Version info
__version__ = "1.0.0"
