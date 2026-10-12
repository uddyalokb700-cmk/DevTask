"""Database Query Plan Analyzer.
Runs EXPLAIN QUERY PLAN on representative DevTask queries and displays execution plans.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.contrib.auth.models import User
from django.db import connection
from django.db.models import Count, Q
from django.utils import timezone

from projects.models import Project
from tasks.models import Task


def explain_query(title, queryset):
    sql, params = queryset.query.sql_with_params()
    with connection.cursor() as cursor:
        cursor.execute(f"EXPLAIN QUERY PLAN {sql}", params)
        rows = cursor.fetchall()

    print("\n" + "=" * 80)
    print(f"QUERY PLAN: {title}")
    print("=" * 80)
    print(f"SQL: {sql[:180]}...")
    print("-" * 80)
    for row in rows:
        # SQLite returns (id, parent, notused, detail)
        detail = row[3] if len(row) > 3 else str(row)
        print(f"  -> {detail}")
    print("-" * 80)


def main():
    alice = User.objects.get(username="alice")
    timezone.now().date()

    # 1. Project List query
    proj_qs = (
        Project.objects.for_user(alice)
        .select_related("owner", "owner__profile")
        .active()
        .annotate(
            members_count=Count("memberships", distinct=True),
            tasks_count=Count("tasks", distinct=True),
            completed_tasks_count=Count("tasks", filter=Q(tasks__status=Task.Status.DONE), distinct=True),
        )
    )
    explain_query("1. Project List with Aggregations", proj_qs)

    # 2. Task List query
    user_projects = Project.objects.for_user(alice)
    task_qs = (
        Task.objects.filter(project__in=user_projects)
        .select_related("project", "created_by", "created_by__profile", "assignee", "assignee__profile")
        .order_by("position", "-created_at")[:20]
    )
    explain_query("2. Task List with Select Related & Ordering", task_qs)

    # 3. Filtered Task Query (status=TODO, priority=HIGH)
    filtered_task_qs = (
        Task.objects.filter(project__in=user_projects, status=Task.Status.TODO, priority=Task.Priority.HIGH)
        .select_related("project", "created_by", "assignee")
        .order_by("position", "-created_at")[:20]
    )
    explain_query("3. Filtered Tasks (Status=TODO, Priority=HIGH using idx_task_status_prio)", filtered_task_qs)

    # 4. Recent Projects (ordering by -updated_at using idx_proj_updated)
    recent_qs = (
        Project.objects.for_user(alice)
        .active()
        .order_by("-updated_at")[:5]
    )
    explain_query("4. Recent Projects Sorted by -updated_at (idx_proj_updated)", recent_qs)


if __name__ == "__main__":
    main()
