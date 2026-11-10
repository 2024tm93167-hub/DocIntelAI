"""ACL tests for versions and suggestions routers.

Verifies that viewers can read but not write, editors can write but not delete
versions, and strangers are denied all access.
"""
from unittest.mock import patch

from app.models.document import DocumentModel, EMPTY_DOCUMENT_CONTENT
from app.models.version import VersionModel
from app.models.suggestion import SuggestionModel

OWNER_TOKEN = {"uid": "owner-uid", "email": "owner@example.com", "name": "Owner"}
VIEWER_TOKEN = {"uid": "viewer-uid", "email": "viewer@example.com", "name": "Viewer"}
EDITOR_TOKEN = {"uid": "editor-uid", "email": "editor@example.com", "name": "Editor"}
STRANGER_TOKEN = {"uid": "stranger-uid", "email": "stranger@example.com", "name": "Stranger"}
AUTH_HEADERS = {"Authorization": "Bearer good-token"}


def _make_document(**overrides) -> DocumentModel:
    defaults = dict(
        id="doc-1", owner_id="owner-uid", title="Doc", content=dict(EMPTY_DOCUMENT_CONTENT),
        word_count=0, revision=1, created_at=None, updated_at=None,
    )
    defaults.update(overrides)
    return DocumentModel(**defaults)


def _make_version(**overrides) -> VersionModel:
    defaults = dict(
        id="ver-1", document_id="doc-1", owner_id="owner-uid", title="Doc",
        content=dict(EMPTY_DOCUMENT_CONTENT), word_count=0, label=None, created_at=None,
    )
    defaults.update(overrides)
    return VersionModel(**defaults)


def _make_suggestion(**overrides) -> SuggestionModel:
    defaults = dict(
        id="sug-1", document_id="doc-1", user_id="owner-uid", type="grammar",
        original_text="hello", suggested_text="Hello", reason="Capitalize",
        status="pending", document_revision=1, created_at=None,
    )
    defaults.update(overrides)
    return SuggestionModel(**defaults)


# --- Versions: viewer can read ---

def test_viewer_can_list_versions(client):
    with patch("app.api.deps.verify_id_token", return_value=VIEWER_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo, patch(
        "app.api.routers.versions.version_repository.list_by_document", return_value=[]
    ):
        doc_repo.get.return_value = _make_document()
        collab_repo.find.return_value = None  # not owner
        from app.models.collaborator import CollaboratorModel
        collab = CollaboratorModel(id="c1", document_id="doc-1", user_id="viewer-uid", role="viewer")
        collab_repo.find.return_value = collab
        response = client.get("/documents/doc-1/versions", headers=AUTH_HEADERS)
    assert response.status_code == 200


def test_viewer_can_diff_versions(client):
    fake_version = _make_version()
    with patch("app.api.deps.verify_id_token", return_value=VIEWER_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo, patch(
        "app.api.routers.versions.version_repository.get", return_value=fake_version
    ):
        doc_repo.get.return_value = _make_document()
        from app.models.collaborator import CollaboratorModel
        collab = CollaboratorModel(id="c1", document_id="doc-1", user_id="viewer-uid", role="viewer")
        collab_repo.find.return_value = collab
        response = client.get("/documents/doc-1/versions/ver-1/diff", headers=AUTH_HEADERS)
    assert response.status_code == 200


# --- Versions: viewer cannot create/restore/delete ---

def test_viewer_cannot_create_version(client):
    with patch("app.api.deps.verify_id_token", return_value=VIEWER_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = _make_document()
        from app.models.collaborator import CollaboratorModel
        collab = CollaboratorModel(id="c1", document_id="doc-1", user_id="viewer-uid", role="viewer")
        collab_repo.find.return_value = collab
        response = client.post("/documents/doc-1/versions", json={"label": "v1"}, headers=AUTH_HEADERS)
    assert response.status_code == 403


def test_viewer_cannot_restore_version(client):
    with patch("app.api.deps.verify_id_token", return_value=VIEWER_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = _make_document()
        from app.models.collaborator import CollaboratorModel
        collab = CollaboratorModel(id="c1", document_id="doc-1", user_id="viewer-uid", role="viewer")
        collab_repo.find.return_value = collab
        response = client.post(
            "/documents/doc-1/versions/ver-1/restore", json={"base_revision": 1}, headers=AUTH_HEADERS
        )
    assert response.status_code == 403


def test_editor_cannot_delete_version(client):
    with patch("app.api.deps.verify_id_token", return_value=EDITOR_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = _make_document()
        from app.models.collaborator import CollaboratorModel
        collab = CollaboratorModel(id="c1", document_id="doc-1", user_id="editor-uid", role="editor")
        collab_repo.find.return_value = collab
        response = client.delete("/documents/doc-1/versions/ver-1", headers=AUTH_HEADERS)
    assert response.status_code == 403


# --- Versions: stranger denied ---

def test_stranger_cannot_list_versions(client):
    with patch("app.api.deps.verify_id_token", return_value=STRANGER_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = _make_document()
        collab_repo.find.return_value = None
        response = client.get("/documents/doc-1/versions", headers=AUTH_HEADERS)
    assert response.status_code == 403


# --- Suggestions: viewer can list but not create ---

def test_viewer_can_list_suggestions(client):
    with patch("app.api.deps.verify_id_token", return_value=VIEWER_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo, patch(
        "app.api.routers.suggestions.suggestion_repository.list_by_document", return_value=[]
    ):
        doc_repo.get.return_value = _make_document()
        from app.models.collaborator import CollaboratorModel
        collab = CollaboratorModel(id="c1", document_id="doc-1", user_id="viewer-uid", role="viewer")
        collab_repo.find.return_value = collab
        response = client.get("/documents/doc-1/suggestions", headers=AUTH_HEADERS)
    assert response.status_code == 200


def test_viewer_cannot_create_suggestion(client):
    with patch("app.api.deps.verify_id_token", return_value=VIEWER_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = _make_document()
        from app.models.collaborator import CollaboratorModel
        collab = CollaboratorModel(id="c1", document_id="doc-1", user_id="viewer-uid", role="viewer")
        collab_repo.find.return_value = collab
        response = client.post(
            "/documents/doc-1/suggestions",
            json={"type": "grammar", "original_text": "hi", "suggested_text": "Hi"},
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 403


def test_viewer_cannot_accept_suggestion(client):
    with patch("app.api.deps.verify_id_token", return_value=VIEWER_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = _make_document()
        from app.models.collaborator import CollaboratorModel
        collab = CollaboratorModel(id="c1", document_id="doc-1", user_id="viewer-uid", role="viewer")
        collab_repo.find.return_value = collab
        response = client.patch(
            "/documents/doc-1/suggestions/sug-1",
            json={"status": "accepted", "base_revision": 1},
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 403


# --- Suggestions: stranger denied ---

def test_stranger_cannot_list_suggestions(client):
    with patch("app.api.deps.verify_id_token", return_value=STRANGER_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = _make_document()
        collab_repo.find.return_value = None
        response = client.get("/documents/doc-1/suggestions", headers=AUTH_HEADERS)
    assert response.status_code == 403


# --- Editor can create/restore versions ---

def test_editor_can_create_version(client):
    fake_version = _make_version(label="Draft")
    with patch("app.api.deps.verify_id_token", return_value=EDITOR_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo, patch(
        "app.api.routers.versions.version_repository.create", return_value=fake_version
    ):
        doc_repo.get.return_value = _make_document()
        from app.models.collaborator import CollaboratorModel
        collab = CollaboratorModel(id="c1", document_id="doc-1", user_id="editor-uid", role="editor")
        collab_repo.find.return_value = collab
        response = client.post("/documents/doc-1/versions", json={"label": "Draft"}, headers=AUTH_HEADERS)
    assert response.status_code == 201


def test_editor_can_restore_version(client):
    restored = _make_document(title="Restored", revision=2)
    with patch("app.api.deps.verify_id_token", return_value=EDITOR_TOKEN), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo, patch(
        "app.api.routers.versions.version_repository.restore", return_value=restored
    ):
        doc_repo.get.return_value = _make_document()
        from app.models.collaborator import CollaboratorModel
        collab = CollaboratorModel(id="c1", document_id="doc-1", user_id="editor-uid", role="editor")
        collab_repo.find.return_value = collab
        response = client.post(
            "/documents/doc-1/versions/ver-1/restore", json={"base_revision": 1}, headers=AUTH_HEADERS
        )
    assert response.status_code == 200
