"""
Dataset loaders for different benchmark types.

This module provides specialized loaders for each supported dataset type,
all extending the base DatasetLoader class with dataset-specific functionality.
"""

from .wikisql import WikiSQLLoader, WikiSQLQuestion, WikiSQLTable, load_wikisql

__all__ = [
    "WikiSQLLoader",
    "WikiSQLQuestion",
    "WikiSQLTable",
    "load_wikisql"
]
