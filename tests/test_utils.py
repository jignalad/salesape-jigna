"""Tests for utility functions."""
import pytest
from unittest.mock import Mock

from chat.models import Conversation, Message, Feedback
from chat.utils import (
    parse_int_query_param,
    calculate_quality_score,
    extract_feedback_themes,
    STOP_WORDS,
)


class TestParseIntQueryParam:
    """Tests for parse_int_query_param utility."""
    
    def test_valid_int(self):
        """Test parsing a valid integer."""
        request = Mock()
        request.query_params = {"limit": "10"}
        result = parse_int_query_param(request, "limit", 20)
        assert result == 10
    
    def test_default_value(self):
        """Test using default value when param is missing."""
        request = Mock()
        request.query_params = {}
        result = parse_int_query_param(request, "limit", 20)
        assert result == 20
    
    def test_invalid_value(self):
        """Test handling invalid value."""
        request = Mock()
        request.query_params = {"limit": "abc"}
        result = parse_int_query_param(request, "limit", 20)
        assert result == 20  # Returns default
    
    def test_min_value_enforcement(self):
        """Test minimum value enforcement."""
        request = Mock()
        request.query_params = {"limit": "-5"}
        result = parse_int_query_param(request, "limit", 20, min_val=1)
        assert result == 1
    
    def test_max_value_enforcement(self):
        """Test maximum value enforcement."""
        request = Mock()
        request.query_params = {"limit": "200"}
        result = parse_int_query_param(request, "limit", 20, max_val=100)
        assert result == 100
    
    def test_min_and_max_enforcement(self):
        """Test both min and max value enforcement."""
        request = Mock()
        request.query_params = {"limit": "50"}
        result = parse_int_query_param(request, "limit", 20, min_val=1, max_val=100)
        assert result == 50
        
        request.query_params = {"limit": "0"}
        result = parse_int_query_param(request, "limit", 20, min_val=1, max_val=100)
        assert result == 1
        
        request.query_params = {"limit": "150"}
        result = parse_int_query_param(request, "limit", 20, min_val=1, max_val=100)
        assert result == 100


@pytest.mark.django_db
class TestCalculateQualityScore:
    """Tests for calculate_quality_score utility."""
    
    def test_no_ai_messages(self):
        """Test quality score when there are no AI messages."""
        conv = Conversation.objects.create(title="Test")
        Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="Hello", sequence=1)
        
        score = calculate_quality_score(conv)
        assert score is None
    
    def test_no_feedback(self):
        """Test quality score when there are no feedback."""
        conv = Conversation.objects.create(title="Test")
        Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI response", sequence=1)
        
        score = calculate_quality_score(conv)
        assert score is None
    
    def test_all_positive_feedback(self):
        """Test quality score with all positive feedback."""
        conv = Conversation.objects.create(title="Test")
        msg1 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 1", sequence=1)
        msg2 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 2", sequence=2)
        
        Feedback.objects.create(message=msg1, rating=True)
        Feedback.objects.create(message=msg2, rating=True)
        
        score = calculate_quality_score(conv)
        assert score is not None
        # With 100% positive feedback and 100% feedback rate, score should be high
        assert score >= 90
    
    def test_all_negative_feedback(self):
        """Test quality score with all negative feedback."""
        conv = Conversation.objects.create(title="Test")
        msg1 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 1", sequence=1)
        msg2 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 2", sequence=2)
        
        Feedback.objects.create(message=msg1, rating=False)
        Feedback.objects.create(message=msg2, rating=False)
        
        score = calculate_quality_score(conv)
        assert score is not None
        # With 0% positive feedback but 100% feedback rate
        # Score = (0.0 * 0.7 + 1.0 * 0.3) * 100 = 30.0
        assert score == 30.0
    
    def test_mixed_feedback(self):
        """Test quality score with mixed feedback."""
        conv = Conversation.objects.create(title="Test")
        msg1 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 1", sequence=1)
        msg2 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 2", sequence=2)
        msg3 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 3", sequence=3)
        
        Feedback.objects.create(message=msg1, rating=True)
        Feedback.objects.create(message=msg2, rating=True)
        Feedback.objects.create(message=msg3, rating=False)
        
        score = calculate_quality_score(conv)
        assert score is not None
        # With 66.7% positive feedback and 100% feedback rate
        # Score = (0.667 * 0.7 + 1.0 * 0.3) * 100 = 76.69
        assert 70 < score < 80
    
    def test_partial_feedback_rate(self):
        """Test quality score with partial feedback rate."""
        conv = Conversation.objects.create(title="Test")
        msg1 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 1", sequence=1)
        msg2 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 2", sequence=2)
        msg3 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 3", sequence=3)
        
        Feedback.objects.create(message=msg1, rating=True)
        # Only 1 out of 3 messages has feedback
        
        score = calculate_quality_score(conv)
        assert score is not None
        # With 100% positive feedback but only 33% feedback rate
        # Score = (1.0 * 0.7 + 0.33 * 0.3) * 100 = 79.9
        assert 75 < score < 85


@pytest.mark.django_db
class TestExtractFeedbackThemes:
    """Tests for extract_feedback_themes utility."""
    
    def test_empty_notes(self):
        """Test with empty feedback notes."""
        from django.db.models import QuerySet
        notes = Feedback.objects.none()
        themes = extract_feedback_themes(notes)
        assert themes == []
    
    def test_single_note(self):
        """Test extracting themes from a single note."""
        conv = Conversation.objects.create(title="Test")
        msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI", sequence=1)
        Feedback.objects.create(message=msg, rating=True, note="This response was excellent and helpful")
        
        notes = Feedback.objects.exclude(note__isnull=True).exclude(note="").values_list('note', flat=True)
        themes = extract_feedback_themes(notes)
        
        assert len(themes) > 0
        theme_words = [t["word"] for t in themes]
        # Should extract meaningful words, filtering out stop words
        assert any(len(word) > 3 for word in theme_words)
    
    def test_multiple_notes(self):
        """Test extracting themes from multiple notes."""
        conv = Conversation.objects.create(title="Test")
        msg1 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 1", sequence=1)
        msg2 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 2", sequence=2)
        msg3 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 3", sequence=3)
        Feedback.objects.create(message=msg1, rating=True, note="Python programming is great")
        Feedback.objects.create(message=msg2, rating=True, note="Python code examples were helpful")
        Feedback.objects.create(message=msg3, rating=True, note="Excellent Python tutorial")
        
        notes = Feedback.objects.exclude(note__isnull=True).exclude(note="").values_list('note', flat=True)
        themes = extract_feedback_themes(notes, top_n=5)
        
        assert len(themes) > 0
        theme_words = [t["word"] for t in themes]
        # "python" should appear multiple times
        python_count = sum(1 for t in themes if t["word"] == "python")
        assert python_count > 0
    
    def test_stop_words_filtered(self):
        """Test that stop words are filtered out."""
        conv = Conversation.objects.create(title="Test")
        msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI", sequence=1)
        Feedback.objects.create(message=msg, rating=True, note="the and or but this that")
        
        notes = Feedback.objects.exclude(note__isnull=True).exclude(note="").values_list('note', flat=True)
        themes = extract_feedback_themes(notes)
        
        theme_words = [t["word"] for t in themes]
        # Stop words should not appear
        assert "the" not in theme_words
        assert "and" not in theme_words
        assert "or" not in theme_words
    
    def test_short_words_filtered(self):
        """Test that short words (<=3 chars) are filtered out."""
        conv = Conversation.objects.create(title="Test")
        msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI", sequence=1)
        Feedback.objects.create(message=msg, rating=True, note="a be cat dog elephant")
        
        notes = Feedback.objects.exclude(note__isnull=True).exclude(note="").values_list('note', flat=True)
        themes = extract_feedback_themes(notes)
        
        theme_words = [t["word"] for t in themes]
        # Short words should not appear
        assert "a" not in theme_words
        assert "be" not in theme_words
        # Longer words should appear
        assert any(len(word) > 3 for word in theme_words)
    
    def test_top_n_parameter(self):
        """Test that top_n parameter limits results."""
        conv = Conversation.objects.create(title="Test")
        msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI", sequence=1)
        # Create multiple unique words
        Feedback.objects.create(message=msg, rating=True, note="apple banana cherry date elderberry fig grape")
        
        notes = Feedback.objects.exclude(note__isnull=True).exclude(note="").values_list('note', flat=True)
        themes = extract_feedback_themes(notes, top_n=3)
        
        assert len(themes) <= 3
    
    def test_case_insensitive(self):
        """Test that extraction is case insensitive."""
        conv = Conversation.objects.create(title="Test")
        msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI", sequence=1)
        Feedback.objects.create(message=msg, rating=True, note="Python PYTHON python")
        
        notes = Feedback.objects.exclude(note__isnull=True).exclude(note="").values_list('note', flat=True)
        themes = extract_feedback_themes(notes)
        
        # Should count all variations as one word
        python_theme = next((t for t in themes if t["word"] == "python"), None)
        assert python_theme is not None
        assert python_theme["count"] == 3
