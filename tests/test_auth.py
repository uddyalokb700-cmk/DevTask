import pytest
from django.contrib.auth.models import User


@pytest.mark.django_db
class TestAuthentication:
    def test_valid_registration(self, api_client):
        res = api_client.post(
            "/api/auth/register/",
            {
                "username": "newdev",
                "email": "newdev@example.com",
                "display_name": "New Developer",
                "password": "SecurePassword123!",
                "password_confirm": "SecurePassword123!",
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.data["username"] == "newdev"
        assert res.data["display_name"] == "New Developer"
        assert User.objects.filter(username="newdev").exists()

    def test_registration_password_mismatch(self, api_client):
        res = api_client.post(
            "/api/auth/register/",
            {
                "username": "mismatch_user",
                "email": "mismatch@example.com",
                "password": "SecurePassword123!",
                "password_confirm": "DifferentPassword123!",
            },
            format="json",
        )
        assert res.status_code == 400
        assert "password_confirm" in res.data

    def test_registration_duplicate_username(self, api_client, user_alice):
        res = api_client.post(
            "/api/auth/register/",
            {
                "username": "alice",  # Already exists
                "email": "unique@example.com",
                "password": "SecurePassword123!",
                "password_confirm": "SecurePassword123!",
            },
            format="json",
        )
        assert res.status_code == 400
        assert "username" in res.data

    def test_successful_login(self, api_client, user_alice):
        res = api_client.post(
            "/api/auth/login/",
            {"username": "alice", "password": "TestPassword123!"},
            format="json",
        )
        assert res.status_code == 200
        assert res.data["username"] == "alice"

    def test_failed_login_invalid_password(self, api_client, user_alice):
        res = api_client.post(
            "/api/auth/login/",
            {"username": "alice", "password": "WrongPassword!"},
            format="json",
        )
        assert res.status_code == 401
        assert "Invalid username or password" in res.data["detail"]

    def test_logout(self, api_client, user_alice):
        api_client.force_authenticate(user=user_alice)
        res = api_client.post("/api/auth/logout/")
        assert res.status_code == 200

    def test_anonymous_access_restriction(self, api_client):
        res = api_client.get("/api/projects/")
        assert res.status_code == 403

    def test_get_current_user_profile(self, api_client, user_alice):
        api_client.force_authenticate(user=user_alice)
        res = api_client.get("/api/auth/me/")
        assert res.status_code == 200
        assert res.data["username"] == "alice"
        assert res.data["display_name"] == "Alice Developer"

    def test_update_current_user_profile(self, api_client, user_alice):
        api_client.force_authenticate(user=user_alice)
        res = api_client.patch(
            "/api/auth/me/",
            {"display_name": "Alice Senior Architect", "bio": "Focusing on systems design"},
            format="json",
        )
        assert res.status_code == 200
        user_alice.refresh_from_db()
        assert user_alice.profile.display_name == "Alice Senior Architect"
        assert user_alice.profile.bio == "Focusing on systems design"

    def test_logout_view_rejects_get_requests(self, api_client, user_alice):
        api_client.force_authenticate(user=user_alice)
        # GET request to logout must be rejected with 405 to prevent Logout CSRF
        res = api_client.get("/logout/")
        assert res.status_code == 405

        # POST request with proper CSRF/session succeeds
        res_post = api_client.post("/logout/")
        assert res_post.status_code == 302
        assert res_post.url == "/login/"


    def test_update_profile_avatar_color_validation(self, api_client, user_alice):
        api_client.force_authenticate(user=user_alice)
        # Invalid hex code or script injection should be rejected with 400
        res = api_client.patch(
            "/api/auth/me/",
            {"avatar_color": "not-a-color<script>"},
            format="json",
        )
        assert res.status_code == 400
        assert "avatar_color" in res.data

        # Valid 6-character hex succeeds
        res_valid = api_client.patch(
            "/api/auth/me/",
            {"avatar_color": "#10b981"},
            format="json",
        )
        assert res_valid.status_code == 200
        user_alice.refresh_from_db()
        assert user_alice.profile.avatar_color == "#10b981"

