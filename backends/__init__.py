"""
Backend configuration system for LiteLLM integration.

Handles automatic backend detection and configuration for:
- LM Studio (localhost:1234)
- Ollama (localhost:11434)
- OpenRouter (openrouter.ai)
"""

import os
import requests
from typing import Dict, Tuple, Union


def _check_endpoint_availability(url: str, timeout: int = 3) -> bool:
    """Check if an endpoint is available.

    Args:
        url: URL to check
        timeout: Request timeout in seconds

    Returns:
        True if endpoint responds, False otherwise
    """
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code in [200, 404]  # 404 is OK for some endpoints
    except (requests.RequestException, Exception):
        return False


def detect_backend(model: str) -> Tuple[str, Dict[str, Union[str, None]]]:
    """Detect backend type based on availability, not model name.

    Checks in order: LM Studio → Ollama → OpenRouter

    Args:
        model: Model name (not used for detection, kept for compatibility)

    Returns:
        Tuple of (backend_type, config_dict)
    """
    # Check LM Studio first
    if _check_endpoint_availability("http://localhost:1234/v1/models"):
        return "lmstudio", {
            "api_base": "http://localhost:1234/v1",
            "api_key_env": None
        }

    # Check Ollama second
    if _check_endpoint_availability("http://localhost:11434/api/tags"):
        return "ollama", {
            "api_base": "http://localhost:11434",
            "api_key_env": None
        }

    # Fall back to OpenRouter
    return "openrouter", {
        "api_base": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY"
    }


def configure_backend(model: str) -> str:
    """Configure LiteLLM for the detected backend.

    Args:
        model: Model name

    Returns:
        Formatted model name for LiteLLM
    """
    backend_type, config = detect_backend(model)

    if backend_type == "lmstudio":
        # Set LM Studio configuration
        api_base = config["api_base"]
        if api_base:
            os.environ["OPENAI_API_BASE"] = api_base
        os.environ["OPENAI_API_KEY"] = "lm-studio"  # LM Studio doesn't validate keys
        return f"openai/{model}"

    elif backend_type == "ollama":
        # Set Ollama configuration
        api_base = config["api_base"]
        if api_base:
            os.environ["OLLAMA_API_BASE"] = api_base
        return f"ollama/{model}"

    elif backend_type == "openrouter":
        # Set OpenRouter configuration
        if not os.getenv("OPENROUTER_API_KEY"):
            raise ValueError("OPENROUTER_API_KEY environment variable required for OpenRouter models")

        api_base = config["api_base"]
        if api_base:
            os.environ["OPENAI_API_BASE"] = api_base
        return f"openai/{model}"

    return model


def get_backend_info(model: str) -> Dict[str, Union[str, bool]]:
    """Get backend information for a model.

    Args:
        model: Model name

    Returns:
        Dictionary with backend information
    """
    backend_type, config = detect_backend(model)

    return {
        "backend": backend_type,
        "api_base": config["api_base"] or "",
        "requires_key": config["api_key_env"] is not None,
        "key_env_var": config["api_key_env"] or ""
    }


def check_backend_connection(model: str) -> bool:
    """Check if backend is accessible.

    Args:
        model: Model name to check

    Returns:
        True if backend responds, False otherwise
    """
    backend_type, config = detect_backend(model)

    if backend_type == "lmstudio":
        return _check_endpoint_availability("http://localhost:1234/v1/models")
    elif backend_type == "ollama":
        return _check_endpoint_availability("http://localhost:11434/api/tags")
    elif backend_type == "openrouter":
        # For OpenRouter, just check if API key is available
        return os.getenv("OPENROUTER_API_KEY") is not None

    return False
