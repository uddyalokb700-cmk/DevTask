from django.contrib.auth.models import User
from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.models import Project
from projects.permissions import is_project_member
from tasks.filters import TaskFilter
from tasks.models import Task
from tasks.serializers import (
    TaskCommentCreateSerializer,
    TaskCommentSerializer,
    TaskCreateUpdateSerializer,
    TaskReorderSerializer,
    TaskSerializer,
)
from tasks.services import (
    create_task,
    create_task_comment,
    delete_task,
    reorder_task_kanban,
    update_task,
)


class TaskListPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class TaskListCreateAPIView(APIView):
    """List paginated tasks filtered by project, status, priority, or search; or create a new task."""

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self, user):
        user_projects = Project.objects.for_user(user)
        return (
            Task.objects.filter(project__in=user_projects)
            .select_related(
                "project",
                "created_by",
                "created_by__profile",
                "assignee",
                "assignee__profile",
            )
            .annotate(comments_count=Count("comments", distinct=True))
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(name="project_id", description="Filter by project UUID", required=False, type=str),
            OpenApiParameter(
                name="status", description="Filter by status (TODO, IN_PROGRESS, DONE)", required=False, type=str
            ),
            OpenApiParameter(
                name="priority", description="Filter by priority (LOW, MEDIUM, HIGH, URGENT)", required=False, type=str
            ),
            OpenApiParameter(
                name="assignee_id", description="Filter by assignee user ID or 'unassigned'", required=False, type=str
            ),
            OpenApiParameter(name="search", description="Search by title or description", required=False, type=str),
            OpenApiParameter(
                name="is_overdue", description="Filter by overdue status (true/false)", required=False, type=bool
            ),
            OpenApiParameter(
                name="ordering",
                description="Order by position, due_date, priority, created_at",
                required=False,
                type=str,
            ),
        ],
        responses={200: TaskSerializer(many=True)},
    )
    def get(self, request):
        qs = self.get_queryset(request.user)

        # Apply filtering
        filterset = TaskFilter(request.query_params, queryset=qs)
        if filterset.is_valid():
            qs = filterset.qs

        # Apply validated ordering
        ordering = request.query_params.get("ordering", "position")
        allowed_ordering = {
            "position": "position",
            "-position": "-position",
            "due_date": "due_date",
            "-due_date": "-due_date",
            "priority": "priority",
            "-priority": "-priority",
            "created_at": "created_at",
            "-created_at": "-created_at",
            "updated_at": "updated_at",
            "-updated_at": "-updated_at",
        }
        order_field = allowed_ordering.get(ordering, "position")
        qs = qs.order_by(order_field, "-created_at")

        paginator = TaskListPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = TaskSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=TaskCreateUpdateSerializer,
        responses={201: TaskSerializer, 400: OpenApiResponse(description="Validation error")},
    )
    def post(self, request):
        serializer = TaskCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        project_id = data.get("project_id") or request.data.get("project_id")
        if not project_id:
            return Response({"project_id": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        project = get_object_or_404(Project, pk=project_id)
        if not is_project_member(project, request.user):
            return Response({"detail": "Access forbidden for this project."}, status=status.HTTP_403_FORBIDDEN)

        assignee = None
        assignee_id = data.get("assignee_id")
        if assignee_id:
            assignee = get_object_or_404(User, pk=assignee_id)

        task = create_task(
            project=project,
            title=data["title"],
            description=data.get("description", ""),
            status=data.get("status", Task.Status.TODO),
            priority=data.get("priority", Task.Priority.MEDIUM),
            assignee=assignee,
            due_date=data.get("due_date"),
            created_by=request.user,
            position=data.get("position"),
        )

        return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)


class TaskDetailAPIView(APIView):
    """Retrieve, update, or delete a task."""

    permission_classes = [permissions.IsAuthenticated]

    def get_task(self, task_id, user):
        task = get_object_or_404(
            Task.objects.select_related(
                "project",
                "created_by",
                "created_by__profile",
                "assignee",
                "assignee__profile",
            ).annotate(comments_count=Count("comments", distinct=True)),
            pk=task_id,
        )
        if not is_project_member(task.project, user):
            return None
        return task

    @extend_schema(responses={200: TaskSerializer, 403: OpenApiResponse(description="Forbidden")})
    def get(self, request, task_id):
        task = self.get_task(task_id, request.user)
        if not task:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        return Response(TaskSerializer(task).data)

    @extend_schema(request=TaskCreateUpdateSerializer, responses={200: TaskSerializer})
    def patch(self, request, task_id):
        task = self.get_task(task_id, request.user)
        if not task:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        if "assignee_id" in data:
            assignee_id = data.get("assignee_id")
            if assignee_id in (None, "", "null"):
                data["assignee"] = None
            else:
                data["assignee"] = get_object_or_404(User, pk=int(assignee_id))

        updated_task = update_task(task, data, request.user)
        return Response(TaskSerializer(updated_task).data)

    @extend_schema(responses={204: OpenApiResponse(description="Deleted")})
    def delete(self, request, task_id):
        task = self.get_task(task_id, request.user)
        if not task:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        delete_task(task, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TaskReorderAPIView(APIView):
    """Reorder a task's status and position on the Kanban board."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=TaskReorderSerializer, responses={200: TaskSerializer})
    def post(self, request, task_id):
        task = get_object_or_404(Task.objects.select_related("project"), pk=task_id)
        if not is_project_member(task.project, request.user):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = TaskReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated_task = reorder_task_kanban(
            task=task,
            new_status=serializer.validated_data["status"],
            new_position=serializer.validated_data["position"],
            actor=request.user,
        )
        return Response(TaskSerializer(updated_task).data)


class TaskCommentListCreateAPIView(APIView):
    """List comments on a task or post a new comment."""

    permission_classes = [permissions.IsAuthenticated]

    def get_task(self, task_id, user):
        task = get_object_or_404(Task.objects.select_related("project"), pk=task_id)
        if not is_project_member(task.project, user):
            return None
        return task

    @extend_schema(responses={200: TaskCommentSerializer(many=True)})
    def get(self, request, task_id):
        task = self.get_task(task_id, request.user)
        if not task:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        comments = task.comments.select_related("author", "author__profile").all()
        return Response(TaskCommentSerializer(comments, many=True).data)

    @extend_schema(request=TaskCommentCreateSerializer, responses={201: TaskCommentSerializer})
    def post(self, request, task_id):
        task = self.get_task(task_id, request.user)
        if not task:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = TaskCommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        comment = create_task_comment(
            task=task,
            author=request.user,
            body=serializer.validated_data["body"],
        )
        return Response(TaskCommentSerializer(comment).data, status=status.HTTP_201_CREATED)
