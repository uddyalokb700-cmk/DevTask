from django.db.models import Case, Count, IntegerField, Q, When
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.models import Project, ProjectMembership
from projects.permissions import (
    is_project_member,
    is_project_owner,
)
from projects.serializers import (
    AddMemberSerializer,
    ArchiveProjectActionSerializer,
    ProjectCreateSerializer,
    ProjectDetailSerializer,
    ProjectMembershipSerializer,
    ProjectSerializer,
    ProjectUpdateSerializer,
    TransferOwnershipSerializer,
    UpdateMemberRoleSerializer,
)
from projects.services import (
    add_project_member,
    archive_project,
    create_project,
    delete_project,
    remove_project_member,
    transfer_project_ownership,
    unarchive_project,
    update_project,
    update_project_membership,
)
from tasks.models import Task
from tasks.serializers import ActivityLogSerializer


class ProjectListCreateAPIView(APIView):
    """List projects accessible to the authenticated user or create a new project."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="archived", description="Include archived projects (true/false)", required=False, type=bool
            ),
            OpenApiParameter(
                name="search", description="Search projects by name or description", required=False, type=str
            ),
        ],
        responses={200: ProjectSerializer(many=True)},
    )
    def get(self, request):
        qs = Project.objects.for_user(request.user).select_related("owner", "owner__profile")

        # Filtering archived vs active
        include_archived = request.query_params.get("archived", "false").lower() in ("true", "1")
        if not include_archived:
            qs = qs.active()

        # Search
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))

        # Database-side aggregation to avoid N+1 queries
        qs = qs.annotate(
            members_count=Count("memberships", distinct=True),
            tasks_count=Count("tasks", distinct=True),
            completed_tasks_count=Count(
                "tasks",
                filter=Q(tasks__status=Task.Status.DONE),
                distinct=True,
            ),
        )

        serializer = ProjectSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        request=ProjectCreateSerializer,
        responses={201: ProjectSerializer, 400: OpenApiResponse(description="Validation error")},
    )
    def post(self, request):
        serializer = ProjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = create_project(
            name=serializer.validated_data["name"],
            description=serializer.validated_data.get("description", ""),
            owner=request.user,
        )
        return Response(
            ProjectSerializer(project, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class ProjectDetailAPIView(APIView):
    """Retrieve, update, or permanently delete a specific project workspace."""

    permission_classes = [permissions.IsAuthenticated]

    def get_project(self, project_id, user):
        project = get_object_or_404(
            Project.objects.select_related("owner", "owner__profile").annotate(
                members_count=Count("memberships", distinct=True),
                tasks_count=Count("tasks", distinct=True),
                completed_tasks_count=Count(
                    "tasks",
                    filter=Q(tasks__status=Task.Status.DONE),
                    distinct=True,
                ),
            ),
            pk=project_id,
        )
        if not is_project_member(project, user):
            return None
        return project

    @extend_schema(responses={200: ProjectDetailSerializer, 403: OpenApiResponse(description="Access forbidden")})
    def get(self, request, project_id):
        project = self.get_project(project_id, request.user)
        if not project:
            return Response({"detail": "You do not have access to this project."}, status=status.HTTP_403_FORBIDDEN)
        return Response(ProjectDetailSerializer(project, context={"request": request}).data)

    @extend_schema(
        request=ProjectUpdateSerializer,
        responses={200: ProjectDetailSerializer, 403: OpenApiResponse(description="Access forbidden")},
    )
    def patch(self, request, project_id):
        project = self.get_project(project_id, request.user)
        if not project:
            return Response({"detail": "You do not have access to this project."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ProjectUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_project = update_project(project, serializer.validated_data, request.user)
        return Response(ProjectDetailSerializer(updated_project, context={"request": request}).data)

    @extend_schema(
        responses={204: OpenApiResponse(description="Deleted"), 403: OpenApiResponse(description="Access forbidden")}
    )
    def delete(self, request, project_id):
        project = self.get_project(project_id, request.user)
        if not project:
            return Response({"detail": "You do not have access to this project."}, status=status.HTTP_403_FORBIDDEN)

        delete_project(project, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectArchiveAPIView(APIView):
    """Archive or unarchive a project."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=ArchiveProjectActionSerializer, responses={200: ProjectSerializer})
    def post(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        if not is_project_member(project, request.user):
            return Response({"detail": "You do not have access to this project."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ArchiveProjectActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data.get("action", "archive")
        if action == "unarchive":
            project = unarchive_project(project, request.user)
        else:
            project = archive_project(project, request.user)

        return Response(ProjectSerializer(project, context={"request": request}).data)


class ProjectTransferOwnershipAPIView(APIView):
    """Transfer ownership of a project to another project member."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=TransferOwnershipSerializer, responses={200: ProjectSerializer})
    def post(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        if not is_project_owner(project, request.user):
            return Response(
                {"detail": "Only the current project owner can transfer ownership."}, status=status.HTTP_403_FORBIDDEN
            )

        serializer = TransferOwnershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_owner = serializer.validated_data["new_owner_id"]

        updated_project = transfer_project_ownership(project, new_owner, request.user)
        return Response(ProjectSerializer(updated_project, context={"request": request}).data)


class ProjectMemberListCreateAPIView(APIView):
    """List project members or add a new team member."""

    permission_classes = [permissions.IsAuthenticated]

    def get_project(self, project_id, user):
        project = get_object_or_404(Project, pk=project_id)
        if not is_project_member(project, user):
            return None
        return project

    @extend_schema(responses={200: ProjectMembershipSerializer(many=True)})
    def get(self, request, project_id):
        project = self.get_project(project_id, request.user)
        if not project:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        memberships = project.memberships.select_related("user", "user__profile").all()
        return Response(ProjectMembershipSerializer(memberships, many=True).data)

    @extend_schema(request=AddMemberSerializer, responses={201: ProjectMembershipSerializer})
    def post(self, request, project_id):
        project = self.get_project(project_id, request.user)
        if not project:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = AddMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_user = serializer.validated_data["username_or_email"]
        role = serializer.validated_data["role"]

        membership = add_project_member(project, target_user, role, request.user)
        return Response(ProjectMembershipSerializer(membership).data, status=status.HTTP_201_CREATED)


class ProjectMemberDetailAPIView(APIView):
    """Update role or remove a team member from the project."""

    permission_classes = [permissions.IsAuthenticated]

    def get_project(self, project_id, user):
        project = get_object_or_404(Project, pk=project_id)
        if not is_project_member(project, user):
            return None
        return project

    @extend_schema(request=UpdateMemberRoleSerializer, responses={200: ProjectMembershipSerializer})
    def patch(self, request, project_id, membership_id):
        project = self.get_project(project_id, request.user)
        if not project:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        membership = get_object_or_404(ProjectMembership, pk=membership_id, project=project)

        serializer = UpdateMemberRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated_membership = update_project_membership(
            project, membership, serializer.validated_data["role"], request.user
        )
        return Response(ProjectMembershipSerializer(updated_membership).data)

    @extend_schema(responses={204: OpenApiResponse(description="Member removed")})
    def delete(self, request, project_id, membership_id):
        project = self.get_project(project_id, request.user)
        if not project:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        membership = get_object_or_404(ProjectMembership, pk=membership_id, project=project)

        remove_project_member(project, membership, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DashboardStatsAPIView(APIView):
    """Aggregated developer dashboard KPI metrics computed across all accessible projects."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: OpenApiResponse(description="Global dashboard metrics")})
    def get(self, request):
        user = request.user
        today = timezone.now().date()
        user_projects = Project.objects.for_user(user).active()

        # Project count
        active_projects_count = user_projects.count()

        # Aggregated task metrics across user projects
        task_qs = Task.objects.filter(project__in=user_projects)
        task_metrics = task_qs.aggregate(
            total_tasks=Count("id"),
            todo_tasks=Count(Case(When(status=Task.Status.TODO, then=1), output_field=IntegerField())),
            in_progress_tasks=Count(Case(When(status=Task.Status.IN_PROGRESS, then=1), output_field=IntegerField())),
            done_tasks=Count(Case(When(status=Task.Status.DONE, then=1), output_field=IntegerField())),
            my_tasks=Count(Case(When(assignee=user, then=1), output_field=IntegerField())),
            my_open_tasks=Count(
                Case(
                    When(assignee=user, status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS], then=1),
                    output_field=IntegerField(),
                )
            ),
            overdue_tasks=Count(
                Case(
                    When(due_date__lt=today, status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS], then=1),
                    output_field=IntegerField(),
                )
            ),
            low_tasks=Count(Case(When(priority=Task.Priority.LOW, then=1), output_field=IntegerField())),
            medium_tasks=Count(Case(When(priority=Task.Priority.MEDIUM, then=1), output_field=IntegerField())),
            high_tasks=Count(Case(When(priority=Task.Priority.HIGH, then=1), output_field=IntegerField())),
            urgent_tasks=Count(Case(When(priority=Task.Priority.URGENT, then=1), output_field=IntegerField())),
        )

        # Top 5 upcoming deadlines
        upcoming = (
            task_qs.filter(due_date__gte=today, status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS])
            .select_related("project", "assignee", "assignee__profile")
            .order_by("due_date")[:5]
        )
        upcoming_data = [
            {
                "id": str(t.id),
                "title": t.title,
                "project_id": str(t.project_id),
                "project_name": t.project.name,
                "due_date": str(t.due_date),
                "priority": t.priority,
                "assignee_name": t.assignee.profile.get_display_name() if t.assignee else "Unassigned",
            }
            for t in upcoming
        ]

        # Top 5 recently updated projects
        recent_projs = (
            user_projects.select_related("owner", "owner__profile")
            .annotate(
                tasks_count=Count("tasks", distinct=True),
                completed_tasks_count=Count("tasks", filter=Q(tasks__status=Task.Status.DONE), distinct=True),
            )
            .order_by("-updated_at")[:5]
        )
        recent_projects_data = [
            {
                "id": str(p.id),
                "name": p.name,
                "description": p.description,
                "updated_at": p.updated_at.isoformat(),
                "tasks_count": p.tasks_count,
                "completed_tasks_count": p.completed_tasks_count,
            }
            for p in recent_projs
        ]

        total = task_metrics["total_tasks"] or 0
        done = task_metrics["done_tasks"] or 0
        open_tasks = (task_metrics["todo_tasks"] or 0) + (task_metrics["in_progress_tasks"] or 0)

        return Response(
            {
                "metrics": {
                    "active_projects": active_projects_count,
                    "open_tasks": open_tasks,
                    "total_tasks": total,
                    "my_open_tasks": task_metrics["my_open_tasks"] or 0,
                    "overdue_tasks": task_metrics["overdue_tasks"] or 0,
                    "completion_percentage": round((done / total * 100), 1) if total > 0 else 0.0,
                },
                "status_distribution": {
                    "TODO": task_metrics["todo_tasks"] or 0,
                    "IN_PROGRESS": task_metrics["in_progress_tasks"] or 0,
                    "DONE": done,
                },
                "priority_distribution": {
                    "LOW": task_metrics["low_tasks"] or 0,
                    "MEDIUM": task_metrics["medium_tasks"] or 0,
                    "HIGH": task_metrics["high_tasks"] or 0,
                    "URGENT": task_metrics["urgent_tasks"] or 0,
                },
                "upcoming_deadlines": upcoming_data,
                "recent_projects": recent_projects_data,
            }
        )


class ProjectStatsAPIView(APIView):
    """Retrieve aggregated project statistics and metrics computed in-database."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: OpenApiResponse(description="Project analytics summary")})
    def get(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        if not is_project_member(project, request.user):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.now().date()
        # Single database-side aggregation query
        stats = project.tasks.aggregate(
            total_tasks=Count("id"),
            todo_tasks=Count(Case(When(status=Task.Status.TODO, then=1), output_field=IntegerField())),
            in_progress_tasks=Count(Case(When(status=Task.Status.IN_PROGRESS, then=1), output_field=IntegerField())),
            done_tasks=Count(Case(When(status=Task.Status.DONE, then=1), output_field=IntegerField())),
            urgent_tasks=Count(Case(When(priority=Task.Priority.URGENT, then=1), output_field=IntegerField())),
            high_tasks=Count(Case(When(priority=Task.Priority.HIGH, then=1), output_field=IntegerField())),
            overdue_tasks=Count(
                Case(
                    When(due_date__lt=today, status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS], then=1),
                    output_field=IntegerField(),
                )
            ),
        )

        total = stats["total_tasks"] or 0
        done = stats["done_tasks"] or 0
        completion_rate = round((done / total * 100), 1) if total > 0 else 0.0

        # Tasks grouped by assignee
        assignee_breakdown = (
            project.tasks.values(
                "assignee__id",
                "assignee__username",
                "assignee__profile__display_name",
                "assignee__profile__avatar_color",
            )
            .annotate(task_count=Count("id"))
            .order_by("-task_count")
        )

        return Response(
            {
                "project_id": str(project.id),
                "project_name": project.name,
                "metrics": {
                    "total": total,
                    "todo": stats["todo_tasks"] or 0,
                    "in_progress": stats["in_progress_tasks"] or 0,
                    "done": done,
                    "urgent": stats["urgent_tasks"] or 0,
                    "high": stats["high_tasks"] or 0,
                    "overdue": stats["overdue_tasks"] or 0,
                    "completion_rate": completion_rate,
                },
                "assignee_breakdown": list(assignee_breakdown),
            }
        )


class ProjectActivityAPIView(APIView):
    """Retrieve paginated activity history for the specified project."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: ActivityLogSerializer(many=True)})
    def get(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        if not is_project_member(project, request.user):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        qs = project.activity_logs.select_related("actor", "actor__profile", "task").all()

        paginator = PageNumberPagination()
        paginator.page_size = 25
        page = paginator.paginate_queryset(qs, request)
        serializer = ActivityLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
