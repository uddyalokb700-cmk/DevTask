from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from projects.models import Project
from projects.permissions import is_project_member
from tasks.broadcaster import broadcast_project_event
from tasks.models import ActivityLog, Task, TaskComment


def validate_assignee_in_project(project: Project, assignee: User | None):
    """Ensure assignee belongs to the project."""
    if assignee:
        is_member = project.owner_id == assignee.id or project.memberships.filter(user=assignee).exists()
        if not is_member:
            raise ValidationError(
                {"assignee": f"User '{assignee.username}' is not a member of project '{project.name}'."}
            )


@transaction.atomic
def create_task(
    project: Project,
    title: str,
    description: str = "",
    status: str = Task.Status.TODO,
    priority: str = Task.Priority.MEDIUM,
    assignee: User | None = None,
    due_date=None,
    created_by: User = None,
    position: float | None = None,
) -> Task:
    """Create a new task with validation, activity logging, and real-time broadcasting."""
    if not is_project_member(project, created_by):
        raise PermissionDenied("You must be a member of this project to create tasks.")

    title = title.strip()
    if not title:
        raise ValidationError({"title": "Task title cannot be empty."})

    validate_assignee_in_project(project, assignee)

    if position is None:
        max_pos = project.tasks.filter(status=status).aggregate(Max("position"))["position__max"]
        position = (max_pos or 0.0) + 1.0

    task = Task.objects.create(
        project=project,
        title=title,
        description=description.strip() if description else "",
        status=status,
        priority=priority,
        assignee=assignee,
        due_date=due_date,
        created_by=created_by,
        position=position,
    )

    ActivityLog.objects.create(
        project=project,
        task=task,
        actor=created_by,
        action=ActivityLog.Action.TASK_CREATED,
        metadata={
            "task_title": task.title,
            "status": task.status,
            "priority": task.priority,
            "assignee": assignee.username if assignee else None,
        },
    )

    broadcast_project_event(
        str(project.id),
        "task_created",
        {"id": str(task.id), "title": task.title, "status": task.status, "priority": task.priority},
    )

    return task


@transaction.atomic
def update_task(task: Task, data: dict, actor: User) -> Task:
    """Update task attributes with granular event logging and transactional integrity."""
    if not is_project_member(task.project, actor):
        raise PermissionDenied("You must be a member of this project to update tasks.")

    old_status = task.status
    old_priority = task.priority
    old_assignee = task.assignee
    updated_fields = ["updated_at"]

    if "title" in data:
        title = data["title"].strip()
        if not title:
            raise ValidationError({"title": "Task title cannot be empty."})
        task.title = title
        updated_fields.append("title")

    if "description" in data:
        task.description = data["description"].strip()
        updated_fields.append("description")

    if "status" in data and data["status"] != old_status:
        new_status = data["status"]
        if new_status not in Task.Status.values:
            raise ValidationError({"status": f"Invalid status '{new_status}'."})
        task.status = new_status
        updated_fields.append("status")

        if new_status == Task.Status.DONE:
            task.completed_at = timezone.now()
        else:
            task.completed_at = None
        updated_fields.append("completed_at")

        ActivityLog.objects.create(
            project=task.project,
            task=task,
            actor=actor,
            action=ActivityLog.Action.STATUS_CHANGED,
            metadata={"task_title": task.title, "old_status": old_status, "new_status": new_status},
        )

    if "priority" in data and data["priority"] != old_priority:
        new_prio = data["priority"]
        if new_prio not in Task.Priority.values:
            raise ValidationError({"priority": f"Invalid priority '{new_prio}'."})
        task.priority = new_prio
        updated_fields.append("priority")

        ActivityLog.objects.create(
            project=task.project,
            task=task,
            actor=actor,
            action=ActivityLog.Action.PRIORITY_CHANGED,
            metadata={"task_title": task.title, "old_priority": old_priority, "new_priority": new_prio},
        )

    if "assignee" in data:
        new_assignee = data["assignee"]
        validate_assignee_in_project(task.project, new_assignee)
        if new_assignee != old_assignee:
            task.assignee = new_assignee
            updated_fields.append("assignee")

            ActivityLog.objects.create(
                project=task.project,
                task=task,
                actor=actor,
                action=ActivityLog.Action.ASSIGNMENT_CHANGED,
                metadata={
                    "task_title": task.title,
                    "old_assignee": old_assignee.username if old_assignee else None,
                    "new_assignee": new_assignee.username if new_assignee else None,
                },
            )

    if "due_date" in data:
        task.due_date = data["due_date"]
        updated_fields.append("due_date")

    if "position" in data:
        task.position = float(data["position"])
        updated_fields.append("position")

    task.save(update_fields=list(set(updated_fields)))

    broadcast_project_event(
        str(task.project_id),
        "task_updated",
        {"id": str(task.id), "title": task.title, "status": task.status, "priority": task.priority},
    )

    return task


@transaction.atomic
def reorder_task_kanban(task: Task, new_status: str, new_position: float, actor: User) -> Task:
    """Atomic reordering of a task on the Kanban board."""
    if not is_project_member(task.project, actor):
        raise PermissionDenied("You must be a member of this project to move tasks.")

    if new_status not in Task.Status.values:
        raise ValidationError({"status": f"Invalid status '{new_status}'."})

    old_status = task.status
    task.status = new_status
    task.position = new_position
    updated_fields = ["status", "position", "updated_at"]

    if new_status != old_status:
        if new_status == Task.Status.DONE:
            task.completed_at = timezone.now()
        else:
            task.completed_at = None
        updated_fields.append("completed_at")

        ActivityLog.objects.create(
            project=task.project,
            task=task,
            actor=actor,
            action=ActivityLog.Action.STATUS_CHANGED,
            metadata={"task_title": task.title, "old_status": old_status, "new_status": new_status},
        )

    task.save(update_fields=updated_fields)

    broadcast_project_event(
        str(task.project_id),
        "task_reordered",
        {"id": str(task.id), "status": task.status, "position": task.position},
    )

    return task


@transaction.atomic
def delete_task(task: Task, actor: User) -> None:
    """Delete a task and log the event."""
    if not is_project_member(task.project, actor):
        raise PermissionDenied("You must be a member of this project to delete tasks.")

    project_id = str(task.project_id)
    task_id = str(task.id)
    task_title = task.title

    ActivityLog.objects.create(
        project=task.project,
        actor=actor,
        action=ActivityLog.Action.TASK_DELETED,
        metadata={"task_title": task_title},
    )

    task.delete()

    broadcast_project_event(
        project_id,
        "task_deleted",
        {"id": task_id, "title": task_title},
    )


@transaction.atomic
def create_task_comment(task: Task, author: User, body: str) -> TaskComment:
    """Post a comment on a task by an authorized project member."""
    if not is_project_member(task.project, author):
        raise PermissionDenied("You must be a member of this project to comment.")

    body = body.strip()
    if not body:
        raise ValidationError({"body": "Comment text cannot be blank."})

    comment = TaskComment.objects.create(
        task=task,
        author=author,
        body=body,
    )

    ActivityLog.objects.create(
        project=task.project,
        task=task,
        actor=author,
        action=ActivityLog.Action.COMMENT_ADDED,
        metadata={"task_title": task.title, "comment_id": comment.id},
    )

    broadcast_project_event(
        str(task.project_id),
        "comment_added",
        {"task_id": str(task.id), "author": author.username, "comment_id": comment.id},
    )

    return comment
