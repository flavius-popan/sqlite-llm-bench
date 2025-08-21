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
import litellm
from typing import Dict, Tuple, Union, Any, Optional


# Uniform settings applied across all backends
UNIFORM_TEMPERATURE = 0.1
UNIFORM_MAX_TOKENS = 1024
UNIFORM_TIMEOUT = 30

# Keys to check for reasoning content in model responses
REASONING_KEYS = ['reasoning', 'reasoning_content']


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
        return "lm_studio", {
            "api_base": "http://localhost:1234/v1",
            "api_key": "lm-studio",
            "api_key_env": None
        }

    # Check Ollama second
    if _check_endpoint_availability("http://localhost:11434/api/tags"):
        return "ollama", {
            "api_base": "http://localhost:11434/v1",
            "api_key": "ollama",
            "api_key_env": None
        }

    # Fall back to OpenRouter
    return "openrouter", {
        "api_base": "https://openrouter.ai/api/v1",
        "api_key": None,
        "api_key_env": "OPENROUTER_API_KEY"
    }


def get_backend(backend_name: Optional[str] = None) -> Optional[str]:
    """Get available backend, either by manual selection or auto-detection.

    Args:
        backend_name: Optional backend name to force selection

    Returns:
        Backend name if available, None if none found
    """
    if backend_name:
        # Validate manually selected backend
        backend_type, config = detect_backend("")  # Model not used in detection
        available_backends = ["lm_studio", "ollama", "openrouter"]
        if backend_name in available_backends:
            if backend_name == "openrouter":
                return backend_name if os.getenv("OPENROUTER_API_KEY") else None
            elif backend_name == "lm_studio":
                return backend_name if _check_endpoint_availability("http://localhost:1234/v1/models") else None
            elif backend_name == "ollama":
                return backend_name if _check_endpoint_availability("http://localhost:11434/api/tags") else None
        return None

    # Auto-detection fallback
    backend_type, _ = detect_backend("")
    return backend_type


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


def get_backend_config(backend_name: str) -> Dict[str, Any]:
    """Get configuration for a specific backend.

    Args:
        backend_name: Name of the backend

    Returns:
        Backend configuration dictionary
    """
    _, config = detect_backend("")

    if backend_name == "lm_studio":
        return {
            "base_url": "http://localhost:1234/v1",
            "api_key": "lm-studio",
            "default_params": get_uniform_parameters()
        }
    elif backend_name == "ollama":
        return {
            "base_url": "http://localhost:11434/v1",
            "api_key": "ollama",
            "default_params": get_uniform_parameters()
        }
    elif backend_name == "openrouter":
        return {
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": None,
            "default_params": get_uniform_parameters()
        }
    else:
        raise ValueError(f"Unknown backend: {backend_name}")


def generate_response(prompt: str, model: str, backend_name: str, use_tools: bool = False, debug: bool = False, enable_reasoning: bool = True) -> Dict[str, Any]:
    """Generate response from model with full reasoning content capture.

    Args:
        prompt: Input prompt
        model: Model identifier
        backend_name: Name of the backend being used
        use_tools: Whether to use tool calling
        debug: Whether to print debug information
        enable_reasoning: Whether to enable reasoning for supported models

    Returns:
        The message dictionary from the API response, including raw fields.

    Raises:
        Exception: If model call fails
    """
    if use_tools:
        raise NotImplementedError("Tool calling mode not yet implemented")

    backend_config = get_backend_config(backend_name)
    params = backend_config["default_params"].copy()
    api_base = backend_config["base_url"]
    api_key = backend_config.get("api_key")

    if backend_name == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable required")

    # For LM Studio and Ollama, make direct HTTP request to get full response including reasoning_content
    if backend_name in ["lm_studio", "ollama"]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            **params
        }

        # Add reasoning parameter if enabled (primarily for LM Studio)
        if enable_reasoning and backend_name == "lm_studio":
            payload["reasoning"] = True

        try:
            response = requests.post(f"{api_base}/chat/completions",
                                   headers=headers,
                                   json=payload,
                                   timeout=60)
            response.raise_for_status()
            raw_response = response.json()
            message = raw_response["choices"][0]["message"]

            if debug:
                reasoning_keys = ['reasoning', 'reasoning_content']
                for key in reasoning_keys:
                    if message.get(key):
                        print(f"DEBUG: Found {key}: {message[key][:100]}...")
                print(f"DEBUG: All message keys: {list(message.keys())}")

            return message
        except Exception as e:
            raise Exception(f"{backend_name.title()} API call failed: {e}")

    # Use LiteLLM for other backends
    litellm_model = f"{backend_name}/{model}"

    try:
        response = litellm.completion(
            model=litellm_model,
            messages=[{"role": "user", "content": prompt}],
            api_base=api_base,
            api_key=api_key,
            **params
        )

        # Extract message data with proper type handling
        message = response.choices[0].message  # type: ignore
        if hasattr(message, 'model_dump'):
            return message.model_dump()
        elif hasattr(message, 'dict'):
            return message.dict()
        else:
            return dict(message)
    except Exception as e:
        raise Exception(f"Model call failed: {e}")


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

    if backend_type == "lm_studio":
        return _check_endpoint_availability("http://localhost:1234/v1/models")
    elif backend_type == "ollama":
        return _check_endpoint_availability("http://localhost:11434/api/tags")
    elif backend_type == "openrouter":
        return os.getenv("OPENROUTER_API_KEY") is not None

    return False
