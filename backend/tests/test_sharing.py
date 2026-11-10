from unittest.mock import MagicMock, patch

import pytest

from app.models.collaborator import CollaboratorModel
from app.models.document import DocumentModel, EMPTY_DOCUMENT_CONTENT

FAKE_DECODED_TOKEN = {"uid": "owner-uid", "email": "owner@example.com", "name": "Owner"}
VIEWER_TOKEN = {"uid": "viewer-uid", "email": "viewer@example.com", "name": "Viewer"}
EDITOR_TOKEN = {"uid": "editor-uid", "email": "editor@example.com", "name": "Editor"}
STRANGER_TOKEN = {"uid": "stranger-uid", "email": "stranger@example.com", "name": "Stranger"}
AUTH_HEADERS = {"Authorization": "Bearer good-token"}


def _make_document(**overrides) -> DocumentModel:
    defaults = dict(
        id="doc-1", owner_id="owner-uid", title="Shared Doc", content=dict(EMPTY_DOCUMENT_CONTENT),
        word_count=0, revision=1, created_at=None, updated_at=None,
    )
    defaults.update(overrides)
    return DocumentModel(**defaults)


def _make_collab(**overrides) -> CollaboratorModel:
    defaults = dict(
        id="col-1", document_id="doc-1", user_id="viewer-uid", role="viewer",
        email="viewer@example.com", name="Viewer", created_at=None, created_by="owner-uid",
    )
    defaults.update(overrides)
    return CollaboratorModel(**defaults)


# --- list_collaborators ---

def test_list_collaborators_requires_auth(client):
    assert client.get("/documents/doc-1/collaborators").status_code == 401


def test_list_collaborators_requires_owner(client):
    doc = _make_document()
    with patch("app.api.deps.verify_id_token", return_value=VIEWER_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = doc
        collab_repo.find.return_value = _make_collab(user_id="viewer-uid", role="viewer")
        response = client.get("/documents/doc-1/collaborators", headers=AUTH_HEADERS)
    assert response.status_code == 403


def test_list_collaborators_success(client):
    doc = _make_document()
    collabs = [_make_collab(id="c1", role="editor"), _make_collab(id="c2", role="viewer")]
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.api.routers.sharing.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = doc
        collab_repo.list_by_document.return_value = collabs
        response = client.get("/documents/doc-1/collaborators", headers=AUTH_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["role"] == "editor"


# --- invite_collaborator ---

def test_invite_collaborator_requires_owner(client):
    doc = _make_document()
    with patch("app.api.deps.verify_id_token", return_value=VIEWER_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = doc
        collab_repo.find.return_value = _make_collab(user_id="viewer-uid", role="viewer")
        response = client.post(
            "/documents/doc-1/collaborators",
            json={"email": "new@example.com", "role": "editor"}, headers=AUTH_HEADERS,
        )
    assert response.status_code == 403


def test_invite_collaborator_success(client):
    doc = _make_document()
    new_collab = _make_collab(id="new-col", user_id="new-uid", role="editor", email="new@example.com")
    user_snap = MagicMock()
    user_snap.id = "new-uid"
    user_snap.to_dict.return_value = {"name": "New User"}
    user_query = MagicMock()
    user_query.limit.return_value.stream.return_value = iter([user_snap])
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.api.routers.sharing.collaborator_repository"
    ) as collab_repo, patch(
        "app.api.routers.sharing.users_collection"
    ) as users_col:
        doc_repo.get.return_value = doc
        collab_repo.find.return_value = None
        collab_repo.upsert.return_value = new_collab
        users_col.return_value.where.return_value = user_query
        response = client.post(
            "/documents/doc-1/collaborators",
            json={"email": "new@example.com", "role": "editor"}, headers=AUTH_HEADERS,
        )
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "editor"
    assert body["email"] == "new@example.com"
    collab_repo.upsert.assert_called_once()


def test_invite_collaborator_rejects_self_share(client):
    doc = _make_document()
    user_snap = MagicMock()
    user_snap.id = "owner-uid"
    user_snap.to_dict.return_value = {"name": "Owner"}
    user_query = MagicMock()
    user_query.limit.return_value.stream.return_value = iter([user_snap])
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.api.routers.sharing.users_collection"
    ) as users_col:
        doc_repo.get.return_value = doc
        users_col.return_value.where.return_value = user_query
        response = client.post(
            "/documents/doc-1/collaborators",
            json={"email": "owner@example.com", "role": "editor"}, headers=AUTH_HEADERS,
        )
    assert response.status_code == 403


def test_invite_collaborator_rejects_unknown_user(client):
    doc = _make_document()
    user_query = MagicMock()
    user_query.limit.return_value.stream.return_value = iter([])
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.api.routers.sharing.users_collection"
    ) as users_col:
        doc_repo.get.return_value = doc
        users_col.return_value.where.return_value = user_query
        response = client.post(
            "/documents/doc-1/collaborators",
            json={"email": "unknown@example.com", "role": "editor"}, headers=AUTH_HEADERS,
        )
    assert response.status_code == 404


def test_invite_collaborator_rejects_invalid_email(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        response = client.post(
            "/documents/doc-1/collaborators",
            json={"email": "not-an-email", "role": "editor"}, headers=AUTH_HEADERS,
        )
    assert response.status_code == 422


def test_invite_collaborator_rejects_owner_role(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        response = client.post(
            "/documents/doc-1/collaborators",
            json={"email": "new@example.com", "role": "owner"}, headers=AUTH_HEADERS,
        )
    assert response.status_code == 422


# --- remove_collaborator ---

def test_remove_collaborator_requires_owner(client):
    doc = _make_document()
    with patch("app.api.deps.verify_id_token", return_value=VIEWER_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = doc
        collab_repo.find.return_value = _make_collab(user_id="viewer-uid", role="viewer")
        response = client.delete("/documents/doc-1/collaborators/col-1", headers=AUTH_HEADERS)
    assert response.status_code == 403


def test_remove_collaborator_success(client):
    doc = _make_document()
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.api.routers.sharing.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = doc
        response = client.delete("/documents/doc-1/collaborators/col-1", headers=AUTH_HEADERS)
    assert response.status_code == 204
    collab_repo.delete.assert_called_once_with("col-1")


# --- role-based document access ---

def test_viewer_can_read_but_not_edit(client):
    doc = _make_document()
    with patch("app.api.deps.verify_id_token", return_value=VIEWER_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = doc
        collab_repo.find.return_value = _make_collab(user_id="viewer-uid", role="viewer")
        # GET should succeed
        get_response = client.get("/documents/doc-1", headers=AUTH_HEADERS)
        assert get_response.status_code == 200
        # PATCH should fail
        patch_response = client.patch(
            "/documents/doc-1", json={"title": "New", "base_revision": 1}, headers=AUTH_HEADERS
        )
        assert patch_response.status_code == 403


def test_editor_can_read_and_edit(client):
    doc = _make_document()
    updated = _make_document(title="New Title", revision=2)
    with patch("app.api.deps.verify_id_token", return_value=EDITOR_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo, patch(
        "app.api.routers.documents.document_repository"
    ) as router_doc_repo:
        doc_repo.get.return_value = doc
        router_doc_repo.update.return_value = updated
        collab_repo.find.return_value = _make_collab(user_id="editor-uid", role="editor")
        # GET should succeed
        get_response = client.get("/documents/doc-1", headers=AUTH_HEADERS)
        assert get_response.status_code == 200
        # PATCH should succeed
        patch_response = client.patch(
            "/documents/doc-1", json={"title": "New Title", "base_revision": 1}, headers=AUTH_HEADERS
        )
        assert patch_response.status_code == 200


def test_editor_cannot_delete(client):
    doc = _make_document()
    with patch("app.api.deps.verify_id_token", return_value=EDITOR_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = doc
        collab_repo.find.return_value = _make_collab(user_id="editor-uid", role="editor")
        response = client.delete("/documents/doc-1", headers=AUTH_HEADERS)
    assert response.status_code == 403


def test_stranger_cannot_access_document(client):
    doc = _make_document()
    with patch("app.api.deps.verify_id_token", return_value=STRANGER_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = doc
        collab_repo.find.return_value = None
        response = client.get("/documents/doc-1", headers=AUTH_HEADERS)
    assert response.status_code == 403


def test_list_documents_includes_shared(client):
    owned = _make_document(id="doc-owned", title="Owned")
    shared = _make_document(id="doc-shared", title="Shared", owner_id="other-uid")
    collab = _make_collab(document_id="doc-shared", user_id="owner-uid")
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo:
        doc_repo.list_by_owner.return_value = [owned]
        collab_repo.list_by_user.return_value = [collab]
        doc_repo.get.return_value = shared
        response = client.get("/documents", headers=AUTH_HEADERS)
    assert response.status_code == 200
    titles = {item["title"] for item in response.json()}
    assert {"Owned", "Shared"} <= titles
