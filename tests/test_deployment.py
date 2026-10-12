import pytest
from django.test import Client
from rest_framework import status


@pytest.mark.django_db
def test_health_check_endpoint():
    """Verify the /health/ endpoint returns HTTP 200 and healthy database status."""
    client = Client()
    response = client.get("/health/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "healthy"


@pytest.mark.django_db
def test_custom_404_view():
    """Verify custom 404 handler renders the branded error page."""
    client = Client()
    response = client.get("/non-existent-devtask-path/")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert b"Page Not Found" in response.content or b"404" in response.content


@pytest.mark.django_db
def test_production_error_sanitization():
    """Verify API exception handler returns sanitized JSON 500 when DEBUG is False."""
    from rest_framework.request import Request
    from rest_framework.test import APIRequestFactory

    from config.exceptions import custom_exception_handler

    factory = APIRequestFactory()
    django_req = factory.get("/api/tasks/")
    drf_req = Request(django_req)

    # Simulating an unexpected runtime error
    exc = RuntimeError("Database password leaked here: super-secret")
    context = {"request": drf_req, "view": None}

    # Under DEBUG=False
    from django.test import override_settings

    with override_settings(DEBUG=False):
        response = custom_exception_handler(exc, context)
        assert response is not None
        assert response.status_code == 500
        assert "super-secret" not in str(response.data)
        assert response.data["detail"] == "A server error occurred. Please try again later."


@pytest.mark.django_db
def test_end_to_end_core_workflows():
    """End-to-end verification of all core application workflows against the database:
    1. Registration
    2. Login
    3. Project creation
    4. Membership management
    5. Task creation
    6. Task assignment
    7. Status changes & completion timestamp
    8. Comments
    9. Activity history logging
    10. Task filtering
    11. Pagination
    """
    from django.contrib.auth.models import User
    from rest_framework.test import APIClient

    # 1. Registration
    client_a = APIClient()
    reg_a = client_a.post(
        "/api/auth/register/",
        {
            "username": "lead_alice",
            "email": "alice@example.com",
            "password": "Password123!",
            "password_confirm": "Password123!",
            "display_name": "Alice Lead",
        },
        format="json",
    )
    assert reg_a.status_code == status.HTTP_201_CREATED
    assert User.objects.filter(username="lead_alice").exists()

    reg_b = client_a.post(
        "/api/auth/register/",
        {
            "username": "dev_bob",
            "email": "bob@example.com",
            "password": "Password123!",
            "password_confirm": "Password123!",
            "display_name": "Bob Dev",
        },
        format="json",
    )
    assert reg_b.status_code == status.HTTP_201_CREATED
    user_b = User.objects.get(username="dev_bob")

    # 2. Login
    login_a = client_a.post(
        "/api/auth/login/",
        {"username": "lead_alice", "password": "Password123!"},
        format="json",
    )
    assert login_a.status_code == status.HTTP_200_OK

    client_b = APIClient()
    login_b = client_b.post(
        "/api/auth/login/",
        {"username": "dev_bob", "password": "Password123!"},
        format="json",
    )
    assert login_b.status_code == status.HTTP_200_OK

    # 3. Project Creation
    proj_res = client_a.post(
        "/api/projects/",
        {"name": "Mission Alpha", "description": "Critical project"},
        format="json",
    )
    assert proj_res.status_code == status.HTTP_201_CREATED
    project_id = proj_res.data["id"]

    # 4. Membership Management (Alice adds Bob to Mission Alpha)
    add_member_res = client_a.post(
        f"/api/projects/{project_id}/members/",
        {"username_or_email": "dev_bob", "role": "MEMBER"},
        format="json",
    )
    assert add_member_res.status_code == status.HTTP_201_CREATED

    members_res = client_a.get(f"/api/projects/{project_id}/members/")
    assert members_res.status_code == status.HTTP_200_OK
    member_usernames = [m["user"]["username"] for m in members_res.data]
    assert "lead_alice" in member_usernames
    assert "dev_bob" in member_usernames

    # 5. Task Creation
    task_res = client_a.post(
        "/api/tasks/",
        {
            "project_id": project_id,
            "title": "Set up production telemetry",
            "description": "Install Prometheus exporter",
            "priority": "HIGH",
            "status": "TODO",
        },
        format="json",
    )
    assert task_res.status_code == status.HTTP_201_CREATED
    task_id = task_res.data["id"]

    # 6. Assignment (Assign Task to Bob)
    assign_res = client_a.patch(
        f"/api/tasks/{task_id}/",
        {"assignee_id": user_b.id},
        format="json",
    )
    assert assign_res.status_code == status.HTTP_200_OK
    assert assign_res.data["assignee"]["id"] == user_b.id

    # 7. Status Changes (Bob moves task to IN_PROGRESS, then DONE)
    move_progress_res = client_b.patch(
        f"/api/tasks/{task_id}/",
        {"status": "IN_PROGRESS"},
        format="json",
    )
    assert move_progress_res.status_code == status.HTTP_200_OK
    assert move_progress_res.data["status"] == "IN_PROGRESS"
    assert move_progress_res.data["completed_at"] is None

    move_done_res = client_b.patch(
        f"/api/tasks/{task_id}/",
        {"status": "DONE"},
        format="json",
    )
    assert move_done_res.status_code == status.HTTP_200_OK
    assert move_done_res.data["status"] == "DONE"
    assert move_done_res.data["completed_at"] is not None

    # 8. Comments (Bob comments on the task)
    comment_res = client_b.post(
        f"/api/tasks/{task_id}/comments/",
        {"body": "Telemetry set up and running smoothly."},
        format="json",
    )
    assert comment_res.status_code == status.HTTP_201_CREATED

    comments_list = client_a.get(f"/api/tasks/{task_id}/comments/")
    assert comments_list.status_code == status.HTTP_200_OK
    assert len(comments_list.data) == 1
    assert comments_list.data[0]["body"] == "Telemetry set up and running smoothly."

    # 9. Activity History
    activity_res = client_a.get(f"/api/projects/{project_id}/activity/")
    assert activity_res.status_code == status.HTTP_200_OK
    assert activity_res.data["count"] >= 3
    actions = [log["action"] for log in activity_res.data["results"]]
    assert "MEMBER_ADDED" in actions
    assert "TASK_CREATED" in actions
    assert "COMMENT_ADDED" in actions

    # 10. Task Filtering & 11. Pagination
    # Create several tasks to verify filtering and pagination
    for i in range(15):
        client_a.post(
            "/api/tasks/",
            {
                "project_id": project_id,
                "title": f"Batch Task {i}",
                "priority": "LOW" if i % 2 == 0 else "HIGH",
                "status": "TODO",
            },
            format="json",
        )

    # Filter by priority
    filter_res = client_a.get(f"/api/tasks/?project_id={project_id}&priority=HIGH")
    assert filter_res.status_code == status.HTTP_200_OK
    for t in filter_res.data["results"]:
        assert t["priority"] == "HIGH"

    # Pagination test with custom page_size
    paged_res = client_a.get(f"/api/tasks/?project_id={project_id}&page=1&page_size=5")
    assert paged_res.status_code == status.HTTP_200_OK
    assert len(paged_res.data["results"]) == 5
    assert paged_res.data["next"] is not None
    assert paged_res.data["count"] == 16  # 1 initial + 15 batch

