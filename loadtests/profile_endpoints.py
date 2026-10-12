"""Endpoint Profiler: Measures query counts, serialization time, response sizes, and query plans."""

import os
import sys
import time
from pathlib import Path

# Setup Django environment
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.contrib.auth.models import User
from django.db import connection, reset_queries
from django.test import RequestFactory

from projects.api_views import (
    DashboardStatsAPIView,
    ProjectActivityAPIView,
    ProjectDetailAPIView,
    ProjectListCreateAPIView,
    ProjectStatsAPIView,
)
from projects.models import Project
from tasks.api_views import TaskListCreateAPIView
from tasks.models import Task


def run_profile():
    rf = RequestFactory()
    alice = User.objects.get(username="alice")
    bob = User.objects.get(username="bob")  # Non-owner member of many Alice projects
    User.objects.get(username="charlie")

    # Find a project where Alice is owner and Bob is member
    proj = Project.objects.filter(owner=alice, memberships__user=bob).first()
    if not proj:
        proj = Project.objects.first()

    Task.objects.filter(project=proj).first()

    endpoints = [
        (
            "1. Project List (Owner: Alice)",
            ProjectListCreateAPIView.as_view(),
            rf.get("/api/projects/"),
            alice,
            {},
        ),
        (
            "2. Project List (Member: Bob - N+1 Check)",
            ProjectListCreateAPIView.as_view(),
            rf.get("/api/projects/"),
            bob,
            {},
        ),
        (
            "3. Project Detail (Alice)",
            ProjectDetailAPIView.as_view(),
            rf.get(f"/api/projects/{proj.id}/"),
            alice,
            {"project_id": proj.id},
        ),
        (
            "4. Dashboard Stats (Alice)",
            DashboardStatsAPIView.as_view(),
            rf.get("/api/projects/dashboard-stats/"),
            alice,
            {},
        ),
        (
            "5. Project Stats (Alice)",
            ProjectStatsAPIView.as_view(),
            rf.get(f"/api/projects/{proj.id}/stats/"),
            alice,
            {"project_id": proj.id},
        ),
        (
            "6. Task List Paginated (Alice)",
            TaskListCreateAPIView.as_view(),
            rf.get(f"/api/tasks/?project_id={proj.id}&page=1"),
            alice,
            {},
        ),
        (
            "7. Task Filter Status & Priority (Alice)",
            TaskListCreateAPIView.as_view(),
            rf.get("/api/tasks/?status=TODO&priority=HIGH&page=1"),
            alice,
            {},
        ),
        (
            "8. Project Activity (Alice)",
            ProjectActivityAPIView.as_view(),
            rf.get(f"/api/projects/{proj.id}/activity/"),
            alice,
            {"project_id": proj.id},
        ),
    ]

    print("=" * 80)
    print("DEVTASK ENDPOINT PROFILING: QUERY COUNTS, LATENCY & SIZES")
    print("=" * 80)
    print(f"{'Endpoint':<42} | {'Queries':<7} | {'Time (ms)':<9} | {'Size (bytes)':<12}")
    print("-" * 80)

    results = []
    for name, view_func, request, user, kwargs in endpoints:
        request.user = user

        # Warm up
        view_func(request, **kwargs)

        reset_queries()
        start = time.perf_counter()
        response = view_func(request, **kwargs)
        duration_ms = (time.perf_counter() - start) * 1000
        query_count = len(connection.queries)

        payload_bytes = len(getattr(response, "rendered_content", b"") or str(response.data).encode("utf-8"))

        print(f"{name:<42} | {query_count:<7} | {duration_ms:<9.2f} | {payload_bytes:<12}")
        results.append({
            "name": name,
            "queries": query_count,
            "duration_ms": duration_ms,
            "size_bytes": payload_bytes,
            "sql": [q["sql"] for q in connection.queries],
        })

    print("-" * 80)
    return results


if __name__ == "__main__":
    run_profile()
