"""
Backend configuration system for LiteLLM integration.

Provides backend detection and model response generation with uniform settings.
Handles LM Studio, Ollama, and OpenRouter backends with automatic detection.
"""

import os
import requests
import litellm
from typing import Dict, Tuple, Any, Optional


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


def detect_backend(model: str) -> Tuple[str, str]:
    """Detect backend type based on availability.

    Checks in order: LM Studio → Ollama → OpenRouter

    Args:
        model: Model name (not used for detection, kept for compatibility)

    Returns:
        Tuple of (backend_type, api_base)
    """
    if _check_endpoint_availability("http://localhost:1234/v1/models"):
        return "lm_studio", "http://localhost:1234/v1"

    if _check_endpoint_availability("http://localhost:11434/api/tags"):
        return "ollama", "http://localhost:11434/v1"

    return "openrouter", "https://openrouter.ai/api/v1"


def get_backend(backend_name: Optional[str] = None) -> Optional[str]:
    """Get available backend, either by manual selection or auto-detection.

    Args:
        backend_name: Optional backend name to force selection

    Returns:
        Backend name if available, None if none found
    """
    if backend_name:
        if backend_name == "openrouter":
            return backend_name if os.getenv("OPENROUTER_API_KEY") else None
        elif backend_name == "lm_studio":
            return backend_name if _check_endpoint_availability("http://localhost:1234/v1/models") else None
        elif backend_name == "ollama":
            return backend_name if _check_endpoint_availability("http://localhost:11434/api/tags") else None
        return None

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


def _get_api_config(backend_name: str) -> Tuple[str, str]:
    """Get API base URL and key for backend.

    Returns:
        Tuple of (api_base, api_key)
    """
    if backend_name == "lm_studio":
        return "http://localhost:1234/v1", "lm-studio"
    elif backend_name == "ollama":
        return "http://localhost:11434/v1", "ollama"
    elif backend_name == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable required")
        return "https://openrouter.ai/api/v1", api_key
    else:
        raise ValueError(f"Unknown backend: {backend_name}")


def _make_direct_request(api_base: str, api_key: str, model: str, prompt: str, params: Dict[str, Any], backend_name: str, debug: bool) -> Dict[str, Any]:
    """Make direct HTTP request for LM Studio and Ollama."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        **params
    }

    if backend_name == "lm_studio":
        payload["reasoning"] = True

    response = requests.post(f"{api_base}/chat/completions",
                           headers=headers,
                           json=payload,
                           timeout=60)
    response.raise_for_status()
    raw_response = response.json()
    message = raw_response["choices"][0]["message"]

    if debug:
        for key in REASONING_KEYS:
            if message.get(key):
                print(f"DEBUG: Found {key}: {message[key][:100]}...")
        print(f"DEBUG: All message keys: {list(message.keys())}")

    return message


def generate_response(prompt: str, model: str, backend_name: str, use_tools: bool = False, debug: bool = False) -> Dict[str, Any]:
    """Generate response from model with full reasoning content capture.

    Args:
        prompt: Input prompt
        model: Model identifier
        backend_name: Name of the backend being used
        use_tools: Whether to use tool calling
        debug: Whether to print debug information

    Returns:
        The message dictionary from the API response, including raw fields.

    Raises:
        Exception: If model call fails
    """
    if use_tools:
        raise NotImplementedError("Tool calling mode not yet implemented")

    api_base, api_key = _get_api_config(backend_name)
    params = get_uniform_parameters()

    # Use direct HTTP requests for LM Studio and Ollama to capture reasoning_content
    if backend_name in ["lm_studio", "ollama"]:
        try:
            return _make_direct_request(api_base, api_key, model, prompt, params, backend_name, debug)
        except Exception as e:
            raise Exception(f"{backend_name.title()} API call failed: {e}")

    # Use LiteLLM for OpenRouter
    try:
        response = litellm.completion(
            model=f"{backend_name}/{model}",
            messages=[{"role": "user", "content": prompt}],
            api_base=api_base,
            api_key=api_key,
            **params
        )

        message = response.choices[0].message  # type: ignore
        return message.model_dump()

    except Exception as e:
        raise Exception(f"Model call failed: {e}")
