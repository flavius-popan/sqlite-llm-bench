#!/usr/bin/env python3

import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

def hash_db_content(db_path):
    with open(db_path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def run_build():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        temp_path = tmp.name

    result = subprocess.run([
        sys.executable, "datasets/scripts/build_wikisql_top500.py", "--out", temp_path
    ], capture_output=True, cwd=Path(__file__).parent.parent)

    if result.returncode != 0:
        Path(temp_path).unlink()
        print(f"Build failed: {result.stderr.decode()}")
        sys.exit(1)

    db_hash = hash_db_content(temp_path)
    Path(temp_path).unlink()
    return db_hash

def validate_deterministic(iterations=3):
    print(f"Running {iterations} builds...")
    hashes = []

    for i in range(iterations):
        print(f"Build {i+1}/{iterations}")
        file_hash = run_build()
        hashes.append(file_hash)
        print(f"  Hash: {file_hash}")

    if len(set(hashes)) == 1:
        print(f"\n✓ All builds identical: {hashes[0]}")
        return True
    else:
        print(f"\n✗ NOT deterministic! {len(set(hashes))} different hashes")
        return False

if __name__ == "__main__":
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    sys.exit(0 if validate_deterministic(iterations) else 1)
