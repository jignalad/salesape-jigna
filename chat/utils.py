"""Utility functions for chat app."""
from __future__ import annotations

from collections import Counter
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from .models import Conversation


# Stop words for feedback theme extraction
STOP_WORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
    'is', 'was', 'are', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
    'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
    'not', 'no', 'yes', 'very', 'too', 'so', 'just', 'only', 'also', 'more', 'most',
    'what', 'which', 'who', 'when', 'where', 'why', 'how', 'can', 'could', 'should', 'would',
    'from', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'up', 'down',
    'out', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when',
    'where', 'why', 'how', 'all', 'each', 'both', 'few', 'more', 'most', 'other', 'some', 'such',
    'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can',
    'will', 'just', 'don', 'should', 'now', 'response', 'answer', 'helpful', 'not', 'wasn', 'didn'
}


def parse_int_query_param(request, param_name: str, default: int, min_val: int | None = None, max_val: int | None = None) -> int:
    """Parse and validate an integer query parameter."""
    try:
        value = int(request.query_params.get(param_name, default))
        if min_val is not None:
            value = max(value, min_val)
        if max_val is not None:
            value = min(value, max_val)
        return value
    except (ValueError, TypeError):
        return default


def calculate_quality_score(conversation: 'Conversation') -> float | None:
    """
    Calculate quality score for a conversation based on feedback ratios.
    
    Quality score formula: (positive feedback ratio * 0.7) + (feedback rate * 0.3)
    This balances satisfaction with engagement.
    """
    from .models import Message, Feedback
    
    ai_messages = conversation.messages.filter(role=Message.ROLE_AI)
    total_ai = ai_messages.count()
    if total_ai == 0:
        return None
    
    feedback_count = Feedback.objects.filter(message__in=ai_messages).count()
    if feedback_count == 0:
        return None
    
    positive_count = Feedback.objects.filter(message__in=ai_messages, rating=True).count()
    positive_ratio = positive_count / feedback_count
    feedback_rate = feedback_count / total_ai
    return round((positive_ratio * 0.7 + feedback_rate * 0.3) * 100, 2)


def extract_feedback_themes(feedback_notes: 'QuerySet', top_n: int = 10) -> list[dict[str, int]]:
    """Extract top themes from feedback notes."""
    word_counter = Counter()
    for note in feedback_notes:
        if note:
            words = re.findall(r'\b[a-z]+\b', note.lower())
            words = [w for w in words if w not in STOP_WORDS and len(w) > 3]
            word_counter.update(words)
    
    return [{"word": word, "count": count} for word, count in word_counter.most_common(top_n)]
