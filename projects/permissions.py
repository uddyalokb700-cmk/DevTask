from rest_framework import permissions

from projects.models import Project, ProjectMembership


def get_user_project_role(project: Project, user) -> str | None:
    """Return the user's role in the given project, or None if not an active member."""
    if not user or not user.is_authenticated:
        return None
    if project.owner_id == user.id:
        return ProjectMembership.Role.OWNER
    membership = ProjectMembership.objects.filter(project=project, user=user).first()
    return membership.role if membership else None


def is_project_member(project: Project, user) -> bool:
    """Check if the user is the owner or has an active membership."""
    return get_user_project_role(project, user) is not None


def is_project_manager_or_owner(project: Project, user) -> bool:
    role = get_user_project_role(project, user)
    return role in (ProjectMembership.Role.OWNER, ProjectMembership.Role.MANAGER)


def is_project_owner(project: Project, user) -> bool:
    role = get_user_project_role(project, user)
    return role == ProjectMembership.Role.OWNER


class IsProjectMember(permissions.BasePermission):
    """Allows access only to authenticated users who are members or owners of the project."""

    def has_object_permission(self, request, view, obj):
        project = obj if isinstance(obj, Project) else getattr(obj, "project", None)
        if project is None:
            return False
        return is_project_member(project, request.user)


class IsProjectManagerOrOwner(permissions.BasePermission):
    """Allows access only to project managers or project owners."""

    def has_object_permission(self, request, view, obj):
        project = obj if isinstance(obj, Project) else getattr(obj, "project", None)
        if project is None:
            return False
        return is_project_manager_or_owner(project, request.user)


class IsProjectOwner(permissions.BasePermission):
    """Allows access only to the project owner."""

    def has_object_permission(self, request, view, obj):
        project = obj if isinstance(obj, Project) else getattr(obj, "project", None)
        if project is None:
            return False
        return is_project_owner(project, request.user)
