from django.urls import path

from . import views


urlpatterns = [
    path("conversations/", views.ConversationListCreateView.as_view(), name="conversation-list-create"),
    path("conversations/<int:pk>/", views.ConversationDetailView.as_view(), name="conversation-detail"),
    path("conversations/<int:pk>/messages/", views.MessageListCreateView.as_view(), name="message-list-create"),
    path("messages/<int:message_id>/feedback/", views.MessageFeedbackView.as_view(), name="message-feedback"),
    path("insights/", views.InsightsView.as_view(), name="insights"),
]

