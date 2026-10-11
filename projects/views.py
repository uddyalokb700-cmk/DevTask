from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from projects.models import Project
from projects.permissions import is_project_member


def root_redirect(request):
    """Redirect root path to dashboard or login."""
    if request.user.is_authenticated:
        return redirect("projects:dashboard")
    return redirect("accounts:login")


@login_required
def dashboard_view(request):
    """Render high-level developer SaaS metrics dashboard."""
    return render(request, "dashboard/index.html")


@login_required
def projects_list_view(request):
    """Render projects workspace overview."""
    return render(request, "projects/index.html")


@login_required
def project_board_view(request, project_id):
    """Render project Kanban board, task manager, and member drawer."""
    project = get_object_or_404(Project, pk=project_id)
    if not is_project_member(project, request.user):
        raise PermissionDenied("You are not a member of this project.")
    return render(request, "projects/board.html", {"project": project})
