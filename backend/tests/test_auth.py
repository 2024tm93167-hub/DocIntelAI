from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from app.firebase.admin import get_firestore, init_firebase
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


def test_live_firestore_is_blocked():
    with pytest.raises(AssertionError, match="Live Firebase access is forbidden"):
        get_firestore()


def test_firebase_initialization_is_thread_safe():
    fake_client = object()
    with patch("app.firebase.admin.init_firebase", init_firebase), patch(
        "app.firebase.admin.credentials.Certificate"
    ), patch("firebase_admin.initialize_app", return_value=object()) as initialize, patch(
        "app.firebase.admin.firestore.client", return_value=fake_client
    ) as create_client:
        with ThreadPoolExecutor(max_workers=8) as pool:
            clients = list(pool.map(lambda _: get_firestore(), range(16)))
    assert all(client is fake_client for client in clients)
    initialize.assert_called_once()
    create_client.assert_called_once()
