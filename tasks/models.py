import uuid

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from projects.models import Project


class Task(models.Model):
    """Task item within a project board."""

    class Status(models.TextChoices):
        TODO = "TODO", "To Do"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        DONE = "DONE", "Done"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="tasks",
        help_text="Project to which this task belongs",
    )
    title = models.CharField(max_length=255, help_text="Short, descriptive task title")
    description = models.TextField(blank=True, default="", help_text="Detailed task description")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TODO,
        help_text="Current task column / progress status",
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        help_text="Priority level",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_tasks",
        help_text="User who created the task",
    )
    assignee = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
        help_text="Project member responsible for this task",
    )
    due_date = models.DateField(null=True, blank=True, help_text="Target completion date")
    position = models.FloatField(default=0.0, help_text="Card ordering index within column")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the task was moved to DONE",
    )

    class Meta:
        ordering = ["position", "-created_at"]
        indexes = [
            models.Index(fields=["project", "status"], name="idx_task_proj_status"),
            models.Index(fields=["project", "assignee"], name="idx_task_proj_assignee"),
            models.Index(fields=["project", "due_date"], name="idx_task_proj_due"),
            models.Index(fields=["project", "position"], name="idx_task_proj_pos"),
            models.Index(fields=["status", "priority"], name="idx_task_status_prio"),
            models.Index(fields=["created_at"], name="idx_task_created"),
        ]

    def __str__(self):
        return f"[{self.project.name}] {self.title}"

    def clean(self):
        super().clean()
        # Ensure assignee belongs to the project
        if self.assignee and hasattr(self, "project") and self.project:
            is_member = (
                self.project.owner_id == self.assignee_id
                or self.project.memberships.filter(user=self.assignee).exists()
            )
            if not is_member:
                raise ValidationError(
                    {"assignee": f"User '{self.assignee.username}' is not a member of project '{self.project.name}'."}
                )

    def save(self, *args, **kwargs):
        # Enforce completed_at logic based on status
        if self.status == self.Status.DONE:
            if not self.completed_at:
                self.completed_at = timezone.now()
        else:
            self.completed_at = None

        super().save(*args, **kwargs)


class TaskComment(models.Model):
    """Comment on a specific task posted by an authorized project member."""

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="task_comments",
    )
    body = models.TextField(help_text="Comment text content")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["task", "created_at"], name="idx_comment_task_created"),
        ]

    def __str__(self):
        return f"Comment by {self.author.username} on {self.task.title}"


class ActivityLog(models.Model):
    """Audit and activity stream log recording events within a project."""

    class Action(models.TextChoices):
        TASK_CREATED = "TASK_CREATED", "Task Created"
        TASK_UPDATED = "TASK_UPDATED", "Task Updated"
        TASK_DELETED = "TASK_DELETED", "Task Deleted"
        STATUS_CHANGED = "STATUS_CHANGED", "Status Changed"
        PRIORITY_CHANGED = "PRIORITY_CHANGED", "Priority Changed"
        ASSIGNMENT_CHANGED = "ASSIGNMENT_CHANGED", "Assignment Changed"
        COMMENT_ADDED = "COMMENT_ADDED", "Comment Added"
        MEMBER_ADDED = "MEMBER_ADDED", "Member Added"
        MEMBER_REMOVED = "MEMBER_REMOVED", "Member Removed"
        MEMBER_ROLE_CHANGED = "MEMBER_ROLE_CHANGED", "Member Role Changed"
        PROJECT_UPDATED = "PROJECT_UPDATED", "Project Updated"
        PROJECT_ARCHIVED = "PROJECT_ARCHIVED", "Project Archived"
        PROJECT_RESTORED = "PROJECT_RESTORED", "Project Restored"

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="activity_logs",
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities_performed",
        help_text="User who initiated the action, or null for system events",
    )
    action = models.CharField(max_length=50, choices=Action.choices)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Compact JSON payload containing non-sensitive change details",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project", "-created_at"], name="idx_act_proj_created"),
            models.Index(fields=["task", "-created_at"], name="idx_act_task_created"),
        ]

    def __str__(self):
        actor_name = self.actor.username if self.actor else "System"
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {actor_name}: {self.action} on {self.project.name}"
