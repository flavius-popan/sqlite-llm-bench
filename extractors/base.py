"""Base response parser for extracting SQL from model responses."""

import json
import re
from abc import ABC
from typing import Dict, Any, List, Optional


class BaseResponseParser(ABC):
    """Base class for parsing SQL from model responses."""

    def extract_sql(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract SQL from model response.

        Args:
            response: Model response data containing raw_response and metadata

        Returns:
            Extracted SQL string or None if no SQL found
        """
        return self.parse_response(response)

    def _extract_from_tool_calls(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract SQL from tool calling response format.

        Args:
            response: Response with potential tool calls

        Returns:
            SQL from execute_sql tool call or None
        """
        # Handle OpenAI-style tool calls
        if 'tool_calls' in response:
            for tool_call in response['tool_calls']:
                if tool_call.get('function', {}).get('name') == 'execute_sql':
                    args = tool_call.get('function', {}).get('arguments', {})
                    if isinstance(args, str):
                        import json
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            continue
                    return args.get('query')

        # Handle direct function call format
        if 'function_call' in response:
            func_call = response['function_call']
            if func_call.get('name') == 'execute_sql':
                args = func_call.get('arguments', {})
                if isinstance(args, str):
                    import json
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        return None
                return args.get('query')

        return None

    def _extract_from_markdown(self, text: str) -> List[str]:
        """Extract SQL from markdown code blocks.

        Args:
            text: Response text potentially containing markdown SQL blocks

        Returns:
            List of SQL statements found in code blocks
        """
        sql_statements = []

        # Pattern for SQL code blocks (```sql, ```SQL)
        sql_patterns = [
            r'```sql\s*\n(.*?)\n```',
            r'```SQL\s*\n(.*?)\n```'
        ]

        # Extract explicitly marked SQL blocks first
        for pattern in sql_patterns:
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            for match in matches:
                cleaned = match.strip()
                if cleaned and self._looks_like_sql(cleaned):
                    sql_statements.append(cleaned)

        # If no explicit SQL blocks found, try plain code blocks
        if not sql_statements:
            plain_pattern = r'```\s*\n(.*?)\n```'
            matches = re.findall(plain_pattern, text, re.DOTALL)
            for match in matches:
                cleaned = match.strip()
                if cleaned and self._looks_like_sql(cleaned):
                    sql_statements.append(cleaned)

        return sql_statements

    def _extract_from_plain_text(self, text: str) -> List[str]:
        """Extract SQL from plain text using patterns.

        Args:
            text: Response text potentially containing SQL statements

        Returns:
            List of SQL statements found in plain text
        """
        sql_statements = []

        # Look for SQL keywords at line start
        lines = text.split('\n')
        current_sql = []
        in_sql_block = False

        for line in lines:
            line = line.strip()
            if not line:
                if in_sql_block and current_sql:
                    sql_text = ' '.join(current_sql).strip()
                    if self._looks_like_sql(sql_text):
                        sql_statements.append(sql_text)
                    current_sql = []
                    in_sql_block = False
                continue

            # Check if line starts with SQL keyword
            if re.match(r'^(SELECT|INSERT|UPDATE|DELETE|WITH|CREATE|DROP|ALTER)\b', line, re.IGNORECASE):
                if in_sql_block and current_sql:
                    sql_text = ' '.join(current_sql).strip()
                    if self._looks_like_sql(sql_text):
                        sql_statements.append(sql_text)
                current_sql = [line]
                in_sql_block = True
            elif in_sql_block:
                current_sql.append(line)
                # Check for statement terminator
                if line.endswith(';'):
                    sql_text = ' '.join(current_sql).strip()
                    if self._looks_like_sql(sql_text):
                        sql_statements.append(sql_text)
                    current_sql = []
                    in_sql_block = False

        # Handle final SQL block
        if in_sql_block and current_sql:
            sql_text = ' '.join(current_sql).strip()
            if self._looks_like_sql(sql_text):
                sql_statements.append(sql_text)

        return sql_statements

    def _looks_like_sql(self, text: str) -> bool:
        """Check if text appears to be a SQL statement.

        Args:
            text: Text to check

        Returns:
            True if text looks like SQL
        """
        if not text or len(text.strip()) < 3:
            return False

        # Must contain SQL keywords
        sql_keywords = r'\b(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|JOIN|GROUP|ORDER|HAVING)\b'
        if not re.search(sql_keywords, text, re.IGNORECASE):
            return False

        # Should not contain too many non-SQL words
        words = re.findall(r'\b\w+\b', text)
        if len(words) == 0:
            return False

        sql_word_pattern = r'^(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|JOIN|INNER|LEFT|RIGHT|OUTER|ON|AS|AND|OR|NOT|IN|EXISTS|BETWEEN|LIKE|ORDER|GROUP|BY|HAVING|DISTINCT|COUNT|SUM|AVG|MIN|MAX|CASE|WHEN|THEN|ELSE|END|TABLE|INDEX|DATABASE|SCHEMA|PRIMARY|FOREIGN|KEY|REFERENCES|CONSTRAINT|NULL|DEFAULT|AUTO_INCREMENT|LIMIT|OFFSET|ASC|DESC|UNION|INTERSECT|EXCEPT|VALUES|SET|INTO|USING)$'

        sql_words = [w for w in words if re.match(sql_word_pattern, w, re.IGNORECASE)]
        sql_ratio = len(sql_words) / len(words) if words else 0

        return sql_ratio > 0.2  # At least 20% of words should be SQL keywords

    def _select_best_sql(self, sql_statements: List[str]) -> Optional[str]:
        """Select the best SQL statement from multiple candidates.

        Args:
            sql_statements: List of potential SQL statements

        Returns:
            Best SQL statement or None if none found
        """
        if not sql_statements:
            return None

        if len(sql_statements) == 1:
            return sql_statements[0]

        # Prefer longer statements (more complete)
        # Prefer statements with more SQL keywords
        def score_sql(sql: str) -> int:
            score = len(sql)
            keywords = re.findall(r'\b(SELECT|FROM|WHERE|JOIN|GROUP|ORDER|HAVING)\b', sql, re.IGNORECASE)
            score += len(keywords) * 10
            return score

        return max(sql_statements, key=score_sql)

    def parse_response(self, response: Dict[str, Any]) -> Optional[str]:
        """Parse response using all available methods.

        This method combines tool calling and text parsing approaches.
        Can be overridden by subclasses for model-specific behavior.

        Args:
            response: Model response data

        Returns:
            Extracted SQL string or None
        """
        # Try tool calling first
        sql = self._extract_from_tool_calls(response)
        if sql:
            return sql.strip()

        # Fall back to text parsing
        raw_response = response.get('raw_response', '')
        if not raw_response:
            return None

        # Try markdown extraction
        sql_statements = self._extract_from_markdown(raw_response)

        # If no markdown SQL found, try plain text
        if not sql_statements:
            sql_statements = self._extract_from_plain_text(raw_response)

        return self._select_best_sql(sql_statements)

    def extract_sql_from_conversation(self, conversation_history: List) -> Optional[str]:
        """Extract final SQL from complete conversation history.

        Args:
            conversation_history: List of API responses from conversation

        Returns:
            Final SQL string or None if no SQL found
        """
        if not conversation_history:
            return None

        # Check for execute_sql tool calls in reverse order (most recent first)
        for response in reversed(conversation_history):
            if hasattr(response, 'choices') and response.choices:
                choice = response.choices[0]
                if hasattr(choice, 'message') and hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                    for tool_call in choice.message.tool_calls:
                        if tool_call.function.name == "execute_sql":
                            try:
                                args = json.loads(tool_call.function.arguments)
                                sql = args.get("query")
                                if sql:
                                    return sql.strip()
                            except (json.JSONDecodeError, Exception):
                                continue

        # Fall back to text parsing from final message
        final_response = conversation_history[-1]
        if hasattr(final_response, 'choices') and final_response.choices:
            choice = final_response.choices[0]
            if hasattr(choice, 'message') and choice.message.content:
                sql_statements = self._extract_from_markdown(choice.message.content)
                if not sql_statements:
                    sql_statements = self._extract_from_plain_text(choice.message.content)
                return self._select_best_sql(sql_statements)

        return None
