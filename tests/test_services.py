"""Tests for service functions."""
import os
import pytest
from unittest.mock import Mock, patch, MagicMock

from chat.services import gemini


class TestGeminiService:
    """Tests for Gemini service functions."""
    
    def test_get_model_name_default(self, monkeypatch):
        """Test default model name when env var is not set."""
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        model_name = gemini._get_model_name()
        assert model_name == "gemini-2.5-flash"
    
    def test_get_model_name_from_env(self, monkeypatch):
        """Test model name from environment variable."""
        monkeypatch.setenv("GEMINI_MODEL", "gemini-1.5-pro")
        model_name = gemini._get_model_name()
        assert model_name == "gemini-1.5-pro"
    
    def test_generate_reply_missing_api_key(self, monkeypatch):
        """Test error when API key is missing."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        
        with pytest.raises(gemini.GeminiServiceError) as exc_info:
            gemini.generate_reply(history=[], prompt="Test")
        
        assert "API key" in str(exc_info.value)
    
    @patch('google.genai')
    def test_generate_reply_success(self, mock_genai, monkeypatch):
        """Test successful reply generation."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        
        # Mock the client and response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "AI Response"
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client
        
        result = gemini.generate_reply(history=[], prompt="Test prompt")
        
        assert result == "AI Response"
        mock_client.models.generate_content.assert_called_once()
        call_args = mock_client.models.generate_content.call_args
        assert call_args[1]["model"] == "gemini-2.5-flash"
        assert call_args[1]["contents"] == "Test prompt"
    
    @patch('google.genai')
    def test_generate_reply_empty_response(self, mock_genai, monkeypatch):
        """Test error when response is empty."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = ""
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client
        
        with pytest.raises(gemini.GeminiServiceError) as exc_info:
            gemini.generate_reply(history=[], prompt="Test")
        
        assert "Empty response" in str(exc_info.value)
    
    @patch('google.genai')
    def test_generate_reply_whitespace_only(self, mock_genai, monkeypatch):
        """Test error when response is only whitespace."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "   \n\t  "
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client
        
        with pytest.raises(gemini.GeminiServiceError) as exc_info:
            gemini.generate_reply(history=[], prompt="Test")
        
        assert "Empty response" in str(exc_info.value)
    
    @patch('google.genai')
    def test_generate_reply_no_text_attribute(self, mock_genai, monkeypatch):
        """Test handling when response has no text attribute."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        del mock_response.text  # Remove text attribute
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client
        
        with pytest.raises(gemini.GeminiServiceError) as exc_info:
            gemini.generate_reply(history=[], prompt="Test")
        
        assert "Empty response" in str(exc_info.value)
    
    def test_generate_reply_import_error(self, monkeypatch):
        """Test error when genai module cannot be imported."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        
        with patch.dict('sys.modules', {'google.genai': None}):
            with pytest.raises(gemini.GeminiServiceError) as exc_info:
                gemini.generate_reply(history=[], prompt="Test")
        
        # The error message may vary, but should indicate the import failed
        assert "request failed" in str(exc_info.value).lower() or "not available" in str(exc_info.value).lower()
    
    @patch('google.genai')
    def test_generate_reply_api_exception(self, mock_genai, monkeypatch):
        """Test handling of API exceptions."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("API Error")
        mock_genai.Client.return_value = mock_client
        
        with pytest.raises(gemini.GeminiServiceError) as exc_info:
            gemini.generate_reply(history=[], prompt="Test")
        
        assert "request failed" in str(exc_info.value).lower()
        assert "API Error" in str(exc_info.value)
    
    @patch('google.genai')
    def test_generate_reply_with_history(self, mock_genai, monkeypatch):
        """Test reply generation with history context."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Response"
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client
        
        history = [
            {"role": "user", "text": "Hello"},
            {"role": "ai", "text": "Hi there"},
        ]
        
        result = gemini.generate_reply(history=history, prompt="How are you?")
        
        assert result == "Response"
        # Note: Current implementation doesn't use history, but we test it doesn't break
        mock_client.models.generate_content.assert_called_once()
    
    @patch('google.genai')
    def test_generate_reply_timeout_parameter(self, mock_genai, monkeypatch):
        """Test that timeout parameter is accepted (even if not used)."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Response"
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client
        
        result = gemini.generate_reply(history=[], prompt="Test", timeout_s=30)
        
        assert result == "Response"
        # Function should accept timeout_s parameter without error
