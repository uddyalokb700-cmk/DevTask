"""Locust Load Testing Suite for DevTask API.

Run locally:
    locust -f loadtests/locustfile.py --host=http://127.0.0.1:8000

Or headless smoke benchmark:
    locust -f loadtests/locustfile.py --host=http://127.0.0.1:8000 --headless -u 20 -r 5 --run-time 30s
"""

import random

from locust import HttpUser, between, task


class DevTaskUser(HttpUser):
    wait_time = between(1.0, 3.0)

    def on_start(self):
        """Authenticate user and obtain session & CSRF cookie."""
        login_res = self.client.post(
            "/api/auth/login/",
            json={"username": "alice", "password": "DevTask123!"},
        )
        if login_res.status_code != 200:
            # Fallback to admin if alice is not seeded
            self.client.post(
                "/api/auth/login/",
                json={"username": "admin", "password": "AdminPass123!"},
            )

        # Cache accessible projects
        projs_res = self.client.get("/api/projects/")
        if projs_res.status_code == 200:
            self.projects = projs_res.json()
        else:
            self.projects = []

    def get_csrf_token(self):
        return self.client.cookies.get("csrftoken", "")

    @task(5)
    def view_dashboard_stats(self):
        """Retrieve aggregated dashboard KPI metrics."""
        self.client.get("/api/projects/dashboard-stats/", name="[GET] /api/projects/dashboard-stats/")

    @task(4)
    def list_projects(self):
        """List active projects with annotations."""
        self.client.get("/api/projects/", name="[GET] /api/projects/")

    @task(5)
    def list_paginated_tasks(self):
        """List paginated tasks with select_related joins."""
        self.client.get("/api/tasks/?page=1", name="[GET] /api/tasks/?page=1")

    @task(4)
    def filter_tasks(self):
        """Filter tasks by status and priority."""
        status = random.choice(["TODO", "IN_PROGRESS", "DONE"])
        priority = random.choice(["LOW", "MEDIUM", "HIGH", "URGENT"])
        self.client.get(
            f"/api/tasks/?status={status}&priority={priority}",
            name="[GET] /api/tasks/?status=&priority=",
        )

    @task(3)
    def view_project_stats(self):
        """View database-side aggregated statistics for a project."""
        if self.projects:
            project_id = random.choice(self.projects)["id"]
            self.client.get(
                f"/api/projects/{project_id}/stats/",
                name="[GET] /api/projects/{id}/stats/",
            )

    @task(2)
    def view_project_activity(self):
        """View paginated project activity history."""
        if self.projects:
            project_id = random.choice(self.projects)["id"]
            self.client.get(
                f"/api/projects/{project_id}/activity/",
                name="[GET] /api/projects/{id}/activity/",
            )

    @task(1)
    def reorder_task(self):
        """Simulate Kanban drag-and-drop column move."""
        tasks_res = self.client.get("/api/tasks/?page=1")
        if tasks_res.status_code == 200:
            data = tasks_res.json()
            results = data.get("results", [])
            if results:
                target_task = random.choice(results)
                new_status = random.choice(["TODO", "IN_PROGRESS", "DONE"])
                csrf = self.get_csrf_token()
                self.client.post(
                    f"/api/tasks/{target_task['id']}/reorder/",
                    json={"status": new_status, "position": random.uniform(1.0, 10.0)},
                    headers={"X-CSRFToken": csrf},
                    name="[POST] /api/tasks/{id}/reorder/",
                )
