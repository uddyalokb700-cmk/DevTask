from django.contrib.auth import logout
from django.shortcuts import redirect, render


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


def logout_view(request):
    """Log out user and redirect to login."""
    logout(request)
    return redirect("accounts:login")
