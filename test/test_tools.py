import pytest
import sqlite3
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval import describe_database, execute_sql


class TestDescribeDatabase:
    """Test the describe_database function."""

    def test_describe_single_table(self, temp_db):
        """Test describing a single table."""
        result = describe_database(temp_db, 'users')

        lines = result.strip().split('\n')
        assert len(lines) == 4  # 4 columns in users table

        # Check column format: cid|name|type|notnull|dflt_value|pk
        id_col = lines[0].split('|')
        assert id_col[1] == 'id'
        assert id_col[2] == 'INTEGER'
        assert id_col[5] == '1'  # primary key

        name_col = lines[1].split('|')
        assert name_col[1] == 'name'
        assert name_col[2] == 'TEXT'
        assert name_col[3] == '1'  # not null

    def test_describe_all_tables(self, temp_db):
        """Test describing all tables in database."""
        result = describe_database(temp_db)

        assert 'Table: users' in result
        assert 'Table: orders' in result
        assert 'name|TEXT|1' in result  # users.name column
        assert 'product|TEXT|1' in result  # orders.product column

    def test_describe_nonexistent_table(self, temp_db):
        """Test describing a table that doesn't exist."""
        result = describe_database(temp_db, 'nonexistent')
        assert result == ""  # Empty result for non-existent table

    def test_describe_with_readonly_connection(self, temp_db):
        """Test that describe_database uses read-only connection."""
        # Should work fine with read-only mode
        result = describe_database(temp_db, 'users')
        assert 'id|INTEGER' in result


class TestExecuteSQL:
    """Test the execute_sql function."""

    def test_simple_select(self, temp_db):
        """Test basic SELECT query."""
        result = execute_sql(temp_db, 'SELECT * FROM users')

        lines = result.strip().split('\n')
        assert lines[0] == 'id|name|email|created_at'  # Headers
        assert len(lines) == 3  # Header + 2 data rows
        assert 'Alice|alice@test.com' in lines[1]
        assert 'Bob|bob@test.com' in lines[2]

    def test_select_with_limit(self, temp_db):
        """Test SELECT with LIMIT clause."""
        result = execute_sql(temp_db, 'SELECT name FROM users LIMIT 1')

        lines = result.strip().split('\n')
        assert lines[0] == 'name'
        assert len(lines) == 2  # Header + 1 data row
        assert lines[1] == 'Alice'

    def test_join_query(self, temp_db):
        """Test JOIN query between tables."""
        result = execute_sql(temp_db, '''
            SELECT u.name, o.product, o.amount
            FROM users u
            JOIN orders o ON u.id = o.user_id
            ORDER BY u.name, o.product
        ''')

        lines = result.strip().split('\n')
        assert lines[0] == 'name|product|amount'
        assert 'Alice|Laptop|999.99' in result
        assert 'Alice|Mouse|29.99' in result
        assert 'Bob|Keyboard|79.99' in result

    def test_aggregate_query(self, temp_db):
        """Test aggregate functions."""
        result = execute_sql(temp_db, 'SELECT COUNT(*) as user_count FROM users')

        lines = result.strip().split('\n')
        assert lines[0] == 'user_count'
        assert lines[1] == '2'

    def test_empty_result(self, temp_db):
        """Test query that returns no rows."""
        result = execute_sql(temp_db, "SELECT * FROM users WHERE name = 'Nonexistent'")

        lines = result.strip().split('\n')
        assert lines[0] == 'id|name|email|created_at'  # Headers only
        assert len(lines) == 1

    def test_null_values(self, temp_db):
        """Test handling of NULL values in results."""
        # Add a row with NULL
        conn = sqlite3.connect(temp_db)
        conn.execute("INSERT INTO users (name, email, created_at) VALUES ('Test', 'test@test.com', NULL)")
        conn.commit()
        conn.close()

        result = execute_sql(temp_db, "SELECT name, created_at FROM users WHERE name = 'Test'")

        lines = result.strip().split('\n')
        assert 'Test|' in lines[1]  # NULL becomes empty string

    def test_readonly_blocks_write_operations(self, temp_db):
        """Test that write operations are blocked by read-only mode."""
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            execute_sql(temp_db, "DELETE FROM users")

        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            execute_sql(temp_db, "UPDATE users SET name = 'Changed'")

        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            execute_sql(temp_db, "INSERT INTO users (name, email) VALUES ('New', 'new@test.com')")

        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            execute_sql(temp_db, "DROP TABLE users")

    def test_invalid_sql_syntax(self, temp_db):
        """Test handling of invalid SQL syntax."""
        with pytest.raises(sqlite3.OperationalError):
            execute_sql(temp_db, "INVALID SQL SYNTAX")

    def test_nonexistent_table_query(self, temp_db):
        """Test querying a table that doesn't exist."""
        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            execute_sql(temp_db, "SELECT * FROM nonexistent_table")


class TestDatabaseIntegration:
    """Integration tests using the actual hello_world database."""

    def test_hello_world_database_exists(self):
        """Test that the hello_world database exists and is accessible."""
        db_path = "datasets/hello_world/database.db"
        assert Path(db_path).exists()

    def test_hello_world_schema(self):
        """Test describing hello_world database schema."""
        db_path = "datasets/hello_world/database.db"

        users_schema = describe_database(db_path, 'users')
        assert 'id|INTEGER' in users_schema
        assert 'name|TEXT' in users_schema
        assert 'email|TEXT' in users_schema

        orders_schema = describe_database(db_path, 'orders')
        assert 'user_id|INTEGER' in orders_schema
        assert 'product|TEXT' in orders_schema
        assert 'amount|DECIMAL' in orders_schema

    def test_hello_world_queries(self):
        """Test basic queries against hello_world database."""
        db_path = "datasets/hello_world/database.db"

        # Test users query
        result = execute_sql(db_path, "SELECT COUNT(*) as count FROM users")
        lines = result.strip().split('\n')
        assert lines[0] == 'count'
        assert int(lines[1]) > 0  # Should have some users

        # Test orders query
        result = execute_sql(db_path, "SELECT COUNT(*) as count FROM orders")
        lines = result.strip().split('\n')
        assert lines[0] == 'count'
        assert int(lines[1]) > 0  # Should have some orders

        # Test join works
        result = execute_sql(db_path, """
            SELECT u.name, o.product
            FROM users u
            JOIN orders o ON u.id = o.user_id
            LIMIT 1
        """)
        lines = result.strip().split('\n')
        assert lines[0] == 'name|product'
        assert len(lines) >= 2  # Should have at least one result
