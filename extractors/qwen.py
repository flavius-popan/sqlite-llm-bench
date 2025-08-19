"""Qwen response parser for Qwen3 models."""

from typing import Dict, Any, Optional
from .base import BaseResponseParser


class QwenResponseParser(BaseResponseParser):
    """Response parser for Qwen family models (qwen3, qwen2.5, etc.).

    This is a placeholder implementation that uses the base parser functionality.
    Can be extended with Qwen-specific response patterns as needed.
    """

    def extract_sql(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract SQL from Qwen model response.

        Args:
            response: Model response data containing raw_response and metadata

        Returns:
            Extracted SQL string or None if no SQL found
        """
        return self.parse_response(response)
