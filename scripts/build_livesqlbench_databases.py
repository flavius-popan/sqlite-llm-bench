#!/usr/bin/env python3
"""
Build LiveSQLBench databases from HuggingFace dataset clone.

This script:
  1) Reads schema files from data/raw/bird_livesqlbench/
  2) Parses CREATE TABLE statements and embedded sample data
  3) Creates populated SQLite databases in data/processed/bird_livesqlbench/
  4) Validates databases against gold SQL queries

The schema files contain both table definitions and columnar sample data:
CREATE TABLE "table_name" (
    column definitions...
);
First 3 rows:
header_row
data_row_1 with space/tab separated values
data_row_2 with space/tab separated values
...

Usage:
  python scripts/build_livesqlbench_databases.py
  python scripts/build_livesqlbench_databases.py --database alien --validate
"""

import re
import sqlite3
import argparse
import json
from pathlib import Path
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw" / "bird_livesqlbench"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed" / "bird_livesqlbench"


class DatabaseBuilder:
    def __init__(self, source_dir: Path):
        self.source_dir = Path(source_dir)

    def parse_schema_file(self, schema_path: Path) -> List[Dict[str, Any]]:
        """Parse a schema file into table definitions and data."""
        logger.info(f"Parsing schema file: {schema_path}")

        with open(schema_path, 'r', encoding='utf-8') as f:
            content = f.read()

        tables = []
        current_table = None
        current_sql = []
        current_data = []
        in_data_section = False

        lines = content.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if line.startswith('CREATE TABLE'):
                # Save previous table if exists
                if current_table:
                    tables.append(self._finalize_table(current_table, current_sql, current_data))

                # Start new table
                current_table = self._extract_table_name(line)
                current_sql = [line]
                current_data = []
                in_data_section = False

            elif line.startswith('First 3 rows:') or line.startswith('First '):
                # End of CREATE TABLE, start of data section
                in_data_section = True

            elif in_data_section:
                if line and not line.startswith('...') and line != '':
                    current_data.append(line)
                elif line.startswith('...') or line == '':
                    # End of data section for this table
                    in_data_section = False

            elif current_table and not in_data_section:
                # Still building CREATE TABLE statement
                current_sql.append(line)

            i += 1

        # Add final table
        if current_table:
            tables.append(self._finalize_table(current_table, current_sql, current_data))

        logger.info(f"Parsed {len(tables)} tables from {schema_path}")
        return tables

    def _extract_table_name(self, create_line: str) -> str:
        """Extract table name from CREATE TABLE statement."""
        # Handle both quoted and unquoted table names
        match = re.search(r'CREATE TABLE\s+["`]?(\w+)["`]?\s*\(', create_line, re.IGNORECASE)
        if match:
            return match.group(1)
        else:
            raise ValueError(f"Could not extract table name from: {create_line}")

    def _finalize_table(self, table_name: str, sql_lines: List[str], data_lines: List[str]) -> Dict[str, Any]:
        """Finalize a table definition with proper SQL and parsed data."""
        # Clean up SQL - ensure it ends with );
        clean_sql = []
        for line in sql_lines:
            if line.strip() and not line.startswith('First'):
                clean_sql.append(line)

        # Ensure proper closing
        if clean_sql and not clean_sql[-1].strip().endswith(');'):
            if clean_sql[-1].strip().endswith(','):
                clean_sql[-1] = clean_sql[-1].rstrip(',')
            clean_sql.append(');')

        sql = '\n'.join(clean_sql)

        # Parse data if available
        columns = []
        rows = []

        if data_lines:
            # First line should be headers
            if data_lines:
                header_line = data_lines[0]
                columns = self._parse_header_line(header_line)

                # Remaining lines are data
                for data_line in data_lines[1:]:
                    if data_line.strip() and not data_line.startswith('...'):
                        row = self._parse_data_line(data_line, len(columns))
                        if row:
                            rows.append(row)

        return {
            'name': table_name,
            'sql': sql,
            'columns': columns,
            'rows': rows
        }

    def _parse_header_line(self, header_line: str) -> List[str]:
        """Parse the header line to extract column names."""
        # The header line appears to be columnar with fixed-width spacing
        # We'll split by multiple spaces to preserve column names that contain single spaces
        import re
        # Split on 2+ consecutive spaces
        parts = re.split(r'\s{2,}', header_line.strip())
        return [part.strip() for part in parts if part.strip()]

    def _parse_data_line(self, data_line: str, expected_columns: int) -> List[Any]:
        """Parse a data line into values using columnar alignment."""
        import re

        # First try splitting on 2+ consecutive spaces (same as header)
        parts = re.split(r'\s{2,}', data_line.strip())

        # If we don't get the expected number of columns, try alternative parsing
        if len(parts) != expected_columns:
            # Try tab-separated
            if '\t' in data_line:
                parts = data_line.strip().split('\t')
            else:
                # Fall back to single space split with reassembly
                space_parts = data_line.strip().split()
                if len(space_parts) > expected_columns:
                    # Take first expected_columns-1 parts, then join the rest
                    parts = space_parts[:expected_columns-1]
                    parts.append(' '.join(space_parts[expected_columns-1:]))
                else:
                    parts = space_parts

        # Pad with None if we still have too few parts
        while len(parts) < expected_columns:
            parts.append(None)

        # Truncate if we have too many parts
        parts = parts[:expected_columns]

        # Convert values
        converted = []
        for part in parts:
            if part is None or part == '' or part.upper() == 'NULL':
                converted.append(None)
            else:
                part = part.strip()
                # Try to convert to appropriate type
                try:
                    # Try integer first
                    if '.' not in part and part.replace('-', '').replace('+', '').isdigit():
                        converted.append(int(part))
                    # Try float
                    elif part.replace('-', '').replace('+', '').replace('.', '').isdigit():
                        converted.append(float(part))
                    else:
                        # Keep as string
                        converted.append(part)
                except ValueError:
                    converted.append(part)

        return converted

    def build_database(self, db_name: str, output_path: Path) -> bool:
        """Build a complete database from schema file."""
        schema_file = self.source_dir / db_name / f"{db_name}_schema.txt"

        if not schema_file.exists():
            logger.error(f"Schema file not found: {schema_file}")
            return False

        try:
            # Parse schema
            tables = self.parse_schema_file(schema_file)

            # Create database
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Remove existing database if it exists
            if output_path.exists():
                output_path.unlink()

            conn = sqlite3.connect(str(output_path))

            try:
                # Create tables and insert data
                for table in tables:
                    logger.info(f"Creating table: {table['name']}")

                    # Create table
                    conn.execute(table['sql'])

                    # Insert data if available
                    if table['rows'] and table['columns']:
                        placeholders = ','.join(['?' for _ in table['columns']])
                        insert_sql = f"INSERT INTO \"{table['name']}\" VALUES ({placeholders})"

                        logger.info(f"Inserting {len(table['rows'])} rows into {table['name']}")
                        conn.executemany(insert_sql, table['rows'])

                conn.commit()

                # Verify database
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                db_tables = [row[0] for row in cursor.fetchall()]
                logger.info(f"Database created with tables: {db_tables}")

                # Show row counts
                for table_name in db_tables:
                    cursor = conn.execute(f"SELECT COUNT(*) FROM \"{table_name}\"")
                    count = cursor.fetchone()[0]
                    logger.info(f"Table {table_name}: {count} rows")

                return True

            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Error building database {db_name}: {e}")
            if output_path.exists():
                output_path.unlink()
            return False

    def build_all_databases(self, output_dir: Path) -> Dict[str, bool]:
        """Build all databases found in the source directory."""
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {}

        # Find all database directories
        for item in self.source_dir.iterdir():
            if item.is_dir() and (item / f"{item.name}_schema.txt").exists():
                db_name = item.name
                output_path = output_dir / f"{db_name}.sqlite"

                logger.info(f"Building database: {db_name}")
                success = self.build_database(db_name, output_path)
                results[db_name] = success

                if success:
                    logger.info(f"✓ Successfully built {db_name}.sqlite")
                else:
                    logger.error(f"✗ Failed to build {db_name}.sqlite")

        return results

    def validate_databases(self, db_dir: Path, gt_file: Path) -> Dict[str, bool]:
        """Validate databases against gold SQL queries."""
        if not gt_file.exists():
            logger.warning(f"Ground truth file not found: {gt_file}")
            return {}

        logger.info(f"Validating databases against {gt_file}")

        # Load ground truth data
        with open(gt_file, 'r') as f:
            gt_data = [json.loads(line) for line in f]

        results = {}

        for example in gt_data[:10]:  # Test first 10 examples
            instance_id = example['instance_id']
            db_name = instance_id.split('_')[0]  # Extract db name from instance_id

            if db_name not in results:
                results[db_name] = {'tested': 0, 'passed': 0}

            results[db_name]['tested'] += 1

            db_path = db_dir / f"{db_name}.sqlite"
            if not db_path.exists():
                logger.error(f"Database not found: {db_path}")
                continue

            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.execute(example['sol_sql'][0])
                result = cursor.fetchall()
                conn.close()

                results[db_name]['passed'] += 1
                logger.debug(f"✓ Query {instance_id}: {len(result)} rows")

            except Exception as e:
                logger.error(f"✗ Query {instance_id} failed: {e}")

        # Print validation summary
        logger.info("Validation Summary:")
        for db_name, stats in results.items():
            success_rate = stats['passed'] / stats['tested'] * 100
            logger.info(f"  {db_name}: {stats['passed']}/{stats['tested']} ({success_rate:.1f}%)")

        return results


def main():
    parser = argparse.ArgumentParser(description='Build SQLite databases from LiveSQLBench HuggingFace dataset')
    parser.add_argument('--source', '-s', type=Path, default=RAW_DATA_DIR,
                       help=f'Source directory (default: {RAW_DATA_DIR})')
    parser.add_argument('--output', '-o', type=Path, default=PROCESSED_DATA_DIR,
                       help=f'Output directory (default: {PROCESSED_DATA_DIR})')
    parser.add_argument('--database', '-d', type=str,
                       help='Build specific database only')
    parser.add_argument('--validate', action='store_true',
                       help='Validate databases against ground truth queries')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Verify source directory exists
    if not args.source.exists():
        logger.error(f"Source directory not found: {args.source}")
        logger.error("Please run: git clone https://huggingface.co/datasets/birdsql/livesqlbench-base-lite-sqlite data/raw/bird_livesqlbench")
        return 1

    builder = DatabaseBuilder(args.source)

    if args.database:
        # Build single database
        output_path = args.output / f"{args.database}.sqlite"
        success = builder.build_database(args.database, output_path)

        if success:
            print(f"✓ Successfully built {args.database}.sqlite")
        else:
            print(f"✗ Failed to build {args.database}.sqlite")
            return 1
    else:
        # Build all databases
        results = builder.build_all_databases(args.output)

        successful = sum(1 for success in results.values() if success)
        total = len(results)

        print(f"\nBuild Results: {successful}/{total} databases built successfully")

        for db_name, success in results.items():
            status = "✓" if success else "✗"
            print(f"{status} {db_name}")

        if successful < total:
            return 1

    # Validation step
    if args.validate:
        gt_file = args.source / "livesqlbench_sqlite_gt_kg_testcases_0528.jsonl"
        if gt_file.exists():
            validation_results = builder.validate_databases(args.output, gt_file)

            if validation_results:
                total_tested = sum(stats['tested'] for stats in validation_results.values())
                total_passed = sum(stats['passed'] for stats in validation_results.values())
                print(f"\nValidation Results: {total_passed}/{total_tested} queries passed")
            else:
                print("\nValidation skipped: no ground truth data")
        else:
            logger.warning(f"Ground truth file not found: {gt_file}")

    return 0


if __name__ == '__main__':
    exit(main())
