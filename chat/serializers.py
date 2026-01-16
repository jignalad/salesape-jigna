from rest_framework import serializers

from .models import Conversation, Message, Feedback


class ConversationSerializer(serializers.ModelSerializer):
    quality_score = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = ["id", "title", "created_at", "updated_at", "quality_score"]
    
    def get_quality_score(self, obj):
        """Calculate quality score based on feedback ratios."""
        from .utils import calculate_quality_score
        return calculate_quality_score(obj)


class UpdateConversationSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, allow_blank=True, required=False, allow_null=True)

    def validate_title(self, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            return value if value else None
        return None


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ["id", "rating", "note", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class MessageSerializer(serializers.ModelSerializer):
    feedback = FeedbackSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Message
        fields = ["id", "conversation", "role", "text", "created_at", "sequence", "feedback"]
        read_only_fields = ["id", "created_at", "sequence", "conversation", "role"]


class CreateMessageSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=1000, allow_blank=False, trim_whitespace=True)


class CreateFeedbackSerializer(serializers.Serializer):
    rating = serializers.BooleanField(help_text="True for thumbs up, False for thumbs down")
    note = serializers.CharField(max_length=1000, allow_blank=True, required=False, allow_null=True)

