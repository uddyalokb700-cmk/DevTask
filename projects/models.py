import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class ProjectQuerySet(models.QuerySet):
    """Custom queryset with helper scopes for active and archived projects."""

    def active(self):
        return self.filter(archived_at__isnull=True)

    def archived(self):
        return self.filter(archived_at__isnull=False)

    def for_user(self, user):
        """Return projects where user is owner or an active member."""
        if not user or not user.is_authenticated:
            return self.none()
        return self.filter(models.Q(owner=user) | models.Q(memberships__user=user)).distinct()


class Project(models.Model):
    """A project workspace containing tasks, team members, and activity history."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="Project display name")
    description = models.TextField(blank=True, default="", help_text="Detailed project description")
    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="owned_projects",
        help_text="Project creator and primary administrator",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when project was archived")

    objects = ProjectQuerySet.as_manager()

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["owner", "archived_at"], name="idx_proj_owner_archived"),
            models.Index(fields=["archived_at"], name="idx_proj_archived"),
            models.Index(fields=["created_at"], name="idx_proj_created"),
        ]

    def __str__(self):
        return self.name

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None

    def archive(self):
        """Archive the project."""
        if not self.archived_at:
            self.archived_at = timezone.now()
            self.save(update_fields=["archived_at", "updated_at"])

    def unarchive(self):
        """Restore an archived project."""
        if self.archived_at:
            self.archived_at = None
            self.save(update_fields=["archived_at", "updated_at"])


class ProjectMembership(models.Model):
    """Associates a user with a project and assigns their role."""

    class Role(models.TextChoices):
        OWNER = "OWNER", "Owner"
        MANAGER = "MANAGER", "Manager"
        MEMBER = "MEMBER", "Member"

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="project_memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.MEMBER,
        help_text="Role-based permission level in this project",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "user"],
                name="unique_project_membership",
            )
        ]
        indexes = [
            models.Index(fields=["project", "user"], name="idx_pm_proj_user"),
            models.Index(fields=["user", "role"], name="idx_pm_user_role"),
        ]

    def __str__(self):
        return f"{self.user.username} ({self.role}) in {self.project.name}"
