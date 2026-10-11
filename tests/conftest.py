import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from projects.models import Project, ProjectMembership


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_alice(db):
    user = User.objects.create_user(
        username="alice",
        email="alice@devtask.test",
        password="TestPassword123!",
        first_name="Alice",
        last_name="Owner",
    )
    user.profile.display_name = "Alice Developer"
    user.profile.save()
    return user


@pytest.fixture
def user_bob(db):
    user = User.objects.create_user(
        username="bob",
        email="bob@devtask.test",
        password="TestPassword123!",
        first_name="Bob",
        last_name="Manager",
    )
    user.profile.display_name = "Bob Manager"
    user.profile.save()
    return user


@pytest.fixture
def user_charlie(db):
    user = User.objects.create_user(
        username="charlie",
        email="charlie@devtask.test",
        password="TestPassword123!",
        first_name="Charlie",
        last_name="Member",
    )
    user.profile.display_name = "Charlie Member"
    user.profile.save()
    return user


@pytest.fixture
def user_stranger(db):
    """User who has no membership in Alice's project (for IDOR tests)."""
    user = User.objects.create_user(
        username="stranger",
        email="stranger@devtask.test",
        password="TestPassword123!",
    )
    return user


@pytest.fixture
def project_with_team(db, user_alice, user_bob, user_charlie):
    project = Project.objects.create(
        name="Apollo Mission",
        description="Core lunar navigation system.",
        owner=user_alice,
    )
    # Alice is OWNER
    ProjectMembership.objects.create(
        project=project,
        user=user_alice,
        role=ProjectMembership.Role.OWNER,
    )
    # Bob is MANAGER
    ProjectMembership.objects.create(
        project=project,
        user=user_bob,
        role=ProjectMembership.Role.MANAGER,
    )
    # Charlie is MEMBER
    ProjectMembership.objects.create(
        project=project,
        user=user_charlie,
        role=ProjectMembership.Role.MEMBER,
    )
    return project
