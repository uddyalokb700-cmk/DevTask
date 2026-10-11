from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def tasks_view(request):
    """Render cross-project global task management list."""
    return render(request, "tasks/index.html")
