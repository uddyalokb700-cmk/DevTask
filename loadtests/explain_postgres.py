"""PostgreSQL Query Plan Benchmark Script.

Provides exact commands, queries, and execution wrappers to inspect PostgreSQL query plans
using EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT TEXT).

Usage against PostgreSQL:
    export DATABASE_URL=postgres://user:password@localhost:5432/devtask
    python loadtests/explain_postgres.py

Or via psql directly:
    psql -d devtask -f loadtests/explain_postgres.sql
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.db import connection

POSTGRES_EXPLAIN_QUERIES = [
    (
        "1. Project List Query with Aggregations and User Filtering",
        """
        EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
        SELECT DISTINCT
            p.id, p.name, p.description, p.owner_id, p.created_at, p.updated_at, p.archived_at,
            COUNT(DISTINCT pm.id) AS members_count,
            COUNT(DISTINCT t.id) AS tasks_count,
            COUNT(DISTINCT t.id) FILTER (WHERE t.status = 'DONE') AS completed_tasks_count,
            u.id, u.username, up.display_name, up.avatar_color
        FROM projects_project p
        INNER JOIN auth_user u ON (p.owner_id = u.id)
        LEFT OUTER JOIN projects_projectmembership pm ON (p.id = pm.project_id)
        LEFT OUTER JOIN tasks_task t ON (p.id = t.project_id)
        LEFT OUTER JOIN accounts_userprofile up ON (u.id = up.user_id)
        WHERE (p.owner_id = 1 OR pm.user_id = 1) AND p.archived_at IS NULL
        GROUP BY p.id, u.id, up.id
        ORDER BY p.updated_at DESC;
        """,
    ),
    (
        "2. Paginated Tasks with Composite Index and Subquery Comments Count",
        """
        EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
        SELECT
            t.id, t.project_id, t.title, t.description, t.status, t.priority,
            t.created_by_id, t.assignee_id, t.due_date, t.position, t.created_at, t.updated_at,
            COALESCE((
                SELECT COUNT(c.id)
                FROM tasks_taskcomment c
                WHERE c.task_id = t.id
            ), 0) AS comments_count,
            p.name AS project_name,
            u.username AS creator_username,
            a.username AS assignee_username
        FROM tasks_task t
        INNER JOIN projects_project p ON (t.project_id = p.id)
        INNER JOIN auth_user u ON (t.created_by_id = u.id)
        LEFT OUTER JOIN auth_user a ON (t.assignee_id = a.id)
        WHERE t.project_id = (SELECT id FROM projects_project LIMIT 1)
        ORDER BY t.position ASC, t.created_at DESC
        LIMIT 20 OFFSET 0;
        """,
    ),
    (
        "3. Filtered Tasks (Status=TODO, Priority=HIGH using idx_task_status_prio)",
        """
        EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
        SELECT
            t.id, t.project_id, t.title, t.status, t.priority, t.due_date
        FROM tasks_task t
        WHERE t.status = 'TODO' AND t.priority = 'HIGH'
        ORDER BY t.position ASC
        LIMIT 20;
        """,
    ),
    (
        "4. Dashboard Aggregation Across Projects",
        """
        EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
        SELECT
            COUNT(t.id) AS total_tasks,
            COUNT(CASE WHEN t.status = 'TODO' THEN 1 END) AS todo_tasks,
            COUNT(CASE WHEN t.status = 'IN_PROGRESS' THEN 1 END) AS in_progress_tasks,
            COUNT(CASE WHEN t.status = 'DONE' THEN 1 END) AS done_tasks,
            COUNT(CASE WHEN t.due_date < CURRENT_DATE AND t.status != 'DONE' THEN 1 END) AS overdue_tasks
        FROM tasks_task t
        INNER JOIN projects_project p ON (t.project_id = p.id)
        WHERE p.archived_at IS NULL AND (p.owner_id = 1 OR EXISTS (
            SELECT 1 FROM projects_projectmembership pm WHERE pm.project_id = p.id AND pm.user_id = 1
        ));
        """,
    ),
]


def run_postgres_explain():
    vendor = connection.vendor
    print(f"Active Django Database Backend: {vendor.upper()}")
    if vendor != "postgresql":
        print(
            "\n[NOTE] PostgreSQL is not configured as the active database backend in this environment.\n"
            "This script outputs the exact PostgreSQL statements with EXPLAIN (ANALYZE, BUFFERS, VERBOSE).\n"
            "To execute against a live PostgreSQL database, ensure DATABASE_URL is configured and re-run.\n"
        )

    for title, query in POSTGRES_EXPLAIN_QUERIES:
        print("=" * 80)
        print(f"QUERY: {title}")
        print("=" * 80)
        print(query.strip())
        print("-" * 80)
        if vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(query)
                for row in cursor.fetchall():
                    print(row[0])
        else:
            print("[COMMAND TO RUN ON POSTGRESQL]:")
            print(f"psql $DATABASE_URL -c \"{query.strip().replace(chr(10), ' ')}\"")
        print("\n")


if __name__ == "__main__":
    run_postgres_explain()
