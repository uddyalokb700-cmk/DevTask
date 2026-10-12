from django.contrib.auth import logout
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST


def login_view(request):
    """Render user authentication screen."""
    if request.user.is_authenticated:
        return redirect("projects:dashboard")
    return render(request, "accounts/login.html")


def register_view(request):
    """Render account registration screen."""
    if request.user.is_authenticated:
        return redirect("projects:dashboard")
    return render(request, "accounts/register.html")


@require_POST
def logout_view(request):
    """Log out user and redirect to login (requires POST to prevent logout CSRF)."""
    logout(request)
    return redirect("accounts:login")

