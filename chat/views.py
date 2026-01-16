from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.db.models import QuerySet
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Conversation, Message, Feedback
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    CreateMessageSerializer,
    CreateFeedbackSerializer,
    FeedbackSerializer,
    UpdateConversationSerializer,
)
from .services import gemini
from .utils import parse_int_query_param, calculate_quality_score, extract_feedback_themes


class ConversationListCreateView(APIView):
    def get(self, request: Request) -> Response:
        qs: QuerySet[Conversation] = Conversation.objects.all().order_by("-updated_at")
        limit = parse_int_query_param(request, "limit", 20, min_val=1, max_val=100)
        offset = parse_int_query_param(request, "offset", 0, min_val=0)
        items = qs[offset : offset + limit]
        data = ConversationSerializer(items, many=True).data
        return Response({"results": data, "count": qs.count(), "offset": offset, "limit": limit})

    def post(self, request: Request) -> Response:
        title = (request.data or {}).get("title")
        conv = Conversation.objects.create(title=title or None)
        return Response(ConversationSerializer(conv).data, status=status.HTTP_201_CREATED)


class ConversationDetailView(APIView):
    def get(self, request: Request, pk: int) -> Response:
        conv = get_object_or_404(Conversation, pk=pk)
        return Response(ConversationSerializer(conv).data)

    def patch(self, request: Request, pk: int) -> Response:
        """Update conversation title."""
        conv = get_object_or_404(Conversation, pk=pk)
        serializer = UpdateConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        title = serializer.validated_data.get("title")
        conv.title = title
        conv.save()
        
        return Response(ConversationSerializer(conv).data)


class MessageListCreateView(APIView):
    def get(self, request: Request, pk: int) -> Response:
        conv = get_object_or_404(Conversation, pk=pk)
        since = parse_int_query_param(request, "since", 0, min_val=0)
        limit = parse_int_query_param(request, "limit", 50, min_val=1, max_val=200)
        qs = conv.messages.select_related('feedback').all()
        if since:
            qs = qs.filter(sequence__gt=since)
        qs = qs.order_by("sequence")[:limit]
        results = list(qs)
        return Response({
            "results": MessageSerializer(results, many=True).data,
            "lastSeq": (results[-1].sequence if results else since),
        })

    def post(self, request: Request, pk: int) -> Response:
        conv = get_object_or_404(Conversation, pk=pk)
        serializer = CreateMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        text: str = serializer.validated_data["text"]

        # Persist user message
        user_msg = Message.objects.create(conversation=conv, role=Message.ROLE_USER, text=text)

        # Build short history context (last 10 messages)
        history = list(
            conv.messages.order_by("-sequence").values("role", "text")[:10]
        )[::-1]

        try:
            reply = gemini.generate_reply(history=history, prompt=text, timeout_s=10)
        except gemini.GeminiServiceError as e:
            # Remove user message to keep integrity if AI fails? We keep it and surface 502.
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        ai_msg = Message.objects.create(conversation=conv, role=Message.ROLE_AI, text=reply)
        
        # Auto-generate title from first user message if conversation has no title
        if not conv.title and conv.messages.filter(role=Message.ROLE_USER).count() == 1:
            # Use first 50 characters of the first user message as title
            title = text[:50].strip()
            if len(text) > 50:
                title += "..."
            conv.title = title
            conv.save(update_fields=["title"])
        
        return Response({
            "user_message": MessageSerializer(user_msg).data,
            "ai_message": MessageSerializer(ai_msg).data,
        }, status=status.HTTP_201_CREATED)


class MessageFeedbackView(APIView):
    def post(self, request: Request, message_id: int) -> Response:
        """Create or update feedback for a message."""
        message = get_object_or_404(Message, pk=message_id)
        # Only allow feedback on AI messages
        if message.role != Message.ROLE_AI:
            return Response(
                {"detail": "Feedback can only be provided for AI messages."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CreateFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get or create feedback, then update
        feedback, created = Feedback.objects.get_or_create(
            message=message,
            defaults={
                "rating": serializer.validated_data["rating"],
                "note": serializer.validated_data.get("note") or "",
            }
        )
        if not created:
            feedback.rating = serializer.validated_data["rating"]
            note = serializer.validated_data.get("note")
            if note is not None:
                feedback.note = note or ""
            feedback.save()

        return Response(
            FeedbackSerializer(feedback).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    def get(self, request: Request, message_id: int) -> Response:
        """Get feedback for a message."""
        message = get_object_or_404(Message, pk=message_id)
        try:
            feedback = message.feedback
            return Response(FeedbackSerializer(feedback).data)
        except Feedback.DoesNotExist:
            return Response({"detail": "No feedback found for this message."}, status=status.HTTP_404_NOT_FOUND)


class InsightsView(APIView):
    def get(self, request: Request) -> Response:
        """Get analytics and insights about chat usage and feedback."""
        # Check if summary should be included (default: True, set to False for polling)
        include_summary = request.query_params.get('include_summary', 'true').lower() != 'false'
        
        # Chat usage statistics
        total_conversations = Conversation.objects.count()
        total_messages = Message.objects.count()
        total_user_messages = Message.objects.filter(role=Message.ROLE_USER).count()
        total_ai_messages = Message.objects.filter(role=Message.ROLE_AI).count()
        
        # Feedback statistics
        total_feedback = Feedback.objects.count()
        positive_feedback = Feedback.objects.filter(rating=True).count()
        negative_feedback = Feedback.objects.filter(rating=False).count()
        
        # Calculate satisfaction rate (positive / total feedback)
        satisfaction_rate = (positive_feedback / total_feedback * 100) if total_feedback > 0 else 0
        
        # Calculate feedback rate (feedback / total AI messages)
        feedback_rate = (total_feedback / total_ai_messages * 100) if total_ai_messages > 0 else 0
        
        # Feedback themes from notes
        feedback_notes = Feedback.objects.exclude(note__isnull=True).exclude(note="").values_list('note', flat=True)
        top_themes = extract_feedback_themes(feedback_notes, top_n=10)
        
        # Calculate quality scores for all conversations
        conversations_with_scores = []
        for conv in Conversation.objects.prefetch_related('messages__feedback').all():
            quality_score = calculate_quality_score(conv)
            ai_messages = conv.messages.filter(role=Message.ROLE_AI)
            conversations_with_scores.append({
                "id": conv.id,
                "title": conv.title,
                "quality_score": quality_score,
                "total_messages": conv.messages.count(),
                "feedback_count": Feedback.objects.filter(message__in=ai_messages).count(),
            })
        
        # Quality score distribution
        quality_scores = [c["quality_score"] for c in conversations_with_scores if c["quality_score"] is not None]
        quality_distribution = {
            "excellent": len([s for s in quality_scores if s >= 80]),
            "good": len([s for s in quality_scores if 60 <= s < 80]),
            "fair": len([s for s in quality_scores if 40 <= s < 60]),
            "poor": len([s for s in quality_scores if s < 40]),
        }
        avg_quality_score = round(sum(quality_scores) / len(quality_scores), 2) if quality_scores else None
        
        # Generate AI summary of insights (only if include_summary is True)
        summary = None
        if include_summary:
            try:
                summary_prompt = f"""Provide a brief 1-2 sentence summary of these chat analytics insights. Be concise and highlight key trends.

Usage Statistics:
- Total Conversations: {total_conversations}
- Total Messages: {total_messages} (User: {total_user_messages}, AI: {total_ai_messages})

Feedback Statistics:
- Total Feedback: {total_feedback}
- Satisfaction Rate: {satisfaction_rate:.1f}%
- Feedback Rate: {feedback_rate:.1f}%
- Positive: {positive_feedback}, Negative: {negative_feedback}

Quality Scores:
- Average Quality Score: {avg_quality_score if avg_quality_score else 'N/A'}
- Distribution: Excellent ({quality_distribution['excellent']}), Good ({quality_distribution['good']}), Fair ({quality_distribution['fair']}), Poor ({quality_distribution['poor']})

Top Feedback Themes: {', '.join([t['word'] for t in top_themes[:5]]) if top_themes else 'None yet'}

Provide a brief, actionable summary in 1-2 sentences."""
                
                summary = gemini.generate_reply(history=[], prompt=summary_prompt, timeout_s=10)
            except gemini.GeminiServiceError:
                # If AI summary fails, continue without it
                summary = None
        
        return Response({
            "usage": {
                "total_conversations": total_conversations,
                "total_messages": total_messages,
                "total_user_messages": total_user_messages,
                "total_ai_messages": total_ai_messages,
            },
            "feedback": {
                "total_feedback": total_feedback,
                "positive_feedback": positive_feedback,
                "negative_feedback": negative_feedback,
                "satisfaction_rate": round(satisfaction_rate, 2),
                "feedback_rate": round(feedback_rate, 2),
            },
            "themes": top_themes,
            "quality_scores": {
                "average": avg_quality_score,
                "distribution": quality_distribution,
                "conversations": conversations_with_scores[:20],  # Top 20 for performance
            },
            "summary": summary,
        })
