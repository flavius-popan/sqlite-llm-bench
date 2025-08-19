"""Response parser module for extracting SQL from model responses."""

from .base import BaseResponseParser
from .gpt_oss import GptOssResponseParser
from .qwen import QwenResponseParser

__all__ = ['BaseResponseParser', 'GptOssResponseParser', 'QwenResponseParser']


# Model family to parser class mapping (will be populated as parsers are added)
PARSER_REGISTRY = {
    'gpt-oss': GptOssResponseParser,
    'qwen': QwenResponseParser,
}


def get_parser_for_model(model_name: str) -> BaseResponseParser:
    """Get appropriate response parser for a model.

    Args:
        model_name: Name of the model (e.g., "gpt-4", "qwen/qwen3-30b")

    Returns:
        Response parser instance for the model family
    """
    # Determine model family from model name
    model_family = _get_model_family(model_name)

    # Get parser class from registry
    parser_class = PARSER_REGISTRY.get(model_family, BaseResponseParser)

    # Return parser instance
    return parser_class()


def _get_model_family(model_name: str) -> str:
    """Determine model family from model name.

    Args:
        model_name: Full model name

    Returns:
        Model family identifier
    """
    model_lower = model_name.lower()

    # gpt-oss models specifically
    if 'gpt-oss' in model_lower:
        return 'gpt-oss'

    # Qwen family models
    if 'qwen' in model_lower:
        return 'qwen'

    # Default to base parser for unknown models
    return 'base'


def register_parser(model_family: str, parser_class: type):
    """Register a parser class for a model family.

    Args:
        model_family: Model family identifier
        parser_class: Parser class to register
    """
    PARSER_REGISTRY[model_family] = parser_class
