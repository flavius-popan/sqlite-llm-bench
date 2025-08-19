"""Default response parser implementation for testing and fallback."""

from typing import Dict, Any, Optional
from .base import BaseResponseParser


class DefaultResponseParser(BaseResponseParser):
    """Default implementation of response parser using base methods."""

    def extract_sql(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract SQL from model response using all available methods.

        Args:
            response: Model response data containing raw_response and metadata

        Returns:
            Extracted SQL string or None if no SQL found
        """
        return self.parse_response(response)
