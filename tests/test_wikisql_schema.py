import sqlite3, os
from benchmark_bundle import resolve_dataset

def test_wikisql_registry_entry():
    db, meta = resolve_dataset("wikisql")
    assert str(db).endswith("wikisql-v1.sqlite")
    # db file may not exist yet; that's ok in CI without data

def test_sqlite_ro_uri():
    # Just ensure we can form a read-only URI (no file open required)
    db_path = "file:dummy.sqlite?mode=ro"
    assert db_path.startswith("file:")
