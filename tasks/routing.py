"""WebSocket URL routing for tasks & projects real-time events."""

from django.urls import path

from tasks.consumers import ProjectTaskConsumer

websocket_urlpatterns = [
    path("ws/projects/<uuid:project_id>/", ProjectTaskConsumer.as_asgi()),
]
