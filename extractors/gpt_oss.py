"""gpt-oss response parser placeholder."""

from typing import Dict, Any, Optional
from .base import BaseResponseParser


class GptOssResponseParser(BaseResponseParser):
    """Response parser for gpt-oss models only (gpt-oss-20b, gpt-oss-120b).

    This is a placeholder implementation that uses the base parser functionality.
    Can be extended with gpt-oss-specific response patterns as needed.
    """

    def extract_sql(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract SQL from gpt-oss model response.

        Args:
            response: Model response data containing raw_response and metadata

        Returns:
            Extracted SQL string or None if no SQL found
        """
        return self.parse_response(response)
