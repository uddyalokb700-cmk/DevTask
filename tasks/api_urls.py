from django.urls import path

from tasks.api_views import (
    TaskCommentListCreateAPIView,
    TaskDetailAPIView,
    TaskListCreateAPIView,
    TaskReorderAPIView,
)

urlpatterns = [
    path("", TaskListCreateAPIView.as_view(), name="api-task-list"),
    path("<uuid:task_id>/", TaskDetailAPIView.as_view(), name="api-task-detail"),
    path("<uuid:task_id>/reorder/", TaskReorderAPIView.as_view(), name="api-task-reorder"),
    path("<uuid:task_id>/comments/", TaskCommentListCreateAPIView.as_view(), name="api-task-comments"),
]
