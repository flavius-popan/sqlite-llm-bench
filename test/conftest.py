import pytest
import sqlite3
import tempfile
from pathlib import Path


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database with test data."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create test tables
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product TEXT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Insert test data
    cursor.execute("INSERT INTO users (name, email) VALUES ('Alice', 'alice@test.com')")
    cursor.execute("INSERT INTO users (name, email) VALUES ('Bob', 'bob@test.com')")

    cursor.execute("INSERT INTO orders (user_id, product, amount) VALUES (1, 'Laptop', 999.99)")
    cursor.execute("INSERT INTO orders (user_id, product, amount) VALUES (1, 'Mouse', 29.99)")
    cursor.execute("INSERT INTO orders (user_id, product, amount) VALUES (2, 'Keyboard', 79.99)")

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    Path(db_path).unlink()
