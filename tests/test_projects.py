import pytest

from projects.models import Project, ProjectMembership


@pytest.mark.django_db
class TestProjectsAndPermissions:
    def test_project_creation_auto_creates_owner_membership(self, api_client, user_alice):
        api_client.force_authenticate(user=user_alice)
        res = api_client.post(
            "/api/projects/",
            {"name": "Project Artemis", "description": "Deep space propulsion"},
            format="json",
        )
        assert res.status_code == 201
        project_id = res.data["id"]
        project = Project.objects.get(pk=project_id)
        assert project.owner == user_alice
        membership = ProjectMembership.objects.filter(project=project, user=user_alice).first()
        assert membership is not None
        assert membership.role == ProjectMembership.Role.OWNER

    def test_membership_uniqueness(self, project_with_team, user_charlie):
        # Charlie is already a member
        with pytest.raises(Exception):
            ProjectMembership.objects.create(
                project=project_with_team,
                user=user_charlie,
                role=ProjectMembership.Role.MEMBER,
            )

    def test_idor_protection_stranger_cannot_access_project(self, api_client, project_with_team, user_stranger):
        api_client.force_authenticate(user=user_stranger)
        # Stranger tries to access project details
        res = api_client.get(f"/api/projects/{project_with_team.id}/")
        assert res.status_code == 403

        # Stranger tries to update project details
        patch_res = api_client.patch(
            f"/api/projects/{project_with_team.id}/",
            {"name": "Hacked Name"},
            format="json",
        )
        assert patch_res.status_code == 403

        # Project name unchanged
        project_with_team.refresh_from_db()
        assert project_with_team.name == "Apollo Mission"

    def test_member_role_cannot_update_project_details(self, api_client, project_with_team, user_charlie):
        api_client.force_authenticate(user=user_charlie)  # Charlie is MEMBER
        res = api_client.patch(
            f"/api/projects/{project_with_team.id}/",
            {"name": "Unauthorized Renaming"},
            format="json",
        )
        assert res.status_code == 403

    def test_manager_can_update_project_details(self, api_client, project_with_team, user_bob):
        api_client.force_authenticate(user=user_bob)  # Bob is MANAGER
        res = api_client.patch(
            f"/api/projects/{project_with_team.id}/",
            {"name": "Apollo Mission V2"},
            format="json",
        )
        assert res.status_code == 200
        project_with_team.refresh_from_db()
        assert project_with_team.name == "Apollo Mission V2"

    def test_add_team_member(self, api_client, project_with_team, user_alice, user_stranger):
        api_client.force_authenticate(user=user_alice)
        res = api_client.post(
            f"/api/projects/{project_with_team.id}/members/",
            {"username_or_email": user_stranger.username, "role": "MEMBER"},
            format="json",
        )
        assert res.status_code == 201
        assert ProjectMembership.objects.filter(project=project_with_team, user=user_stranger).exists()

    def test_member_cannot_add_team_members(self, api_client, project_with_team, user_charlie, user_stranger):
        api_client.force_authenticate(user=user_charlie)  # Charlie is MEMBER
        res = api_client.post(
            f"/api/projects/{project_with_team.id}/members/",
            {"username_or_email": user_stranger.username, "role": "MEMBER"},
            format="json",
        )
        assert res.status_code == 403

    def test_cannot_remove_project_owner(self, api_client, project_with_team, user_alice):
        api_client.force_authenticate(user=user_alice)
        owner_membership = ProjectMembership.objects.get(project=project_with_team, user=user_alice)
        res = api_client.delete(f"/api/projects/{project_with_team.id}/members/{owner_membership.id}/")
        assert res.status_code == 400

    def test_archive_and_unarchive_project_owner_only(self, api_client, project_with_team, user_alice, user_bob):
        # Bob (Manager) tries to archive
        api_client.force_authenticate(user=user_bob)
        res_bob = api_client.post(
            f"/api/projects/{project_with_team.id}/archive/",
            {"action": "archive"},
            format="json",
        )
        assert res_bob.status_code == 403

        # Alice (Owner) archives
        api_client.force_authenticate(user=user_alice)
        res_alice = api_client.post(
            f"/api/projects/{project_with_team.id}/archive/",
            {"action": "archive"},
            format="json",
        )
        assert res_alice.status_code == 200
        project_with_team.refresh_from_db()
        assert project_with_team.is_archived is True

        # Alice unarchives
        res_unarchive = api_client.post(
            f"/api/projects/{project_with_team.id}/archive/",
            {"action": "unarchive"},
            format="json",
        )
        assert res_unarchive.status_code == 200
        project_with_team.refresh_from_db()
        assert project_with_team.is_archived is False

    def test_transfer_ownership(self, api_client, project_with_team, user_alice, user_bob):
        api_client.force_authenticate(user=user_alice)
        res = api_client.post(
            f"/api/projects/{project_with_team.id}/transfer-ownership/",
            {"new_owner_id": user_bob.id},
            format="json",
        )
        assert res.status_code == 200
        project_with_team.refresh_from_db()
        assert project_with_team.owner == user_bob

        bob_membership = ProjectMembership.objects.get(project=project_with_team, user=user_bob)
        alice_membership = ProjectMembership.objects.get(project=project_with_team, user=user_alice)
        assert bob_membership.role == ProjectMembership.Role.OWNER
        assert alice_membership.role == ProjectMembership.Role.MANAGER

    def test_member_detail_oracle_prevention_for_stranger(
        self, api_client, project_with_team, user_stranger, user_charlie
    ):
        api_client.force_authenticate(user=user_stranger)
        charlie_membership = ProjectMembership.objects.get(project=project_with_team, user=user_charlie)

        # Hitting an existing membership in a private project as an outsider returns 403
        res_existing = api_client.patch(
            f"/api/projects/{project_with_team.id}/members/{charlie_membership.id}/",
            {"role": "MANAGER"},
            format="json",
        )
        assert res_existing.status_code == 403

        # Hitting a non-existing membership as an outsider ALSO returns 403 (eliminates oracle)
        res_nonexistent = api_client.patch(
            f"/api/projects/{project_with_team.id}/members/999999/",
            {"role": "MANAGER"},
            format="json",
        )
        assert res_nonexistent.status_code == 403

        # DELETE as an outsider also returns 403 in both cases
        res_del_existing = api_client.delete(
            f"/api/projects/{project_with_team.id}/members/{charlie_membership.id}/"
        )
        assert res_del_existing.status_code == 403

        res_del_nonexistent = api_client.delete(
            f"/api/projects/{project_with_team.id}/members/999999/"
        )
        assert res_del_nonexistent.status_code == 403

    def test_project_patch_mass_assignment_protection(self, api_client, project_with_team, user_alice, user_bob):
        api_client.force_authenticate(user=user_alice)
        original_id = project_with_team.id
        original_owner = project_with_team.owner

        res = api_client.patch(
            f"/api/projects/{project_with_team.id}/",
            {
                "name": "Updated Apollo Project",
                "owner": user_bob.id,
                "id": "00000000-0000-0000-0000-000000000000",
                "archived_at": "2026-01-01T00:00:00Z",
            },
            format="json",
        )
        assert res.status_code == 200
        project_with_team.refresh_from_db()
        assert project_with_team.name == "Updated Apollo Project"
        # Protected fields cannot be modified via mass assignment
        assert project_with_team.id == original_id
        assert project_with_team.owner == original_owner
        assert project_with_team.is_archived is False

    def test_project_archive_invalid_action_rejected(self, api_client, project_with_team, user_alice):
        api_client.force_authenticate(user=user_alice)
        res = api_client.post(
            f"/api/projects/{project_with_team.id}/archive/",
            {"action": "delete_all"},
            format="json",
        )
        assert res.status_code == 400

    def test_cannot_add_inactive_user_to_project(self, api_client, project_with_team, user_bob):
        from django.contrib.auth.models import User

        User.objects.create_user(
            username="deactivated_user",
            email="deactivated@devtask.test",
            password="TestPassword123!",
            is_active=False,
        )

        api_client.force_authenticate(user=user_bob)
        res = api_client.post(
            f"/api/projects/{project_with_team.id}/members/",
            {"username_or_email": "deactivated_user", "role": "MEMBER"},
            format="json",
        )
        assert res.status_code == 400

    def test_cannot_transfer_ownership_to_inactive_user(self, api_client, project_with_team, user_alice, user_bob):
        user_bob.is_active = False
        user_bob.save()

        api_client.force_authenticate(user=user_alice)
        res = api_client.post(
            f"/api/projects/{project_with_team.id}/transfer-ownership/",
            {"new_owner_id": user_bob.id},
            format="json",
        )
        assert res.status_code == 400

    def test_cannot_update_archived_project(self, api_client, project_with_team, user_alice):
        api_client.force_authenticate(user=user_alice)
        # Archive project first
        api_client.post(
            f"/api/projects/{project_with_team.id}/archive/",
            {"action": "archive"},
            format="json",
        )

        # Attempt to patch details
        res = api_client.patch(
            f"/api/projects/{project_with_team.id}/",
            {"name": "Attempted Name Change"},
            format="json",
        )
        assert res.status_code == 400

