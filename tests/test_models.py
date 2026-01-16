"""Comprehensive tests for models."""
import time
import pytest
from django.utils import timezone
from django.db import IntegrityError

from chat.models import Conversation, Message, Feedback


def test_conversation_str_with_title(db):
    """Test Conversation __str__ with title."""
    conv = Conversation.objects.create(title="Test Conversation")
    assert str(conv) == "Test Conversation"


def test_conversation_str_without_title(db):
    """Test Conversation __str__ without title."""
    conv = Conversation.objects.create(title=None)
    assert str(conv) == f"Conversation {conv.pk}"


def test_conversation_ordering(db):
    """Test Conversation ordering by updated_at."""
    conv1 = Conversation.objects.create(title="First")
    time.sleep(0.01)  # Small delay to ensure different timestamps
    conv2 = Conversation.objects.create(title="Second")
    
    conversations = list(Conversation.objects.all())
    assert conversations[0].id == conv2.id  # Newest first
    assert conversations[1].id == conv1.id


def test_message_sequence_increments_and_updates_conversation(db):
    """Test that message sequence increments and updates conversation."""
    conv = Conversation.objects.create(title=None)
    t0 = conv.updated_at
    msg1 = Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="hi")
    msg2 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="hello")

    assert msg1.sequence == 1
    assert msg2.sequence == 2
    conv.refresh_from_db()
    assert conv.updated_at >= t0


def test_message_sequence_per_conversation(db):
    """Test that sequence is per conversation."""
    conv1 = Conversation.objects.create(title="Conv 1")
    conv2 = Conversation.objects.create(title="Conv 2")
    
    msg1 = Message.objects.create(conversation=conv1, role=Message.ROLE_USER, text="hi")
    msg2 = Message.objects.create(conversation=conv2, role=Message.ROLE_USER, text="hello")
    msg3 = Message.objects.create(conversation=conv1, role=Message.ROLE_AI, text="response")
    
    assert msg1.sequence == 1
    assert msg2.sequence == 1  # Different conversation, starts at 1
    assert msg3.sequence == 2  # Same conversation as msg1


def test_message_sequence_with_explicit_value(db):
    """Test that explicit sequence value is preserved."""
    conv = Conversation.objects.create(title="Test")
    msg = Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="hi", sequence=5)
    assert msg.sequence == 5


def test_message_str(db):
    """Test Message __str__."""
    conv = Conversation.objects.create(title="Test")
    msg = Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="hi", sequence=1)
    assert str(msg) == f"{conv.id}#1:user"


def test_message_unique_together(db):
    """Test that sequence is unique per conversation."""
    conv = Conversation.objects.create(title="Test")
    Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="hi", sequence=1)
    
    # Should raise IntegrityError when trying to create duplicate sequence
    with pytest.raises(IntegrityError):
        Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="hello", sequence=1)


def test_message_ordering(db):
    """Test Message ordering by sequence."""
    conv = Conversation.objects.create(title="Test")
    msg3 = Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="third", sequence=3)
    msg1 = Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="first", sequence=1)
    msg2 = Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="second", sequence=2)
    
    messages = list(conv.messages.all())
    assert messages[0].sequence == 1
    assert messages[1].sequence == 2
    assert messages[2].sequence == 3


def test_message_role_choices(db):
    """Test Message role choices."""
    conv = Conversation.objects.create(title="Test")
    user_msg = Message.objects.create(conversation=conv, role=Message.ROLE_USER, text="hi", sequence=1)
    ai_msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="hello", sequence=2)
    
    assert user_msg.role == "user"
    assert ai_msg.role == "ai"


def test_feedback_str_positive(db):
    """Test Feedback __str__ for positive rating."""
    conv = Conversation.objects.create(title="Test")
    msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI", sequence=1)
    feedback = Feedback.objects.create(message=msg, rating=True)
    
    assert "👍" in str(feedback)
    assert str(msg) in str(feedback)


def test_feedback_str_negative(db):
    """Test Feedback __str__ for negative rating."""
    conv = Conversation.objects.create(title="Test")
    msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI", sequence=1)
    feedback = Feedback.objects.create(message=msg, rating=False)
    
    assert "👎" in str(feedback)
    assert str(msg) in str(feedback)


def test_feedback_one_to_one_relationship(db):
    """Test that Feedback has one-to-one relationship with Message."""
    conv = Conversation.objects.create(title="Test")
    msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI", sequence=1)
    
    feedback1 = Feedback.objects.create(message=msg, rating=True)
    assert msg.feedback == feedback1
    
    # Creating another feedback for same message should fail
    with pytest.raises(IntegrityError):
        Feedback.objects.create(message=msg, rating=False)


def test_feedback_with_note(db):
    """Test Feedback with note."""
    conv = Conversation.objects.create(title="Test")
    msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI", sequence=1)
    feedback = Feedback.objects.create(message=msg, rating=True, note="Great response!")
    
    assert feedback.note == "Great response!"


def test_feedback_without_note(db):
    """Test Feedback without note."""
    conv = Conversation.objects.create(title="Test")
    msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI", sequence=1)
    feedback = Feedback.objects.create(message=msg, rating=True, note=None)
    
    assert feedback.note is None


def test_feedback_ordering(db):
    """Test Feedback ordering by created_at descending."""
    conv = Conversation.objects.create(title="Test")
    msg1 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 1", sequence=1)
    msg2 = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI 2", sequence=2)
    
    feedback1 = Feedback.objects.create(message=msg1, rating=True)
    time.sleep(0.01)
    feedback2 = Feedback.objects.create(message=msg2, rating=False)
    
    feedbacks = list(Feedback.objects.all())
    assert feedbacks[0].id == feedback2.id  # Newest first
    assert feedbacks[1].id == feedback1.id


def test_feedback_constants(db):
    """Test Feedback rating constants."""
    assert Feedback.RATING_POSITIVE is True
    assert Feedback.RATING_NEGATIVE is False


def test_message_cascade_delete(db):
    """Test that deleting a message deletes its feedback."""
    conv = Conversation.objects.create(title="Test")
    msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI", sequence=1)
    feedback = Feedback.objects.create(message=msg, rating=True)
    
    msg_id = msg.id
    feedback_id = feedback.id
    
    msg.delete()
    
    assert not Message.objects.filter(id=msg_id).exists()
    assert not Feedback.objects.filter(id=feedback_id).exists()


def test_conversation_cascade_delete(db):
    """Test that deleting a conversation deletes its messages and feedback."""
    conv = Conversation.objects.create(title="Test")
    msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text="AI", sequence=1)
    feedback = Feedback.objects.create(message=msg, rating=True)
    
    conv_id = conv.id
    msg_id = msg.id
    feedback_id = feedback.id
    
    conv.delete()
    
    assert not Conversation.objects.filter(id=conv_id).exists()
    assert not Message.objects.filter(id=msg_id).exists()
    assert not Feedback.objects.filter(id=feedback_id).exists()
