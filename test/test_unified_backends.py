"""
Tests for unified backend parameter application.
"""

import os
from unittest.mock import patch
from backends import get_uniform_parameters, configure_backend, get_lmstudio_parameters


class TestUniformParameters:
    """Test uniform parameter application across backends."""

    def test_uniform_parameters_default(self):
        """Test default uniform parameters."""
        params = get_uniform_parameters()

        assert params["temperature"] == 0.1
        assert params["max_tokens"] == 1024
        assert params["timeout"] == 30

    def test_uniform_parameters_structure(self):
        """Test uniform parameters return correct structure."""
        params = get_uniform_parameters()

        assert isinstance(params, dict)
        assert set(params.keys()) == {"temperature", "max_tokens", "timeout"}
        assert all(isinstance(v, (int, float)) for v in params.values())


class TestLMStudioParameters:
    """Test LM Studio parameter configuration."""

    def test_lmstudio_parameters_default(self):
        """Test default LM Studio parameters match uniform settings."""
        params = get_lmstudio_parameters()
        uniform_params = get_uniform_parameters()

        assert params == uniform_params

    def test_lmstudio_parameters_environment_override(self):
        """Test LM Studio parameters with environment overrides."""
        env_vars = {
            "LMSTUDIO_TEMPERATURE": "0.5",
            "LMSTUDIO_MAX_TOKENS": "512",
            "LMSTUDIO_TIMEOUT": "60"
        }

        with patch.dict(os.environ, env_vars):
            params = get_lmstudio_parameters()

        assert params["temperature"] == 0.5
        assert params["max_tokens"] == 512
        assert params["timeout"] == 60

    def test_lmstudio_partial_environment_override(self):
        """Test LM Studio parameters with partial environment overrides."""
        env_vars = {"LMSTUDIO_TEMPERATURE": "0.2"}

        with patch.dict(os.environ, env_vars):
            params = get_lmstudio_parameters()

        assert params["temperature"] == 0.2
        assert params["max_tokens"] == 1024  # default
        assert params["timeout"] == 30      # default


class TestBackendConfiguration:
    """Test backend configuration maintains simplicity."""

    @patch('backends._check_endpoint_availability')
    def test_configure_backend_applies_settings(self, mock_check):
        """Test backend configuration applies uniform settings."""
        mock_check.side_effect = lambda url, timeout=3: url == "http://localhost:1234/v1/models"

        model = "test-model"
        formatted_model = configure_backend(model)

        assert formatted_model == f"openai/{model}"
        assert os.environ.get("OPENAI_API_BASE") == "http://localhost:1234/v1"
        assert os.environ.get("OPENAI_API_KEY") == "lm-studio"

    def test_uniform_parameters_consistency(self):
        """Test that uniform parameters are consistently applied."""
        uniform_params = get_uniform_parameters()
        lmstudio_params = get_lmstudio_parameters()

        # Without environment overrides, should be identical
        assert uniform_params == lmstudio_params


class TestSimplifiedArchitecture:
    """Test that the simplified architecture meets design goals."""

    def test_temperature_consistency(self):
        """Test that temperature is consistently set to 0.1 across backends."""
        uniform_params = get_uniform_parameters()
        lmstudio_params = get_lmstudio_parameters()

        assert uniform_params["temperature"] == 0.1
        assert lmstudio_params["temperature"] == 0.1

    def test_environment_customization_works(self):
        """Test that users can customize via environment variables."""
        custom_temp = "0.3"
        env_vars = {"LMSTUDIO_TEMPERATURE": custom_temp}

        with patch.dict(os.environ, env_vars):
            params = get_lmstudio_parameters()

        assert params["temperature"] == float(custom_temp)

    def test_backend_specific_modules_are_simple(self):
        """Test that backend-specific modules focus on parameter application."""
        # LM Studio module should provide simple parameter access
        params = get_lmstudio_parameters()

        # Should contain exactly the parameters needed for model calls
        expected_keys = {"temperature", "max_tokens", "timeout"}
        assert set(params.keys()) == expected_keys

        # All values should be numeric
        assert all(isinstance(v, (int, float)) for v in params.values())
