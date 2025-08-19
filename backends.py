"""
Backend configuration system for LiteLLM integration.

Provides complete abstraction for backend detection, configuration, and provider routing.
Handles uniform settings across all backends while allowing model-specific customization
through backend tools (LM Studio presets, Ollama modelfiles, etc.).

The backends module abstracts away all LiteLLM provider routing so that eval.py
doesn't need to know about backend-specific details.
"""

import os
import requests
from typing import Dict, Tuple, Union, Any


# Uniform settings applied across all backends
UNIFORM_TEMPERATURE = 0.1
UNIFORM_MAX_TOKENS = 1024
UNIFORM_TIMEOUT = 30


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
    """Configure LiteLLM for the detected backend with uniform settings.

    Handles both environment configuration and LiteLLM provider routing internally.
    The caller doesn't need to know which backend was detected or how to format
    the model name for LiteLLM.

    Args:
        model: Original model name

    Returns:
        LiteLLM-compatible model name with proper provider routing
    """
    backend_type, config = detect_backend(model)

    if backend_type == "lmstudio":
        # Set LM Studio configuration with uniform settings
        api_base = config["api_base"]
        if api_base:
            os.environ["OPENAI_API_BASE"] = api_base
        os.environ["OPENAI_API_KEY"] = "lm-studio"
        return f"openai/{model}"

    elif backend_type == "ollama":
        # Set Ollama configuration with uniform settings
        api_base = config["api_base"]
        if api_base:
            os.environ["OLLAMA_API_BASE"] = api_base
        return f"ollama/{model}"

    elif backend_type == "openrouter":
        # Set OpenRouter configuration with uniform settings
        if not os.getenv("OPENROUTER_API_KEY"):
            raise ValueError("OPENROUTER_API_KEY environment variable required for OpenRouter models")
        api_base = config["api_base"]
        if api_base:
            os.environ["OPENAI_API_BASE"] = api_base
        return f"openai/{model}"

    return model


def get_uniform_parameters() -> Dict[str, Any]:
    """Get uniform parameters applied across all backends.

    Returns:
        Dictionary of uniform parameters for model completion calls
    """
    return {
        "temperature": UNIFORM_TEMPERATURE,
        "max_tokens": UNIFORM_MAX_TOKENS,
        "timeout": UNIFORM_TIMEOUT,
    }


def get_lmstudio_parameters() -> Dict[str, Any]:
    """Get LM Studio-specific parameters with environment variable overrides.

    Applies uniform settings that can be overridden via environment variables.
    Model-specific settings should be configured in LM Studio presets.

    Environment variables:
    - LMSTUDIO_TEMPERATURE: Override default temperature (default: 0.1)
    - LMSTUDIO_MAX_TOKENS: Override default max tokens (default: 1024)
    - LMSTUDIO_TIMEOUT: Override default timeout (default: 30)

    Returns:
        Dictionary of parameters for LM Studio model calls
    """
    return {
        "temperature": float(os.getenv("LMSTUDIO_TEMPERATURE", str(UNIFORM_TEMPERATURE))),
        "max_tokens": int(os.getenv("LMSTUDIO_MAX_TOKENS", str(UNIFORM_MAX_TOKENS))),
        "timeout": int(os.getenv("LMSTUDIO_TIMEOUT", str(UNIFORM_TIMEOUT))),
    }


def get_ollama_parameters() -> Dict[str, Any]:
    """Get Ollama-specific parameters with environment variable overrides.

    Environment variables:
    - OLLAMA_TEMPERATURE: Override default temperature (default: 0.1)
    - OLLAMA_MAX_TOKENS: Override default max tokens (default: 1024)
    - OLLAMA_TIMEOUT: Override default timeout (default: 30)

    Returns:
        Dictionary of parameters for Ollama model calls
    """
    return {
        "temperature": float(os.getenv("OLLAMA_TEMPERATURE", str(UNIFORM_TEMPERATURE))),
        "max_tokens": int(os.getenv("OLLAMA_MAX_TOKENS", str(UNIFORM_MAX_TOKENS))),
        "timeout": int(os.getenv("OLLAMA_TIMEOUT", str(UNIFORM_TIMEOUT))),
    }


def get_openrouter_parameters() -> Dict[str, Any]:
    """Get OpenRouter-specific parameters with environment variable overrides.

    Environment variables:
    - OPENROUTER_TEMPERATURE: Override default temperature (default: 0.1)
    - OPENROUTER_MAX_TOKENS: Override default max tokens (default: 1024)
    - OPENROUTER_TIMEOUT: Override default timeout (default: 30)

    Returns:
        Dictionary of parameters for OpenRouter model calls
    """
    return {
        "temperature": float(os.getenv("OPENROUTER_TEMPERATURE", str(UNIFORM_TEMPERATURE))),
        "max_tokens": int(os.getenv("OPENROUTER_MAX_TOKENS", str(UNIFORM_MAX_TOKENS))),
        "timeout": int(os.getenv("OPENROUTER_TIMEOUT", str(UNIFORM_TIMEOUT))),
    }


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
        return os.getenv("OPENROUTER_API_KEY") is not None

    return False
