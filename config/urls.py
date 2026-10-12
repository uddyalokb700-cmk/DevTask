"""Root URL Configuration for DevTask."""

from django.conf import settings
from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


def health_check(request):
    """Deployment health check endpoint verifying database connectivity."""
    status = {"status": "ok", "database": "healthy"}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return JsonResponse(status, status=200)
    except Exception as exc:
        status["status"] = "error"
        status["database"] = f"unhealthy: {str(exc)}" if settings.DEBUG else "unhealthy"
        return JsonResponse(status, status=503)



urlpatterns = [
    # Administration
    path("admin/", admin.site.urls),
    # Health Check
    path("health/", health_check, name="health-check"),
    # OpenAPI Schema & Interactive Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # REST APIs
    path("api/auth/", include("accounts.api_urls")),
    path("api/projects/", include("projects.api_urls")),
    path("api/tasks/", include("tasks.api_urls")),
    # Frontend Views (Django Templates)
    path("", include("accounts.urls")),
    path("", include("projects.urls")),
    path("", include("tasks.urls")),
]
