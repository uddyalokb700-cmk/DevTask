import pytest

from projects.models import Project, ProjectMembership
from tasks.models import Task


@pytest.mark.django_db
class TestPerformanceAndQueryCounts:
    def test_project_list_avoids_n_plus_one(self, api_client, user_alice, django_assert_num_queries):
        api_client.force_authenticate(user=user_alice)

        # Create 10 projects for Alice with members and tasks
        for i in range(10):
            p = Project.objects.create(name=f"Project {i}", owner=user_alice)
            ProjectMembership.objects.create(project=p, user=user_alice, role=ProjectMembership.Role.OWNER)
            for j in range(3):
                Task.objects.create(project=p, title=f"Task {i}-{j}", created_by=user_alice)

        # Exactly 2 queries: 1 for projects with annotations + 1 for prefetched user memberships
        with django_assert_num_queries(2):
            res = api_client.get("/api/projects/")
            assert res.status_code == 200
            assert len(res.data) >= 10

    def test_project_list_avoids_n_plus_one_for_non_owner_member(
        self, api_client, user_alice, user_bob, django_assert_num_queries
    ):
        api_client.force_authenticate(user=user_bob)

        # Alice creates 10 projects and adds Bob as MEMBER to all 10
        for i in range(10):
            p = Project.objects.create(name=f"Alice Project {i}", owner=user_alice)
            ProjectMembership.objects.create(project=p, user=user_alice, role=ProjectMembership.Role.OWNER)
            ProjectMembership.objects.create(project=p, user=user_bob, role=ProjectMembership.Role.MEMBER)

        # Even though Bob is not the owner of 10 projects, prefetch ensures exactly 2 queries (not 1 + 10)!
        with django_assert_num_queries(2):
            res = api_client.get("/api/projects/")
            assert res.status_code == 200
            assert len(res.data) >= 10
            for item in res.data:
                assert item["current_user_role"] == "MEMBER"

    def test_project_detail_avoids_duplicate_queries(
        self, api_client, project_with_team, user_alice, django_assert_num_queries
    ):
        api_client.force_authenticate(user=user_alice)

        # Project detail: 1 query for project annotations + 1 for prefetched memberships with user profiles
        with django_assert_num_queries(2):
            res = api_client.get(f"/api/projects/{project_with_team.id}/")
            assert res.status_code == 200
            assert res.data["name"] == project_with_team.name
            assert len(res.data["members"]) == 3

    def test_task_list_avoids_n_plus_one(
        self, api_client, project_with_team, user_alice, user_bob, user_charlie, django_assert_num_queries
    ):
        api_client.force_authenticate(user=user_alice)

        # Create 20 tasks assigned to different users
        for i in range(20):
            assignee = [user_alice, user_bob, user_charlie, None][i % 4]
            Task.objects.create(
                project=project_with_team,
                title=f"Telemetry Stream {i}",
                status=Task.Status.TODO if i % 2 == 0 else Task.Status.DONE,
                created_by=user_alice,
                assignee=assignee,
            )

        # Listing tasks selects related 'project', 'created_by', 'assignee' with subquery comments_count
        # Queries: 1 count query (pagination) + 1 select query with joins = 2 queries total
        with django_assert_num_queries(2):
            res = api_client.get(f"/api/tasks/?project_id={project_with_team.id}")
            assert res.status_code == 200
            assert len(res.data["results"]) == 20

    def test_project_stats_constant_queries(self, api_client, project_with_team, user_alice, django_assert_num_queries):
        api_client.force_authenticate(user=user_alice)

        for i in range(15):
            Task.objects.create(
                project=project_with_team,
                title=f"Benchmark Task {i}",
                status=Task.Status.TODO if i % 2 == 0 else Task.Status.DONE,
                priority=Task.Priority.HIGH,
                created_by=user_alice,
            )

        # Project stats endpoint:
        # 1 query for project check + 1 aggregate query + 1 values/annotate assignee breakdown query = 3 queries
        with django_assert_num_queries(3):
            res = api_client.get(f"/api/projects/{project_with_team.id}/stats/")
            assert res.status_code == 200
            assert res.data["metrics"]["total"] >= 15

    def test_dashboard_stats_constant_queries(self, api_client, user_alice, django_assert_num_queries):
        api_client.force_authenticate(user=user_alice)

        # Dashboard stats uses exactly 4 aggregate/sliced queries regardless of project and task volume
        with django_assert_num_queries(4):
            res = api_client.get("/api/projects/dashboard-stats/")
            assert res.status_code == 200
            assert "metrics" in res.data
            assert "status_distribution" in res.data

