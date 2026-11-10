from unittest.mock import patch

from app.models.document import EMPTY_DOCUMENT_CONTENT, DocumentModel

FAKE_DECODED_TOKEN = {"uid": "owner-uid", "email": "owner@example.com", "name": "Owner"}
AUTH_HEADERS = {"Authorization": "Bearer good-token"}


def _make_document(**overrides) -> DocumentModel:
    defaults = dict(
        id="doc-1",
        owner_id="owner-uid",
        title="Untitled Document",
        content=dict(EMPTY_DOCUMENT_CONTENT),
        word_count=0,
        created_at=None,
        updated_at=None,
    )
    defaults.update(overrides)
    return DocumentModel(**defaults)


def test_create_document_requires_auth(client):
    response = client.post("/documents", json={"title": "My Doc"})
    assert response.status_code == 401


def test_create_document_success(client):
    fake_doc = _make_document(title="My Doc")
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.documents.document_repository.create", return_value=fake_doc
    ):
        response = client.post("/documents", json={"title": "My Doc"}, headers=AUTH_HEADERS)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "doc-1"
    assert body["title"] == "My Doc"
    assert body["content"] == EMPTY_DOCUMENT_CONTENT


def test_list_documents_success(client):
    docs = [_make_document(id="doc-1"), _make_document(id="doc-2", title="Second")]
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo:
        doc_repo.list_by_owner.return_value = docs
        collab_repo.list_by_user.return_value = []
        response = client.get("/documents", headers=AUTH_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert "content" not in body[0]


def test_get_document_not_found(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.documents.document_repository.get", return_value=None
    ):
        response = client.get("/documents/missing-doc", headers=AUTH_HEADERS)

    assert response.status_code == 404


def test_get_document_forbidden_for_non_owner(client):
    other_users_doc = _make_document(owner_id="someone-else")
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = other_users_doc
        collab_repo.find.return_value = None
        response = client.get("/documents/doc-1", headers=AUTH_HEADERS)

    assert response.status_code == 403


def test_get_document_success(client):
    fake_doc = _make_document()
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo:
        doc_repo.get.return_value = fake_doc
        response = client.get("/documents/doc-1", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json()["id"] == "doc-1"


def test_update_document_success(client):
    fake_doc = _make_document()
    updated_doc = _make_document(title="Renamed", word_count=42)
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.api.routers.documents.document_repository"
    ) as router_doc_repo:
        doc_repo.get.return_value = fake_doc
        router_doc_repo.update.return_value = updated_doc
        response = client.patch(
            "/documents/doc-1",
            json={"title": "Renamed", "word_count": 42, "base_revision": 0},
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Renamed"
    assert body["word_count"] == 42


def test_update_document_forbidden_for_non_owner(client):
    other_users_doc = _make_document(owner_id="someone-else")
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = other_users_doc
        collab_repo.find.return_value = None
        response = client.patch("/documents/doc-1", json={"title": "Renamed", "base_revision": 0}, headers=AUTH_HEADERS)

    assert response.status_code == 403


def test_delete_document_success(client):
    fake_doc = _make_document()
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.api.routers.documents.document_repository"
    ) as router_doc_repo, patch(
        "app.api.routers.documents.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = fake_doc
        response = client.delete("/documents/doc-1", headers=AUTH_HEADERS)

    assert response.status_code == 204
    router_doc_repo.delete.assert_called_once_with("doc-1")
    collab_repo.delete_all_for_document.assert_called_once_with("doc-1")
