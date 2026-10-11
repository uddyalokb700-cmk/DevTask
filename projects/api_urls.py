from django.urls import path

from projects.api_views import (
    DashboardStatsAPIView,
    ProjectActivityAPIView,
    ProjectArchiveAPIView,
    ProjectDetailAPIView,
    ProjectListCreateAPIView,
    ProjectMemberDetailAPIView,
    ProjectMemberListCreateAPIView,
    ProjectStatsAPIView,
    ProjectTransferOwnershipAPIView,
)

urlpatterns = [
    path("dashboard-stats/", DashboardStatsAPIView.as_view(), name="api-dashboard-stats"),
    path("", ProjectListCreateAPIView.as_view(), name="api-project-list"),
    path("<uuid:project_id>/", ProjectDetailAPIView.as_view(), name="api-project-detail"),
    path("<uuid:project_id>/archive/", ProjectArchiveAPIView.as_view(), name="api-project-archive"),
    path(
        "<uuid:project_id>/transfer-ownership/", ProjectTransferOwnershipAPIView.as_view(), name="api-project-transfer"
    ),
    path("<uuid:project_id>/members/", ProjectMemberListCreateAPIView.as_view(), name="api-project-members"),
    path(
        "<uuid:project_id>/members/<int:membership_id>/",
        ProjectMemberDetailAPIView.as_view(),
        name="api-project-member-detail",
    ),
    path("<uuid:project_id>/stats/", ProjectStatsAPIView.as_view(), name="api-project-stats"),
    path("<uuid:project_id>/activity/", ProjectActivityAPIView.as_view(), name="api-project-activity"),
]
