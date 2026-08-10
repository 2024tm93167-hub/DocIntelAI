from unittest.mock import patch

from app.models.user import UserModel


def test_users_me_requires_authorization_header(client):
    response = client.get("/users/me")
    assert response.status_code == 401


def test_users_me_rejects_malformed_header(client):
    response = client.get("/users/me", headers={"Authorization": "Token abc"})
    assert response.status_code == 401


def test_users_me_rejects_invalid_token(client):
    with patch("app.api.deps.verify_id_token", side_effect=ValueError("bad token")):
        response = client.get("/users/me", headers={"Authorization": "Bearer bad-token"})
    assert response.status_code == 401


def test_users_me_returns_profile_for_valid_token(client):
    fake_decoded = {"uid": "test-uid-123", "email": "test@example.com", "name": "Test User"}
    fake_user = UserModel(
        uid="test-uid-123",
        name="Test User",
        email="test@example.com",
        created_at=None,
        last_login_at=None,
    )

    with patch("app.api.deps.verify_id_token", return_value=fake_decoded), patch(
        "app.api.routers.users.user_repository.get_or_create", return_value=fake_user
    ):
        response = client.get("/users/me", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["uid"] == "test-uid-123"
    assert body["email"] == "test@example.com"
    assert body["name"] == "Test User"
