"""Comprehensive tests for all API endpoints."""
import json
import pytest
from django.urls import reverse
from django.utils import timezone

from chat.models import Conversation, Message, Feedback
from chat.services import gemini


@pytest.mark.django_db
class TestConversationListCreateView:
    """Tests for GET and POST /api/conversations/"""
    
    def test_list_conversations_empty(self, client):
        """Test listing conversations when none exist."""
        resp = client.get("/api/conversations/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["results"] == []
    
    def test_list_conversations_with_data(self, client):
        """Test listing conversations with data."""
        conv1 = Conversation.objects.create(title="First")
        conv2 = Conversation.objects.create(title="Second")
        
        resp = client.get("/api/conversations/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert len(data["results"]) == 2
        assert data["results"][0]["id"] == conv2.id  # Newest first
    
    def test_list_conversations_pagination(self, client):
        """Test pagination parameters."""
        for i in range(5):
            Conversation.objects.create(title=f"Conv {i}")
        
        resp = client.get("/api/conversations/?limit=2&offset=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 5
        assert len(data["results"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 1
    
    def test_list_conversations_invalid_params(self, client):
        """Test handling of invalid query parameters."""
        Conversation.objects.create(title="Test")
        
        # Invalid limit
        resp = client.get("/api/conversations/?limit=abc")
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 20  # Default
        
        # Invalid offset
        resp = client.get("/api/conversations/?offset=xyz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["offset"] == 0  # Default
    
    def test_list_conversations_limit_bounds(self, client):
        """Test limit bounds enforcement."""
        Conversation.objects.create(title="Test")
        
        # Over max limit
        resp = client.get("/api/conversations/?limit=200")
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 100  # Max is 100
        
        # Negative limit
        resp = client.get("/api/conversations/?limit=-5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 1  # Min is 1
    
    def test_create_conversation_with_title(self, client):
        """Test creating a conversation with a title."""
        resp = client.post(
            "/api/conversations/",
            data=json.dumps({"title": "My Chat"}),
            content_type="application/json"
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "My Chat"
        assert "id" in data
        assert "created_at" in data
    
    def test_create_conversation_without_title(self, client):
        """Test creating a conversation without a title."""
        resp = client.post(
            "/api/conversations/",
            data=json.dumps({}),
            content_type="application/json"
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] is None
    
    def test_create_conversation_empty_title(self, client):
        """Test creating a conversation with empty title."""
        resp = client.post(
            "/api/conversations/",
            data=json.dumps({"title": ""}),
            content_type="application/json"
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] is None


@pytest.mark.django_db
class TestConversationDetailView:
    """Tests for GET and PATCH /api/conversations/<id>/"""
    
    def test_get_conversation(self, client):
        """Test retrieving a conversation."""
        conv = Conversation.objects.create(title="Test Conversation")
        resp = client.get(f"/api/conversations/{conv.id}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == conv.id
        assert data["title"] == "Test Conversation"
    
    def test_get_nonexistent_conversation(self, client):
        """Test retrieving a non-existent conversation."""
        resp = client.get("/api/conversations/999/")
        assert resp.status_code == 404
    
    def test_patch_conversation_title(self, client):
        """Test updating a conversation title."""
        conv = Conversation.objects.create(title="Old Title")
        resp = client.patch(
            f"/api/conversations/{conv.id}/",
            data=json.dumps({"title": "New Title"}),
            content_type="application/json"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "New Title"
        conv.refresh_from_db()
        assert conv.title == "New Title"
    
    def test_patch_conversation_empty_title(self, client):
        """Test clearing a conversation title."""
        conv = Conversation.objects.create(title="Old Title")
        resp = client.patch(
            f"/api/conversations/{conv.id}/",
            data=json.dumps({"title": ""}),
            content_type="application/json"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] is None
        conv.refresh_from_db()
        assert conv.title is None
    
    def test_patch_conversation_invalid_data(self, client):
        """Test updating with invalid data."""
        conv = Conversation.objects.create(title="Test")
        resp = client.patch(
            f"/api/conversations/{conv.id}/",
            data=json.dumps({"title": "x" * 300}),  # Too long
            content_type="application/json"
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestMessageListCreateView:
    """Tests for GET and POST /api/conversations/<id>/messages/"""
    
    def test_list_messages_empty(self, client):
        """Test listing messages when none exist."""
        conv = Conversation.objects.create(title="Test")
        resp = client.get(f"/api/conversations/{conv.id}/messages/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []
        assert data["lastSeq"] == 0
    
    def test_list_messages(self, client):
        """Test listing messages."""
        conv = Conversation.objects.create(title="Test")
        msg1 = Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="Hello", sequence=1)
        msg2 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="Hi", sequence=2)
        
        resp = client.get(f"/api/conversations/{conv.id}/messages/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 2
        assert data["lastSeq"] == 2
    
    def test_list_messages_with_since(self, client):
        """Test listing messages with since parameter."""
        conv = Conversation.objects.create(title="Test")
        msg1 = Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="Hello", sequence=1)
        msg2 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="Hi", sequence=2)
        msg3 = Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="How are you?", sequence=3)
        
        resp = client.get(f"/api/conversations/{conv.id}/messages/?since=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["sequence"] == 3
    
    def test_list_messages_with_limit(self, client):
        """Test listing messages with limit."""
        conv = Conversation.objects.create(title="Test")
        for i in range(5):
            Message.objects.create(conversation=conv, role=Message.ROLE_USER, text=f"Msg {i}", sequence=i+1)
        
        resp = client.get(f"/api/conversations/{conv.id}/messages/?limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 2
    
    def test_list_messages_invalid_params(self, client):
        """Test handling of invalid query parameters."""
        conv = Conversation.objects.create(title="Test")
        Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="Hello", sequence=1)
        
        # Invalid since
        resp = client.get(f"/api/conversations/{conv.id}/messages/?since=abc")
        assert resp.status_code == 200
        data = resp.json()
        # When since is invalid, it defaults to 0, but lastSeq will be the last message sequence
        assert data["lastSeq"] == 1  # Last message sequence
        
        # Invalid limit
        resp = client.get(f"/api/conversations/{conv.id}/messages/?limit=xyz")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 50  # Default limit
    
    def test_create_message_success(self, client, monkeypatch):
        """Test creating a message successfully."""
        conv = Conversation.objects.create(title="Test")
        
        def fake_generate_reply(history, prompt, timeout_s=10):
            return "AI Response"
        
        monkeypatch.setattr(gemini, "generate_reply", fake_generate_reply)
        
        resp = client.post(
            f"/api/conversations/{conv.id}/messages/",
            data=json.dumps({"text": "Hello"}),
            content_type="application/json"
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["user_message"]["role"] == "user"
        assert data["user_message"]["text"] == "Hello"
        assert data["ai_message"]["role"] == "ai"
        assert data["ai_message"]["text"] == "AI Response"
    
    def test_create_message_auto_title(self, client, monkeypatch):
        """Test auto-generating conversation title from first message."""
        conv = Conversation.objects.create(title=None)
        
        def fake_generate_reply(history, prompt, timeout_s=10):
            return "AI Response"
        
        monkeypatch.setattr(gemini, "generate_reply", fake_generate_reply)
        
        resp = client.post(
            f"/api/conversations/{conv.id}/messages/",
            data=json.dumps({"text": "This is a very long message that should be truncated"}),
            content_type="application/json"
        )
        assert resp.status_code == 201
        conv.refresh_from_db()
        assert conv.title is not None
        assert len(conv.title) <= 53  # 50 chars + "..."
        assert conv.title.endswith("...")
    
    def test_create_message_empty_text(self, client):
        """Test creating a message with empty text."""
        conv = Conversation.objects.create(title="Test")
        resp = client.post(
            f"/api/conversations/{conv.id}/messages/",
            data=json.dumps({"text": "   "}),
            content_type="application/json"
        )
        assert resp.status_code == 400
    
    def test_create_message_too_long(self, client):
        """Test creating a message that's too long."""
        conv = Conversation.objects.create(title="Test")
        resp = client.post(
            f"/api/conversations/{conv.id}/messages/",
            data=json.dumps({"text": "x" * 1001}),
            content_type="application/json"
        )
        assert resp.status_code == 400
    
    def test_create_message_gemini_error(self, client, monkeypatch):
        """Test handling Gemini service errors."""
        conv = Conversation.objects.create(title="Test")
        
        def fake_generate_reply(history, prompt, timeout_s=10):
            raise gemini.GeminiServiceError("API Error")
        
        monkeypatch.setattr(gemini, "generate_reply", fake_generate_reply)
        
        resp = client.post(
            f"/api/conversations/{conv.id}/messages/",
            data=json.dumps({"text": "Hello"}),
            content_type="application/json"
        )
        assert resp.status_code == 502
        # User message should still be created
        assert Message.objects.filter(conversation=conv, role=Message.ROLE_USER).count() == 1


@pytest.mark.django_db
class TestMessageFeedbackView:
    """Tests for GET and POST /api/messages/<id>/feedback/"""
    
    def test_create_feedback_positive(self, client):
        """Test creating positive feedback."""
        conv = Conversation.objects.create(title="Test")
        msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI response", sequence=1)
        
        resp = client.post(
            f"/api/messages/{msg.id}/feedback/",
            data=json.dumps({"rating": True, "note": "Great response!"}),
            content_type="application/json"
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["rating"] is True
        assert data["note"] == "Great response!"
        
        feedback = Feedback.objects.get(message=msg)
        assert feedback.rating is True
        assert feedback.note == "Great response!"
    
    def test_create_feedback_negative(self, client):
        """Test creating negative feedback."""
        conv = Conversation.objects.create(title="Test")
        msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI response", sequence=1)
        
        resp = client.post(
            f"/api/messages/{msg.id}/feedback/",
            data=json.dumps({"rating": False}),
            content_type="application/json"
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["rating"] is False
        assert data["note"] == ""
    
    def test_update_feedback(self, client):
        """Test updating existing feedback."""
        conv = Conversation.objects.create(title="Test")
        msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI response", sequence=1)
        feedback = Feedback.objects.create(message=msg, rating=True, note="Initial")
        
        resp = client.post(
            f"/api/messages/{msg.id}/feedback/",
            data=json.dumps({"rating": False, "note": "Updated"}),
            content_type="application/json"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rating"] is False
        assert data["note"] == "Updated"
        
        feedback.refresh_from_db()
        assert feedback.rating is False
        assert feedback.note == "Updated"
    
    def test_create_feedback_user_message(self, client):
        """Test that feedback can only be created for AI messages."""
        conv = Conversation.objects.create(title="Test")
        msg = Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="User message", sequence=1)
        
        resp = client.post(
            f"/api/messages/{msg.id}/feedback/",
            data=json.dumps({"rating": True}),
            content_type="application/json"
        )
        assert resp.status_code == 400
        assert "AI messages" in resp.json()["detail"]
    
    def test_get_feedback(self, client):
        """Test retrieving feedback."""
        conv = Conversation.objects.create(title="Test")
        msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI response", sequence=1)
        feedback = Feedback.objects.create(message=msg, rating=True, note="Test note")
        
        resp = client.get(f"/api/messages/{msg.id}/feedback/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rating"] is True
        assert data["note"] == "Test note"
    
    def test_get_feedback_not_found(self, client):
        """Test retrieving feedback when none exists."""
        conv = Conversation.objects.create(title="Test")
        msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI response", sequence=1)
        
        resp = client.get(f"/api/messages/{msg.id}/feedback/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestInsightsView:
    """Tests for GET /api/insights/"""
    
    def test_insights_empty(self, client):
        """Test insights when no data exists."""
        resp = client.get("/api/insights/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["usage"]["total_conversations"] == 0
        assert data["usage"]["total_messages"] == 0
        assert data["feedback"]["total_feedback"] == 0
        assert data["themes"] == []
        assert data["quality_scores"]["average"] is None
    
    def test_insights_usage_statistics(self, client):
        """Test usage statistics calculation."""
        conv1 = Conversation.objects.create(title="Conv 1")
        conv2 = Conversation.objects.create(title="Conv 2")
        
        Message.objects.create(conversation=conv1, role=Message.ROLE_USER, text="Hello", sequence=1)
        Message.objects.create(conversation=conv1, role=Message.ROLE_AI, text="Hi", sequence=2)
        Message.objects.create(conversation=conv2, role=Message.ROLE_USER, text="Test", sequence=1)
        
        resp = client.get("/api/insights/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["usage"]["total_conversations"] == 2
        assert data["usage"]["total_messages"] == 3
        assert data["usage"]["total_user_messages"] == 2
        assert data["usage"]["total_ai_messages"] == 1
    
    def test_insights_feedback_statistics(self, client):
        """Test feedback statistics calculation."""
        conv = Conversation.objects.create(title="Test")
        msg1 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 1", sequence=1)
        msg2 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 2", sequence=2)
        msg3 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 3", sequence=3)
        
        Feedback.objects.create(message=msg1, rating=True)
        Feedback.objects.create(message=msg2, rating=True)
        Feedback.objects.create(message=msg3, rating=False)
        
        resp = client.get("/api/insights/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["feedback"]["total_feedback"] == 3
        assert data["feedback"]["positive_feedback"] == 2
        assert data["feedback"]["negative_feedback"] == 1
        assert data["feedback"]["satisfaction_rate"] == pytest.approx(66.67, abs=0.01)
        assert data["feedback"]["feedback_rate"] == pytest.approx(100.0, abs=0.01)
    
    def test_insights_feedback_themes(self, client):
        """Test feedback theme extraction."""
        conv = Conversation.objects.create(title="Test")
        msg1 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 1", sequence=1)
        msg2 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 2", sequence=2)
        
        Feedback.objects.create(message=msg1, rating=True, note="This response was excellent and helpful")
        Feedback.objects.create(message=msg2, rating=True, note="Very helpful response about Python programming")
        
        resp = client.get("/api/insights/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["themes"]) > 0
        # Should extract meaningful words
        theme_words = [t["word"] for t in data["themes"]]
        assert any("helpful" in word or "excellent" in word or "python" in word or "programming" in word 
                   for word in theme_words)
    
    def test_insights_quality_scores(self, client):
        """Test quality score calculation."""
        conv1 = Conversation.objects.create(title="Good Conv")
        conv2 = Conversation.objects.create(title="Poor Conv")
        
        # Conv1: 2 AI messages, both with positive feedback
        msg1 = Message.objects.create(conversation=conv1, role=Message.ROLE_AI, text="AI 1", sequence=1)
        msg2 = Message.objects.create(conversation=conv1, role=Message.ROLE_AI, text="AI 2", sequence=2)
        Feedback.objects.create(message=msg1, rating=True)
        Feedback.objects.create(message=msg2, rating=True)
        
        # Conv2: 2 AI messages, one with negative feedback
        msg3 = Message.objects.create(conversation=conv2, role=Message.ROLE_AI, text="AI 3", sequence=1)
        msg4 = Message.objects.create(conversation=conv2, role=Message.ROLE_AI, text="AI 4", sequence=2)
        Feedback.objects.create(message=msg3, rating=False)
        
        resp = client.get("/api/insights/")
        assert resp.status_code == 200
        data = resp.json()
        
        # Find conv1 in results
        conv1_data = next((c for c in data["quality_scores"]["conversations"] if c["id"] == conv1.id), None)
        assert conv1_data is not None
        assert conv1_data["quality_score"] is not None
        assert conv1_data["quality_score"] > 50  # Should be high with 100% positive feedback
        
        # Find conv2 in results
        conv2_data = next((c for c in data["quality_scores"]["conversations"] if c["id"] == conv2.id), None)
        assert conv2_data is not None
        # May be None if only 1 feedback out of 2 messages
    
    def test_insights_without_summary(self, client, monkeypatch):
        """Test insights without AI summary generation."""
        Conversation.objects.create(title="Test")
        
        call_count = 0
        def fake_generate_reply(history, prompt, timeout_s=10):
            nonlocal call_count
            call_count += 1
            return "Summary"
        
        monkeypatch.setattr(gemini, "generate_reply", fake_generate_reply)
        
        resp = client.get("/api/insights/?include_summary=false")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"] is None
        assert call_count == 0
    
    def test_insights_with_summary(self, client, monkeypatch):
        """Test insights with AI summary generation."""
        Conversation.objects.create(title="Test")
        
        def fake_generate_reply(history, prompt, timeout_s=10):
            return "This is a test summary"
        
        monkeypatch.setattr(gemini, "generate_reply", fake_generate_reply)
        
        resp = client.get("/api/insights/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"] == "This is a test summary"
    
    def test_insights_summary_error_handling(self, client, monkeypatch):
        """Test that insights continue even if summary generation fails."""
        Conversation.objects.create(title="Test")
        
        def fake_generate_reply(history, prompt, timeout_s=10):
            raise gemini.GeminiServiceError("API Error")
        
        monkeypatch.setattr(gemini, "generate_reply", fake_generate_reply)
        
        resp = client.get("/api/insights/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"] is None
        assert "usage" in data  # Other data should still be present
