"""
Tests for backend configuration and LiteLLM integration.
"""

import pytest
import os
from unittest.mock import patch
from backends import detect_backend, configure_backend, get_backend_info, check_backend_connection


class TestBackendDetection:
    """Test backend auto-detection logic based on availability."""

    @patch('backends._check_endpoint_availability')
    def test_detect_lmstudio_first(self, mock_check):
        """Test LM Studio is detected when available."""
        def mock_availability(url, timeout=3):
            return url == "http://localhost:1234/v1/models"

        mock_check.side_effect = mock_availability

        backend_type, config = detect_backend("any-model")
        assert backend_type == "lmstudio"
        assert config["api_base"] == "http://localhost:1234/v1"
        assert config["api_key_env"] is None

    @patch('backends._check_endpoint_availability')
    def test_detect_ollama_second(self, mock_check):
        """Test Ollama is detected when LM Studio unavailable but Ollama available."""
        def mock_availability(url, timeout=3):
            return url == "http://localhost:11434/api/tags"

        mock_check.side_effect = mock_availability

        backend_type, config = detect_backend("any-model")
        assert backend_type == "ollama"
        assert config["api_base"] == "http://localhost:11434"
        assert config["api_key_env"] is None

    @patch('backends._check_endpoint_availability')
    def test_detect_openrouter_fallback(self, mock_check):
        """Test OpenRouter is used when no local backends available."""
        mock_check.return_value = False  # No local backends available

        backend_type, config = detect_backend("any-model")
        assert backend_type == "openrouter"
        assert config["api_base"] == "https://openrouter.ai/api/v1"
        assert config["api_key_env"] == "OPENROUTER_API_KEY"


class TestBackendConfiguration:
    """Test backend configuration setup."""

    @patch('backends._check_endpoint_availability')
    def test_configure_lmstudio(self, mock_check):
        """Test LM Studio configuration."""
        def mock_availability(url, timeout=3):
            return url == "http://localhost:1234/v1/models"

        mock_check.side_effect = mock_availability

        model = "test-model"
        formatted_model = configure_backend(model)

        assert formatted_model == f"openai/{model}"
        assert os.environ["OPENAI_API_BASE"] == "http://localhost:1234/v1"
        assert os.environ["OPENAI_API_KEY"] == "lm-studio"

    @patch('backends._check_endpoint_availability')
    def test_configure_ollama(self, mock_check):
        """Test Ollama configuration."""
        def mock_availability(url, timeout=3):
            return url == "http://localhost:11434/api/tags"

        mock_check.side_effect = mock_availability

        model = "test-model"
        formatted_model = configure_backend(model)

        assert formatted_model == f"ollama/{model}"
        assert os.environ["OLLAMA_API_BASE"] == "http://localhost:11434"

    @patch('backends._check_endpoint_availability')
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False)
    def test_configure_openrouter(self, mock_check):
        """Test OpenRouter configuration."""
        mock_check.return_value = False  # No local backends available

        model = "test-model"
        formatted_model = configure_backend(model)

        assert formatted_model == f"openai/{model}"
        assert os.environ["OPENAI_API_BASE"] == "https://openrouter.ai/api/v1"

    @patch('backends._check_endpoint_availability')
    def test_configure_openrouter_missing_key(self, mock_check):
        """Test OpenRouter configuration without API key."""
        mock_check.return_value = False  # No local backends available

        with patch.dict(os.environ, {}, clear=True):
            model = "test-model"
            with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
                configure_backend(model)


class TestBackendInfo:
    """Test backend information retrieval."""

    @patch('backends._check_endpoint_availability')
    def test_get_lmstudio_info(self, mock_check):
        """Test LM Studio backend info."""
        def mock_availability(url, timeout=3):
            return url == "http://localhost:1234/v1/models"

        mock_check.side_effect = mock_availability

        model = "test-model"
        info = get_backend_info(model)

        assert info["backend"] == "lmstudio"
        assert info["api_base"] == "http://localhost:1234/v1"
        assert info["requires_key"] is False
        assert info["key_env_var"] == ""

    @patch('backends._check_endpoint_availability')
    def test_get_ollama_info(self, mock_check):
        """Test Ollama backend info."""
        def mock_availability(url, timeout=3):
            return url == "http://localhost:11434/api/tags"

        mock_check.side_effect = mock_availability

        model = "test-model"
        info = get_backend_info(model)

        assert info["backend"] == "ollama"
        assert info["api_base"] == "http://localhost:11434"
        assert info["requires_key"] is False
        assert info["key_env_var"] == ""

    @patch('backends._check_endpoint_availability')
    def test_get_openrouter_info(self, mock_check):
        """Test OpenRouter backend info."""
        mock_check.return_value = False  # No local backends available

        model = "test-model"
        info = get_backend_info(model)

        assert info["backend"] == "openrouter"
        assert info["api_base"] == "https://openrouter.ai/api/v1"
        assert info["requires_key"] is True
        assert info["key_env_var"] == "OPENROUTER_API_KEY"


class TestBackendConnection:
    """Test backend connectivity."""

    @patch('backends._check_endpoint_availability')
    def test_lmstudio_connection(self, mock_check):
        """Test LM Studio connection check."""
        def mock_availability(url, timeout=3):
            return url == "http://localhost:1234/v1/models"

        mock_check.side_effect = mock_availability

        model = "test-model"
        result = check_backend_connection(model)

        assert result is True
        mock_check.assert_called_with("http://localhost:1234/v1/models")

    @patch('backends._check_endpoint_availability')
    def test_ollama_connection(self, mock_check):
        """Test Ollama connection check."""
        def mock_availability(url, timeout=3):
            return url == "http://localhost:11434/api/tags"

        mock_check.side_effect = mock_availability

        model = "test-model"
        result = check_backend_connection(model)

        assert result is True
        mock_check.assert_called_with("http://localhost:11434/api/tags")

    @patch('backends._check_endpoint_availability')
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False)
    def test_openrouter_connection_with_key(self, mock_check):
        """Test OpenRouter connection check with API key."""
        mock_check.return_value = False  # No local backends available

        model = "test-model"
        result = check_backend_connection(model)

        assert result is True

    @patch('backends._check_endpoint_availability')
    def test_openrouter_connection_without_key(self, mock_check):
        """Test OpenRouter connection check without API key."""
        mock_check.return_value = False  # No local backends available

        with patch.dict(os.environ, {}, clear=True):
            model = "test-model"
            result = check_backend_connection(model)

            assert result is False
