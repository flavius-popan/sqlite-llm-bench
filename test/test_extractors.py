"""Tests for response parser functionality."""

import pytest
from extractors.base import BaseResponseParser
from extractors.default import DefaultResponseParser


class TestBaseResponseParser:
    """Test base response parser abstract interface."""

    def test_base_parser_is_abstract(self):
        """Test that BaseResponseParser cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseResponseParser()

    def test_extract_sql_is_abstract(self):
        """Test that extract_sql method is abstract."""
        # This is verified by the instantiation test above
        assert hasattr(BaseResponseParser, 'extract_sql')


class TestDefaultResponseParser:
    """Test default response parser implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = DefaultResponseParser()

    def test_parser_instantiation(self):
        """Test that DefaultResponseParser can be instantiated."""
        assert isinstance(self.parser, DefaultResponseParser)
        assert isinstance(self.parser, BaseResponseParser)

    def test_extract_sql_basic(self):
        """Test basic SQL extraction from response."""
        response = {
            "raw_response": "```sql\nSELECT * FROM users;\n```"
        }
        result = self.parser.extract_sql(response)
        assert result == "SELECT * FROM users;"

    def test_extract_sql_no_response(self):
        """Test extraction with no raw_response."""
        response = {}
        result = self.parser.extract_sql(response)
        assert result is None

    def test_extract_sql_empty_response(self):
        """Test extraction with empty raw_response."""
        response = {"raw_response": ""}
        result = self.parser.extract_sql(response)
        assert result is None


class TestMarkdownExtraction:
    """Test markdown SQL extraction methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = DefaultResponseParser()

    def test_extract_sql_markdown_block(self):
        """Test extraction from SQL markdown blocks."""
        response = {
            "raw_response": "Here's the query:\n```sql\nSELECT COUNT(*) FROM orders;\n```"
        }
        result = self.parser.extract_sql(response)
        assert result == "SELECT COUNT(*) FROM orders;"

    def test_extract_uppercase_sql_markdown(self):
        """Test extraction from uppercase SQL markdown blocks."""
        response = {
            "raw_response": "```SQL\nSELECT name FROM users WHERE id = 1;\n```"
        }
        result = self.parser.extract_sql(response)
        assert result == "SELECT name FROM users WHERE id = 1;"

    def test_extract_plain_markdown_block(self):
        """Test extraction from plain markdown blocks containing SQL."""
        response = {
            "raw_response": "```\nSELECT u.name, COUNT(o.id) FROM users u JOIN orders o ON u.id = o.user_id GROUP BY u.name;\n```"
        }
        result = self.parser.extract_sql(response)
        assert result == "SELECT u.name, COUNT(o.id) FROM users u JOIN orders o ON u.id = o.user_id GROUP BY u.name;"

    def test_extract_multiple_sql_blocks(self):
        """Test extraction when multiple SQL blocks are present."""
        response = {
            "raw_response": """First attempt:
```sql
SELECT * FROM users;
```

Better query:
```sql
SELECT name, email FROM users WHERE active = 1;
```"""
        }
        result = self.parser.extract_sql(response)
        # Should return the better (longer) query
        assert result == "SELECT name, email FROM users WHERE active = 1;"

    def test_extract_non_sql_markdown_ignored(self):
        """Test that non-SQL markdown blocks are ignored."""
        response = {
            "raw_response": """```python
print("Hello world")
```

```sql
SELECT * FROM users;
```"""
        }
        result = self.parser.extract_sql(response)
        assert result == "SELECT * FROM users;"


class TestPlainTextExtraction:
    """Test plain text SQL extraction methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = DefaultResponseParser()

    def test_extract_plain_text_select(self):
        """Test extraction of SELECT from plain text."""
        response = {
            "raw_response": "The answer is:\nSELECT COUNT(*) FROM users WHERE active = 1;"
        }
        result = self.parser.extract_sql(response)
        assert result == "SELECT COUNT(*) FROM users WHERE active = 1;"

    def test_extract_multiline_sql(self):
        """Test extraction of multiline SQL from plain text."""
        response = {
            "raw_response": """To get user orders:
SELECT u.name, o.product, o.amount
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE o.order_date >= '2024-01-01';"""
        }
        result = self.parser.extract_sql(response)
        expected = "SELECT u.name, o.product, o.amount FROM users u JOIN orders o ON u.id = o.user_id WHERE o.order_date >= '2024-01-01';"
        assert result == expected

    def test_extract_sql_with_semicolon(self):
        """Test extraction when SQL ends with semicolon."""
        response = {
            "raw_response": "SELECT name FROM users WHERE id = 5;"
        }
        result = self.parser.extract_sql(response)
        assert result == "SELECT name FROM users WHERE id = 5;"

    def test_extract_insert_statement(self):
        """Test extraction of INSERT statements."""
        response = {
            "raw_response": "INSERT INTO users (name, email) VALUES ('John', 'john@example.com');"
        }
        result = self.parser.extract_sql(response)
        assert result == "INSERT INTO users (name, email) VALUES ('John', 'john@example.com');"

    def test_extract_update_statement(self):
        """Test extraction of UPDATE statements."""
        response = {
            "raw_response": "UPDATE users SET email = 'new@example.com' WHERE id = 1;"
        }
        result = self.parser.extract_sql(response)
        assert result == "UPDATE users SET email = 'new@example.com' WHERE id = 1;"

    def test_extract_delete_statement(self):
        """Test extraction of DELETE statements."""
        response = {
            "raw_response": "DELETE FROM orders WHERE order_date < '2023-01-01';"
        }
        result = self.parser.extract_sql(response)
        assert result == "DELETE FROM orders WHERE order_date < '2023-01-01';"


class TestToolCallExtraction:
    """Test tool calling response extraction."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = DefaultResponseParser()

    def test_extract_openai_tool_calls(self):
        """Test extraction from OpenAI-style tool calls."""
        response = {
            "tool_calls": [
                {
                    "function": {
                        "name": "execute_sql",
                        "arguments": {"query": "SELECT * FROM users;"}
                    }
                }
            ]
        }
        result = self.parser.extract_sql(response)
        assert result == "SELECT * FROM users;"

    def test_extract_tool_calls_json_string(self):
        """Test extraction when arguments are JSON string."""
        response = {
            "tool_calls": [
                {
                    "function": {
                        "name": "execute_sql",
                        "arguments": '{"query": "SELECT COUNT(*) FROM orders;"}'
                    }
                }
            ]
        }
        result = self.parser.extract_sql(response)
        assert result == "SELECT COUNT(*) FROM orders;"

    def test_extract_function_call_format(self):
        """Test extraction from direct function call format."""
        response = {
            "function_call": {
                "name": "execute_sql",
                "arguments": {"query": "SELECT name FROM users WHERE active = 1;"}
            }
        }
        result = self.parser.extract_sql(response)
        assert result == "SELECT name FROM users WHERE active = 1;"

    def test_extract_wrong_function_ignored(self):
        """Test that wrong function calls are ignored."""
        response = {
            "tool_calls": [
                {
                    "function": {
                        "name": "describe_database",
                        "arguments": {"table_name": "users"}
                    }
                }
            ],
            "raw_response": "```sql\nSELECT * FROM users;\n```"
        }
        result = self.parser.extract_sql(response)
        # Should fall back to text parsing
        assert result == "SELECT * FROM users;"

    def test_extract_invalid_json_fallback(self):
        """Test fallback when tool call JSON is invalid."""
        response = {
            "tool_calls": [
                {
                    "function": {
                        "name": "execute_sql",
                        "arguments": '{"query": "SELECT * FROM users;'  # Invalid JSON
                    }
                }
            ],
            "raw_response": "```sql\nSELECT name FROM users;\n```"
        }
        result = self.parser.extract_sql(response)
        # Should fall back to text parsing
        assert result == "SELECT name FROM users;"


class TestSQLValidation:
    """Test SQL validation and selection logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = DefaultResponseParser()

    def test_looks_like_sql_basic(self):
        """Test basic SQL detection."""
        assert self.parser._looks_like_sql("SELECT * FROM users")
        assert self.parser._looks_like_sql("INSERT INTO users VALUES (1, 'John')")
        assert self.parser._looks_like_sql("UPDATE users SET name = 'Jane'")
        assert self.parser._looks_like_sql("DELETE FROM users WHERE id = 1")

    def test_looks_like_sql_complex(self):
        """Test complex SQL detection."""
        sql = "SELECT u.name, COUNT(o.id) FROM users u LEFT JOIN orders o ON u.id = o.user_id GROUP BY u.name"
        assert self.parser._looks_like_sql(sql)

    def test_not_sql_text(self):
        """Test that non-SQL text is rejected."""
        assert not self.parser._looks_like_sql("This is just plain text")
        assert not self.parser._looks_like_sql("Hello world")
        assert not self.parser._looks_like_sql("def function(): return True")

    def test_not_sql_empty(self):
        """Test that empty/short text is rejected."""
        assert not self.parser._looks_like_sql("")
        assert not self.parser._looks_like_sql("  ")
        assert not self.parser._looks_like_sql("a")

    def test_select_best_sql_single(self):
        """Test selection when only one SQL statement."""
        sqls = ["SELECT * FROM users;"]
        result = self.parser._select_best_sql(sqls)
        assert result == "SELECT * FROM users;"

    def test_select_best_sql_empty(self):
        """Test selection when no SQL statements."""
        result = self.parser._select_best_sql([])
        assert result is None

    def test_select_best_sql_multiple(self):
        """Test selection of best SQL from multiple candidates."""
        sqls = [
            "SELECT *",  # Short, incomplete
            "SELECT name FROM users WHERE active = 1 ORDER BY name;",  # Better
            "SELECT id"  # Short, incomplete
        ]
        result = self.parser._select_best_sql(sqls)
        assert result == "SELECT name FROM users WHERE active = 1 ORDER BY name;"


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = DefaultResponseParser()

    def test_mixed_response_tool_call_preferred(self):
        """Test that tool calls are preferred over text when both present."""
        response = {
            "tool_calls": [
                {
                    "function": {
                        "name": "execute_sql",
                        "arguments": {"query": "SELECT COUNT(*) FROM users;"}
                    }
                }
            ],
            "raw_response": "```sql\nSELECT * FROM users;\n```"
        }
        result = self.parser.extract_sql(response)
        # Tool call should be preferred
        assert result == "SELECT COUNT(*) FROM users;"

    def test_chatbot_style_response(self):
        """Test extraction from conversational response."""
        response = {
            "raw_response": """I'll help you count the users. Here's the SQL query:

```sql
SELECT COUNT(*) FROM users WHERE active = 1;
```

This query will return the number of active users in the database."""
        }
        result = self.parser.extract_sql(response)
        assert result == "SELECT COUNT(*) FROM users WHERE active = 1;"

    def test_explanation_with_sql(self):
        """Test extraction when SQL is embedded in explanation."""
        response = {
            "raw_response": """To find the total order amount for each user, you need to:
1. Join the users and orders tables
2. Group by user
3. Sum the amounts

SELECT u.name, SUM(o.amount)
FROM users u
JOIN orders o ON u.id = o.user_id
GROUP BY u.name;

This will give you the result you're looking for."""
        }
        result = self.parser.extract_sql(response)
        expected = "SELECT u.name, SUM(o.amount) FROM users u JOIN orders o ON u.id = o.user_id GROUP BY u.name;"
        assert result == expected

    def test_no_sql_in_response(self):
        """Test when response contains no SQL."""
        response = {
            "raw_response": "I don't understand the question. Could you please clarify what you're looking for?"
        }
        result = self.parser.extract_sql(response)
        assert result is None

    def test_malformed_sql_response(self):
        """Test with malformed SQL that doesn't pass validation."""
        response = {
            "raw_response": "```sql\nthis is not really sql\n```"
        }
        result = self.parser.extract_sql(response)
        assert result is None
