"""Tests for serializer validation."""
import pytest
from rest_framework.exceptions import ValidationError

from chat.serializers import (
    ConversationSerializer,
    UpdateConversationSerializer,
    CreateMessageSerializer,
    CreateFeedbackSerializer,
    FeedbackSerializer,
    MessageSerializer,
)
from chat.models import Conversation, Message, Feedback


@pytest.mark.django_db
class TestConversationSerializer:
    """Tests for ConversationSerializer."""
    
    def test_serialize_conversation(self):
        """Test serializing a conversation."""
        conv = Conversation.objects.create(title="Test Conversation")
        serializer = ConversationSerializer(conv)
        data = serializer.data
        
        assert data["id"] == conv.id
        assert data["title"] == "Test Conversation"
        assert "created_at" in data
        assert "updated_at" in data
        assert "quality_score" in data
    
    def test_quality_score_calculation(self):
        """Test quality score is calculated correctly."""
        conv = Conversation.objects.create(title="Test")
        msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI", sequence=1)
        Feedback.objects.create(message=msg, rating=True)
        
        serializer = ConversationSerializer(conv)
        data = serializer.data
        
        assert data["quality_score"] is not None
        assert isinstance(data["quality_score"], (int, float))


class TestUpdateConversationSerializer:
    """Tests for UpdateConversationSerializer."""
    
    def test_valid_title(self):
        """Test validation with valid title."""
        serializer = UpdateConversationSerializer(data={"title": "New Title"})
        assert serializer.is_valid()
        assert serializer.validated_data["title"] == "New Title"
    
    def test_empty_title(self):
        """Test validation with empty title."""
        serializer = UpdateConversationSerializer(data={"title": ""})
        assert serializer.is_valid()
        assert serializer.validated_data["title"] is None
    
    def test_whitespace_only_title(self):
        """Test validation with whitespace-only title."""
        serializer = UpdateConversationSerializer(data={"title": "   "})
        assert serializer.is_valid()
        assert serializer.validated_data["title"] is None
    
    def test_none_title(self):
        """Test validation with None title."""
        serializer = UpdateConversationSerializer(data={"title": None})
        assert serializer.is_valid()
        assert serializer.validated_data["title"] is None
    
    def test_title_too_long(self):
        """Test validation with title exceeding max length."""
        long_title = "x" * 201
        serializer = UpdateConversationSerializer(data={"title": long_title})
        assert not serializer.is_valid()
        assert "title" in serializer.errors


class TestCreateMessageSerializer:
    """Tests for CreateMessageSerializer."""
    
    def test_valid_text(self):
        """Test validation with valid text."""
        serializer = CreateMessageSerializer(data={"text": "Hello, world!"})
        assert serializer.is_valid()
        assert serializer.validated_data["text"] == "Hello, world!"
    
    def test_empty_text(self):
        """Test validation with empty text."""
        serializer = CreateMessageSerializer(data={"text": ""})
        assert not serializer.is_valid()
        assert "text" in serializer.errors
    
    def test_whitespace_only_text(self):
        """Test validation with whitespace-only text."""
        serializer = CreateMessageSerializer(data={"text": "   "})
        assert not serializer.is_valid()
        assert "text" in serializer.errors
    
    def test_text_too_long(self):
        """Test validation with text exceeding max length."""
        long_text = "x" * 1001
        serializer = CreateMessageSerializer(data={"text": long_text})
        assert not serializer.is_valid()
        assert "text" in serializer.errors
    
    def test_text_at_max_length(self):
        """Test validation with text at max length."""
        max_text = "x" * 1000
        serializer = CreateMessageSerializer(data={"text": max_text})
        assert serializer.is_valid()
    
    def test_text_trimmed(self):
        """Test that text is trimmed."""
        serializer = CreateMessageSerializer(data={"text": "  Hello  "})
        assert serializer.is_valid()
        assert serializer.validated_data["text"] == "Hello"


class TestCreateFeedbackSerializer:
    """Tests for CreateFeedbackSerializer."""
    
    def test_valid_positive_feedback(self):
        """Test validation with valid positive feedback."""
        serializer = CreateFeedbackSerializer(data={"rating": True, "note": "Great!"})
        assert serializer.is_valid()
        assert serializer.validated_data["rating"] is True
        assert serializer.validated_data["note"] == "Great!"
    
    def test_valid_negative_feedback(self):
        """Test validation with valid negative feedback."""
        serializer = CreateFeedbackSerializer(data={"rating": False})
        assert serializer.is_valid()
        assert serializer.validated_data["rating"] is False
    
    def test_feedback_without_note(self):
        """Test validation without note."""
        serializer = CreateFeedbackSerializer(data={"rating": True})
        assert serializer.is_valid()
        assert serializer.validated_data.get("note") is None
    
    def test_feedback_empty_note(self):
        """Test validation with empty note."""
        serializer = CreateFeedbackSerializer(data={"rating": True, "note": ""})
        assert serializer.is_valid()
        assert serializer.validated_data["note"] == ""
    
    def test_feedback_note_too_long(self):
        """Test validation with note exceeding max length."""
        long_note = "x" * 1001
        serializer = CreateFeedbackSerializer(data={"rating": True, "note": long_note})
        assert not serializer.is_valid()
        assert "note" in serializer.errors
    
    def test_missing_rating(self):
        """Test validation with missing rating."""
        serializer = CreateFeedbackSerializer(data={"note": "Test"})
        assert not serializer.is_valid()
        assert "rating" in serializer.errors


@pytest.mark.django_db
class TestFeedbackSerializer:
    """Tests for FeedbackSerializer."""
    
    def test_serialize_feedback(self):
        """Test serializing feedback."""
        conv = Conversation.objects.create(title="Test")
        msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI", sequence=1)
        feedback = Feedback.objects.create(message=msg, rating=True, note="Great!")
        
        serializer = FeedbackSerializer(feedback)
        data = serializer.data
        
        assert data["id"] == feedback.id
        assert data["rating"] is True
        assert data["note"] == "Great!"
        assert "created_at" in data
        assert "updated_at" in data


@pytest.mark.django_db
class TestMessageSerializer:
    """Tests for MessageSerializer."""
    
    def test_serialize_message_without_feedback(self):
        """Test serializing message without feedback."""
        conv = Conversation.objects.create(title="Test")
        msg = Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="Hello", sequence=1)
        
        serializer = MessageSerializer(msg)
        data = serializer.data
        
        assert data["id"] == msg.id
        assert data["role"] == "user"
        assert data["text"] == "Hello"
        assert data["feedback"] is None
    
    def test_serialize_message_with_feedback(self):
        """Test serializing message with feedback."""
        conv = Conversation.objects.create(title="Test")
        msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI response", sequence=1)
        feedback = Feedback.objects.create(message=msg, rating=True, note="Helpful")
        
        serializer = MessageSerializer(msg)
        data = serializer.data
        
        assert data["feedback"] is not None
        assert data["feedback"]["rating"] is True
        assert data["feedback"]["note"] == "Helpful"
