import datetime

import pytest
from django.utils import timezone

from tasks.models import ActivityLog, Task


@pytest.mark.django_db
class TestTasks:
    def test_task_creation(self, api_client, project_with_team, user_alice, user_bob):
        api_client.force_authenticate(user=user_alice)
        today = timezone.now().date()
        res = api_client.post(
            "/api/tasks/",
            {
                "project_id": str(project_with_team.id),
                "title": "Build Telemetry Ingestion",
                "description": "Kafka consumer pipeline",
                "status": "TODO",
                "priority": "HIGH",
                "assignee_id": user_bob.id,
                "due_date": str(today + datetime.timedelta(days=3)),
            },
            format="json",
        )
        assert res.status_code == 201
        task_id = res.data["id"]
        task = Task.objects.get(pk=task_id)
        assert task.title == "Build Telemetry Ingestion"
        assert task.assignee == user_bob
        assert task.created_by == user_alice
        assert task.completed_at is None

        # Verify activity log was created
        log = ActivityLog.objects.filter(task=task, action=ActivityLog.Action.TASK_CREATED).first()
        assert log is not None
        assert log.actor == user_alice

    def test_assignee_must_be_project_member(self, api_client, project_with_team, user_alice, user_stranger):
        api_client.force_authenticate(user=user_alice)
        # Try to assign task to someone outside the project
        res = api_client.post(
            "/api/tasks/",
            {
                "project_id": str(project_with_team.id),
                "title": "Invalid Assignee Task",
                "assignee_id": user_stranger.id,
            },
            format="json",
        )
        assert res.status_code == 400
        assert "assignee" in str(res.data)

    def test_status_transition_and_completed_at(self, api_client, project_with_team, user_alice):
        api_client.force_authenticate(user=user_alice)
        task = Task.objects.create(
            project=project_with_team,
            title="Calibrate Sensors",
            status=Task.Status.TODO,
            created_by=user_alice,
        )
        assert task.completed_at is None

        # Transition to IN_PROGRESS
        patch_res1 = api_client.patch(
            f"/api/tasks/{task.id}/",
            {"status": "IN_PROGRESS"},
            format="json",
        )
        assert patch_res1.status_code == 200
        task.refresh_from_db()
        assert task.status == Task.Status.IN_PROGRESS
        assert task.completed_at is None

        # Transition to DONE -> sets completed_at
        patch_res2 = api_client.patch(
            f"/api/tasks/{task.id}/",
            {"status": "DONE"},
            format="json",
        )
        assert patch_res2.status_code == 200
        task.refresh_from_db()
        assert task.status == Task.Status.DONE
        assert task.completed_at is not None

        # Reopen to TODO -> clears completed_at
        patch_res3 = api_client.patch(
            f"/api/tasks/{task.id}/",
            {"status": "TODO"},
            format="json",
        )
        assert patch_res3.status_code == 200
        task.refresh_from_db()
        assert task.status == Task.Status.TODO
        assert task.completed_at is None

    def test_reorder_task_kanban(self, api_client, project_with_team, user_alice):
        api_client.force_authenticate(user=user_alice)
        task = Task.objects.create(
            project=project_with_team,
            title="Docking Simulation",
            status=Task.Status.TODO,
            position=1.0,
            created_by=user_alice,
        )

        res = api_client.post(
            f"/api/tasks/{task.id}/reorder/",
            {"status": "IN_PROGRESS", "position": 2.5},
            format="json",
        )
        assert res.status_code == 200
        task.refresh_from_db()
        assert task.status == Task.Status.IN_PROGRESS
        assert task.position == 2.5

    def test_task_filtering_and_pagination(self, api_client, project_with_team, user_alice):
        api_client.force_authenticate(user=user_alice)
        # Create 5 tasks with distinct attributes
        for i in range(5):
            Task.objects.create(
                project=project_with_team,
                title=f"Subsystem {i}",
                status=Task.Status.TODO if i % 2 == 0 else Task.Status.DONE,
                priority=Task.Priority.URGENT if i == 0 else Task.Priority.LOW,
                created_by=user_alice,
            )

        # Filter by status=TODO
        res_todo = api_client.get(f"/api/tasks/?project_id={project_with_team.id}&status=TODO")
        assert res_todo.status_code == 200
        for item in res_todo.data["results"]:
            assert item["status"] == "TODO"

        # Filter by priority=URGENT
        res_urgent = api_client.get(f"/api/tasks/?project_id={project_with_team.id}&priority=URGENT")
        assert res_urgent.status_code == 200
        assert len(res_urgent.data["results"]) == 1

        # Search filter
        res_search = api_client.get(f"/api/tasks/?project_id={project_with_team.id}&search=Subsystem 3")
        assert res_search.status_code == 200
        assert len(res_search.data["results"]) == 1

    def test_idor_protection_stranger_cannot_view_or_modify_task(
        self, api_client, project_with_team, user_alice, user_stranger
    ):
        task = Task.objects.create(
            project=project_with_team,
            title="Secret Flight Plan",
            status=Task.Status.TODO,
            created_by=user_alice,
        )

        api_client.force_authenticate(user=user_stranger)

        # Stranger cannot GET task
        res_get = api_client.get(f"/api/tasks/{task.id}/")
        assert res_get.status_code == 403

        # Stranger cannot PATCH task
        res_patch = api_client.patch(
            f"/api/tasks/{task.id}/",
            {"title": "Modified by Stranger"},
            format="json",
        )
        assert res_patch.status_code == 403

        # Stranger cannot DELETE task
        res_del = api_client.delete(f"/api/tasks/{task.id}/")
        assert res_del.status_code == 403

        task.refresh_from_db()
        assert task.title == "Secret Flight Plan"
