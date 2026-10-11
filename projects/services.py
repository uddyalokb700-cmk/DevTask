from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from projects.models import Project, ProjectMembership
from projects.permissions import (
    is_project_manager_or_owner,
    is_project_owner,
)
from tasks.models import ActivityLog


@transaction.atomic
def create_project(name: str, description: str, owner: User) -> Project:
    """Create a new project and initialize owner membership and activity log."""
    name = name.strip()
    if not name:
        raise ValidationError({"name": "Project name cannot be empty."})

    project = Project.objects.create(
        name=name,
        description=description.strip() if description else "",
        owner=owner,
    )
    # Create owner membership
    ProjectMembership.objects.create(
        project=project,
        user=owner,
        role=ProjectMembership.Role.OWNER,
    )
    # Log activity
    ActivityLog.objects.create(
        project=project,
        actor=owner,
        action=ActivityLog.Action.PROJECT_UPDATED,
        metadata={"detail": f"Project '{project.name}' created by {owner.username}."},
    )
    return project


@transaction.atomic
def update_project(project: Project, data: dict, actor: User) -> Project:
    """Update project details if actor is manager or owner."""
    if not is_project_manager_or_owner(project, actor):
        raise PermissionDenied("Only project managers or owners can update project details.")

    if "name" in data:
        name = data["name"].strip()
        if not name:
            raise ValidationError({"name": "Project name cannot be empty."})
        project.name = name

    if "description" in data:
        project.description = data["description"].strip()

    project.save(update_fields=["name", "description", "updated_at"])

    ActivityLog.objects.create(
        project=project,
        actor=actor,
        action=ActivityLog.Action.PROJECT_UPDATED,
        metadata={"name": project.name},
    )
    return project


@transaction.atomic
def archive_project(project: Project, actor: User) -> Project:
    """Archive a project (owner only)."""
    if not is_project_owner(project, actor):
        raise PermissionDenied("Only the project owner can archive this project.")

    project.archive()
    ActivityLog.objects.create(
        project=project,
        actor=actor,
        action=ActivityLog.Action.PROJECT_ARCHIVED,
        metadata={"archived": True},
    )
    return project


@transaction.atomic
def unarchive_project(project: Project, actor: User) -> Project:
    """Restore an archived project (owner only)."""
    if not is_project_owner(project, actor):
        raise PermissionDenied("Only the project owner can restore this project.")

    project.unarchive()
    ActivityLog.objects.create(
        project=project,
        actor=actor,
        action=ActivityLog.Action.PROJECT_RESTORED,
        metadata={"archived": False},
    )
    return project


@transaction.atomic
def delete_project(project: Project, actor: User) -> None:
    """Delete a project permanently (owner only)."""
    if not is_project_owner(project, actor):
        raise PermissionDenied("Only the project owner can permanently delete this project.")

    project.delete()


@transaction.atomic
def add_project_member(project: Project, user: User, role: str, actor: User) -> ProjectMembership:
    """Add a new member to the project."""
    if not is_project_manager_or_owner(project, actor):
        raise PermissionDenied("Only project managers or owners can add team members.")

    if role not in ProjectMembership.Role.values:
        raise ValidationError({"role": f"Invalid role '{role}'."})

    # Cannot add someone as OWNER directly (ownership must be transferred)
    if role == ProjectMembership.Role.OWNER and not is_project_owner(project, actor):
        raise PermissionDenied("Only the owner can assign the OWNER role.")

    if ProjectMembership.objects.filter(project=project, user=user).exists():
        raise ValidationError({"user": f"User '{user.username}' is already a member of this project."})

    membership = ProjectMembership.objects.create(
        project=project,
        user=user,
        role=role,
    )

    ActivityLog.objects.create(
        project=project,
        actor=actor,
        action=ActivityLog.Action.MEMBER_ADDED,
        metadata={"username": user.username, "role": role},
    )
    return membership


@transaction.atomic
def update_project_membership(
    project: Project, membership: ProjectMembership, new_role: str, actor: User
) -> ProjectMembership:
    """Update a team member's role."""
    if not is_project_manager_or_owner(project, actor):
        raise PermissionDenied("Only project managers or owners can modify member roles.")

    if new_role not in ProjectMembership.Role.values:
        raise ValidationError({"role": f"Invalid role '{new_role}'."})

    # Prevent non-owners from promoting to OWNER or altering owner's role
    if membership.role == ProjectMembership.Role.OWNER and not is_project_owner(project, actor):
        raise PermissionDenied("Cannot modify the owner's role.")

    if new_role == ProjectMembership.Role.OWNER and not is_project_owner(project, actor):
        raise PermissionDenied("Only the current owner can transfer or grant the owner role.")

    old_role = membership.role
    membership.role = new_role
    membership.save(update_fields=["role"])

    ActivityLog.objects.create(
        project=project,
        actor=actor,
        action=ActivityLog.Action.MEMBER_ROLE_CHANGED,
        metadata={"username": membership.user.username, "old_role": old_role, "new_role": new_role},
    )
    return membership


@transaction.atomic
def remove_project_member(project: Project, membership: ProjectMembership, actor: User) -> None:
    """Remove a member from the project and unassign their tasks."""
    if not is_project_manager_or_owner(project, actor):
        raise PermissionDenied("Only project managers or owners can remove team members.")

    # Prevent removing the project owner
    if membership.user_id == project.owner_id:
        raise ValidationError({"detail": "Cannot remove the project owner. Transfer ownership first."})

    user = membership.user
    # Unassign tasks currently assigned to this user in this project
    project.tasks.filter(assignee=user).update(assignee=None)

    membership.delete()

    ActivityLog.objects.create(
        project=project,
        actor=actor,
        action=ActivityLog.Action.MEMBER_REMOVED,
        metadata={"username": user.username},
    )


@transaction.atomic
def transfer_project_ownership(project: Project, new_owner: User, actor: User) -> Project:
    """Transfer project ownership to another active member (owner only)."""
    if not is_project_owner(project, actor):
        raise PermissionDenied("Only the current project owner can transfer ownership.")

    if new_owner.id == project.owner_id:
        raise ValidationError({"detail": "User is already the owner."})

    # Ensure new owner is already a member
    membership = ProjectMembership.objects.filter(project=project, user=new_owner).first()
    if not membership:
        raise ValidationError({"detail": f"User '{new_owner.username}' must be a member of the project first."})

    old_owner = project.owner
    project.owner = new_owner
    project.save(update_fields=["owner", "updated_at"])

    # Update new owner membership role to OWNER
    membership.role = ProjectMembership.Role.OWNER
    membership.save(update_fields=["role"])

    # Update previous owner membership role to MANAGER
    old_owner_membership = ProjectMembership.objects.filter(project=project, user=old_owner).first()
    if old_owner_membership:
        old_owner_membership.role = ProjectMembership.Role.MANAGER
        old_owner_membership.save(update_fields=["role"])

    ActivityLog.objects.create(
        project=project,
        actor=actor,
        action=ActivityLog.Action.MEMBER_ROLE_CHANGED,
        metadata={"new_owner": new_owner.username, "old_owner": old_owner.username},
    )
    return project
