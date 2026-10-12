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

    def test_regular_member_cannot_delete_other_members_task(
        self, api_client, project_with_team, user_alice, user_bob, user_charlie
    ):
        # Alice creates a task
        task_alice = Task.objects.create(
            project=project_with_team,
            title="Alice's Architect Design",
            status=Task.Status.TODO,
            created_by=user_alice,
        )

        # Charlie (regular MEMBER) cannot delete Alice's task
        api_client.force_authenticate(user=user_charlie)
        res_charlie_del = api_client.delete(f"/api/tasks/{task_alice.id}/")
        assert res_charlie_del.status_code == 403
        assert Task.objects.filter(pk=task_alice.id).exists()

        # Charlie CAN delete a task Charlie created
        task_charlie = Task.objects.create(
            project=project_with_team,
            title="Charlie's Feature Task",
            status=Task.Status.TODO,
            created_by=user_charlie,
        )
        res_charlie_own_del = api_client.delete(f"/api/tasks/{task_charlie.id}/")
        assert res_charlie_own_del.status_code == 204
        assert not Task.objects.filter(pk=task_charlie.id).exists()

        # Bob (MANAGER) CAN delete Alice's task
        api_client.force_authenticate(user=user_bob)
        res_bob_del = api_client.delete(f"/api/tasks/{task_alice.id}/")
        assert res_bob_del.status_code == 204
        assert not Task.objects.filter(pk=task_alice.id).exists()

    def test_cannot_mutate_tasks_on_archived_project(
        self, api_client, project_with_team, user_alice
    ):
        task = Task.objects.create(
            project=project_with_team,
            title="Pre-archive Task",
            status=Task.Status.TODO,
            created_by=user_alice,
        )

        # Archive project
        api_client.force_authenticate(user=user_alice)
        api_client.post(
            f"/api/projects/{project_with_team.id}/archive/",
            {"action": "archive"},
            format="json",
        )
        project_with_team.refresh_from_db()
        assert project_with_team.is_archived is True

        # Creating new task on archived project fails
        res_create = api_client.post(
            "/api/tasks/",
            {"project_id": str(project_with_team.id), "title": "New Task"},
            format="json",
        )
        assert res_create.status_code == 400

        # Updating existing task on archived project fails
        res_update = api_client.patch(
            f"/api/tasks/{task.id}/",
            {"title": "Updated Title"},
            format="json",
        )
        assert res_update.status_code == 400

        # Reordering task on archived project fails
        res_reorder = api_client.post(
            f"/api/tasks/{task.id}/reorder/",
            {"status": "DONE", "position": 5.0},
            format="json",
        )
        assert res_reorder.status_code == 400

        # Commenting on task in archived project fails
        res_comment = api_client.post(
            f"/api/tasks/{task.id}/comments/",
            {"body": "Comment on archived project task"},
            format="json",
        )
        assert res_comment.status_code == 400

        # Deleting task on archived project fails
        res_del = api_client.delete(f"/api/tasks/{task.id}/")
        assert res_del.status_code == 400

    def test_task_patch_and_create_rejects_invalid_assignee(
        self, api_client, project_with_team, user_alice
    ):
        from django.contrib.auth.models import User

        task = Task.objects.create(
            project=project_with_team,
            title="Task for Validation",
            status=Task.Status.TODO,
            created_by=user_alice,
        )
        api_client.force_authenticate(user=user_alice)

        # 1. Non-integer assignee_id must return 400 Bad Request (not 500!)
        res_str = api_client.patch(
            f"/api/tasks/{task.id}/",
            {"assignee_id": "invalid_string"},
            format="json",
        )
        assert res_str.status_code == 400
        assert "assignee_id" in res_str.data

        # 2. Non-existent user ID must return 400 Bad Request (not 404!)
        res_not_found = api_client.patch(
            f"/api/tasks/{task.id}/",
            {"assignee_id": 999999},
            format="json",
        )
        assert res_not_found.status_code == 400
        assert "assignee_id" in res_not_found.data

        # 3. Deactivated user cannot be assigned
        inactive_user = User.objects.create_user(
            username="inactive_assignee",
            email="inactive_assignee@devtask.test",
            password="TestPassword123!",
            is_active=False,
        )
        res_inactive = api_client.patch(
            f"/api/tasks/{task.id}/",
            {"assignee_id": inactive_user.id},
            format="json",
        )
        assert res_inactive.status_code == 400
        assert "assignee_id" in res_inactive.data

    def test_task_patch_mass_assignment_protection(
        self, api_client, project_with_team, user_alice, user_bob
    ):
        task = Task.objects.create(
            project=project_with_team,
            title="Task Protection",
            status=Task.Status.TODO,
            created_by=user_alice,
        )
        api_client.force_authenticate(user=user_alice)

        res = api_client.patch(
            f"/api/tasks/{task.id}/",
            {
                "title": "Clean Updated Title",
                "created_by": user_bob.id,
                "id": "11111111-1111-1111-1111-111111111111",
            },
            format="json",
        )
        assert res.status_code == 200
        task.refresh_from_db()
        assert task.title == "Clean Updated Title"
        # Protected fields cannot be changed
        assert task.created_by == user_alice
        assert str(task.id) != "11111111-1111-1111-1111-111111111111"

