import pytest

from tasks.models import ActivityLog, Task, TaskComment


@pytest.mark.django_db
class TestCommentsAndActivity:
    def test_member_can_comment_on_task(self, api_client, project_with_team, user_alice, user_charlie):
        task = Task.objects.create(
            project=project_with_team,
            title="Landing Gear Hydraulics",
            status=Task.Status.TODO,
            created_by=user_alice,
        )

        api_client.force_authenticate(user=user_charlie)  # Charlie is Member
        res = api_client.post(
            f"/api/tasks/{task.id}/comments/",
            {"body": "Pressure test completed with nominal results."},
            format="json",
        )
        assert res.status_code == 201
        assert res.data["body"] == "Pressure test completed with nominal results."
        assert res.data["author"]["username"] == "charlie"

        # Check comment in DB
        comment = TaskComment.objects.filter(task=task).first()
        assert comment is not None
        assert comment.author == user_charlie

        # Check activity log was emitted
        log = ActivityLog.objects.filter(task=task, action=ActivityLog.Action.COMMENT_ADDED).first()
        assert log is not None
        assert log.actor == user_charlie

    def test_stranger_cannot_comment_or_view_comments(self, api_client, project_with_team, user_alice, user_stranger):
        task = Task.objects.create(
            project=project_with_team,
            title="Restricted System",
            status=Task.Status.TODO,
            created_by=user_alice,
        )

        api_client.force_authenticate(user=user_stranger)
        # Attempt to view comments
        get_res = api_client.get(f"/api/tasks/{task.id}/comments/")
        assert get_res.status_code == 403

        # Attempt to post comment
        post_res = api_client.post(
            f"/api/tasks/{task.id}/comments/",
            {"body": "Unauthorized injection attempt"},
            format="json",
        )
        assert post_res.status_code == 403

    def test_project_activity_logs_paginated(self, api_client, project_with_team, user_alice):
        api_client.force_authenticate(user=user_alice)

        # Generate 30 activity logs
        for i in range(30):
            ActivityLog.objects.create(
                project=project_with_team,
                actor=user_alice,
                action=ActivityLog.Action.TASK_UPDATED,
                metadata={"iteration": i},
            )

        res = api_client.get(f"/api/projects/{project_with_team.id}/activity/")
        assert res.status_code == 200
        assert "results" in res.data
        assert len(res.data["results"]) == 25  # Page size limit is 25
        assert res.data["count"] >= 30
