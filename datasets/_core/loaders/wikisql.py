"""
WikiSQL-specific dataset loader with versioning support.

This module provides a specialized loader for WikiSQL datasets that handles:
- Single database with multiple tables
- Tool-based SQL execution
- Difficulty scoring and question ranking
- Human-readable column names
- Version compatibility checking
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from ..registry import DatasetLoader, DatasetRegistry, DatasetConfig


@dataclass
class WikiSQLQuestion:
    """A single WikiSQL question with metadata."""
    uid: int
    split: str
    table_id: str
    table_name: str
    question: str
    gold_sql: str
    difficulty_score: float
    expected_rows: float
    n_rows: int
    n_cols: int
    agg: int
    sel: int
    conds_json: str
    q_words: int
    cond_count: int
    op_rarity_sum: float
    has_agg: int
    agg_rarity: float

    @property
    def conditions(self) -> List[List[Any]]:
        """Parse conditions from JSON."""
        return json.loads(self.conds_json)

    @property
    def has_aggregation(self) -> bool:
        """Check if question requires aggregation."""
        return self.agg != 0

    @property
    def complexity_level(self) -> str:
        """Categorize question complexity based on difficulty score."""
        if self.difficulty_score >= 15:
            return "very_hard"
        elif self.difficulty_score >= 10:
            return "hard"
        elif self.difficulty_score >= 5:
            return "medium"
        else:
            return "easy"


@dataclass
class WikiSQLTable:
    """Metadata for a WikiSQL table."""
    split: str
    table_id: str
    header_json: str
    types_json: str
    clean_colnames_json: str
    page_title: str
    section_title: str
    caption: str
    page_id: int
    n_rows: int
    n_cols: int

    @property
    def headers(self) -> List[str]:
        """Get original column headers."""
        return json.loads(self.header_json)

    @property
    def types(self) -> List[str]:
        """Get column types."""
        return json.loads(self.types_json)

    @property
    def clean_column_names(self) -> List[str]:
        """Get human-readable column names."""
        return json.loads(self.clean_colnames_json)

    def get_schema_info(self) -> Dict[str, Any]:
        """Get comprehensive schema information for prompting."""
        return {
            "table_name": f"table_{self.table_id.replace('-', '_')}",
            "columns": [
                {
                    "name": clean_name,
                    "original_header": header,
                    "type": col_type
                }
                for clean_name, header, col_type in zip(
                    self.clean_column_names, self.headers, self.types
                )
            ],
            "row_count": self.n_rows,
            "context": {
                "page_title": self.page_title,
                "section_title": self.section_title,
                "caption": self.caption
            }
        }


class WikiSQLLoader(DatasetLoader):
    """Specialized loader for WikiSQL datasets."""

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

    def get_questions(self, limit: Optional[int] = None,
                     complexity_filter: Optional[str] = None,
                     split_filter: Optional[str] = None) -> List[WikiSQLQuestion]:
        """
        Get questions from WikiSQL dataset.

        Args:
            limit: Maximum number of questions to return
            complexity_filter: Filter by complexity level ("easy", "medium", "hard", "very_hard")
            split_filter: Filter by split ("train", "dev", "test")

        Returns:
            List of WikiSQLQuestion objects
        """
        query = "SELECT * FROM questions"
        params = []

        # Build WHERE clause
        conditions = []

        if split_filter:
            conditions.append("split = ?")
            params.append(split_filter)

        if complexity_filter:
            score_ranges = {
                "easy": (0, 5),
                "medium": (5, 10),
                "hard": (10, 15),
                "very_hard": (15, float('inf'))
            }
            if complexity_filter in score_ranges:
                min_score, max_score = score_ranges[complexity_filter]
                if max_score == float('inf'):
                    conditions.append("difficulty_score >= ?")
                    params.append(min_score)
                else:
                    conditions.append("difficulty_score >= ? AND difficulty_score < ?")
                    params.extend([min_score, max_score])

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY difficulty_score DESC"

        if limit:
            query += f" LIMIT {limit}"

        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            questions = []
            for row in rows:
                data = dict(zip(columns, row))
                questions.append(WikiSQLQuestion(**data))

            return questions

    def get_table_metadata(self, table_id: str, split: str) -> Optional[WikiSQLTable]:
        """Get metadata for a specific table."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM wikisql_tables WHERE table_id = ? AND split = ?",
                (table_id, split)
            )
            row = cursor.fetchone()

            if row:
                columns = [desc[0] for desc in cursor.description]
                data = dict(zip(columns, row))
                return WikiSQLTable(**data)

            return None

    def get_all_tables(self) -> List[WikiSQLTable]:
        """Get metadata for all tables in the dataset."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM wikisql_tables ORDER BY n_rows DESC")
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            tables = []
            for row in rows:
                data = dict(zip(columns, row))
                tables.append(WikiSQLTable(**data))

            return tables

    def get_table_names(self) -> List[str]:
        """Get all table names available for SQL execution."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'table_%'"
            )
            return [row[0] for row in cursor.fetchall()]

    def execute_sql(self, sql: str) -> Tuple[bool, Optional[List[List[Any]]], Optional[str]]:
        """
        Execute SQL against the WikiSQL database.

        Args:
            sql: SQL query to execute

        Returns:
            Tuple of (success, results, error_message)
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(sql)
                results = cursor.fetchall()
                return True, results, None
        except Exception as e:
            return False, None, str(e)

    def get_question_with_context(self, uid: int) -> Optional[Dict[str, Any]]:
        """Get a question with full context including table schema."""
        questions = self.get_questions()
        question = next((q for q in questions if q.uid == uid), None)

        if not question:
            return None

        table_meta = self.get_table_metadata(question.table_id, question.split)
        if not table_meta:
            return None

        return {
            "question": question,
            "table_meta": table_meta,
            "schema_info": table_meta.get_schema_info(),
            "available_tables": [question.table_name]
        }

    def get_dataset_stats(self) -> Dict[str, Any]:
        """Get comprehensive dataset statistics."""
        with self.get_connection() as conn:
            stats = {}

            # Basic counts
            cursor = conn.execute("SELECT COUNT(*) FROM questions")
            stats["total_questions"] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM wikisql_tables")
            stats["total_tables"] = cursor.fetchone()[0]

            # Complexity distribution
            cursor = conn.execute("""
                SELECT
                    CASE
                        WHEN difficulty_score >= 15 THEN 'very_hard'
                        WHEN difficulty_score >= 10 THEN 'hard'
                        WHEN difficulty_score >= 5 THEN 'medium'
                        ELSE 'easy'
                    END as complexity,
                    COUNT(*) as count
                FROM questions
                GROUP BY complexity
            """)
            stats["complexity_distribution"] = dict(cursor.fetchall())

            # Split distribution
            cursor = conn.execute("SELECT split, COUNT(*) FROM questions GROUP BY split")
            stats["split_distribution"] = dict(cursor.fetchall())

            # Aggregation distribution
            cursor = conn.execute("SELECT has_agg, COUNT(*) FROM questions GROUP BY has_agg")
            agg_dist = dict(cursor.fetchall())
            stats["aggregation_distribution"] = {
                "with_aggregation": agg_dist.get(1, 0),
                "without_aggregation": agg_dist.get(0, 0)
            }

            # Table size distribution
            cursor = conn.execute("""
                SELECT
                    CASE
                        WHEN n_rows < 10 THEN 'small'
                        WHEN n_rows < 100 THEN 'medium'
                        WHEN n_rows < 1000 THEN 'large'
                        ELSE 'very_large'
                    END as size_category,
                    COUNT(*) as count
                FROM questions
                GROUP BY size_category
            """)
            stats["table_size_distribution"] = dict(cursor.fetchall())

            return stats


def load_wikisql(variant: str = "top500", version: str = "latest",
                datasets_root: Path = None) -> WikiSQLLoader:
    """
    Convenience function to load WikiSQL dataset.

    Args:
        variant: Dataset variant (default: "top500")
        version: Version to load (default: "latest")
        datasets_root: Root directory for datasets

    Returns:
        WikiSQLLoader instance
    """
    from ..registry import load_dataset
    return load_dataset("wikisql", variant, version, datasets_root)
