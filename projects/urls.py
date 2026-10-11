from django.urls import path

from projects.views import (
    dashboard_view,
    project_board_view,
    projects_list_view,
    root_redirect,
)

app_name = "projects"

urlpatterns = [
    path("", root_redirect, name="root"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("projects/", projects_list_view, name="projects-list"),
    path("projects/<uuid:project_id>/", project_board_view, name="project-board"),
]
