from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest

from app.models.document import DocumentModel
from app.repositories.version_repository import VersionRepository
from app.utils.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture()
def restore_store():
    current = {"ownerId": "owner", "title": "Current", "content": {"type": "doc", "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "Keep this latest draft"}]}]},
        "wordCount": 4, "revision": 5}
    previous = {"ownerId": "owner", "documentId": "doc", "title": "Older", "label": "First draft",
        "content": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Earlier text"}]}]},
        "wordCount": 999}
    document_ref = MagicMock()
    document_snapshot = MagicMock(exists=True)
    document_snapshot.to_dict.side_effect = lambda: deepcopy(current)
    document_ref.get.return_value = document_snapshot
    version_ref = MagicMock()
    version_snapshot = MagicMock(exists=True)
    version_snapshot.to_dict.side_effect = lambda: deepcopy(previous)
    version_ref.get.return_value = version_snapshot
    transaction = MagicMock()
    with patch("app.repositories.version_repository.documents_collection", create=True) as documents, patch(
        "app.repositories.version_repository.versions_collection"
    ) as versions, patch("app.repositories.version_repository.get_firestore", create=True) as db, patch(
        "google.cloud.firestore.transactional", side_effect=lambda callback: callback
    ):
        documents.return_value.document.return_value = document_ref
        versions.return_value.document.side_effect = lambda identifier=None: version_ref if identifier else MagicMock()
        db.return_value.transaction.return_value = transaction
        yield current, previous, document_ref, version_ref, transaction


def test_restore_preserves_current_and_records_restored_snapshot_atomically(restore_store):
    current, previous, document_ref, version_ref, transaction = restore_store
    restored = VersionRepository().restore("doc", "version", "owner", 5, "Owner")
    assert restored.title == "Older"
    assert restored.content == previous["content"]
    assert restored.revision == 6
    assert restored.word_count == 2
    assert restored.updated_by == "owner"
    document_ref.get.assert_called_once_with(transaction=transaction)
    version_ref.get.assert_called_once_with(transaction=transaction)
    document_ref.update.assert_not_called()
    transaction.update.assert_called_once()
    assert transaction.set.call_count == 2
    snapshots = [call.args[1] for call in transaction.set.call_args_list]
    before = next(item for item in snapshots if item["source"] == "before_restore")
    after = next(item for item in snapshots if item["source"] == "restore")
    assert before["content"] == current["content"]
    assert before["title"] == "Current"
    assert before["documentRevision"] == 5
    assert after["content"] == previous["content"]
    assert after["documentRevision"] == 6
    assert after["restoredFromVersionId"] == "version"
    assert after["createdBy"] == "owner"
    assert after["authorName"] == "Owner"


def test_editor_actor_can_restore_shared_document(restore_store):
    current, previous, _, _, transaction = restore_store
    restored = VersionRepository().restore("doc", "version", "editor-uid", 5, "Editor")
    assert restored.title == "Older"
    assert restored.revision == 6
    assert restored.updated_by == "editor-uid"
    assert transaction.update.call_count == 1
    snapshots = [call.args[1] for call in transaction.set.call_args_list]
    assert all(s["createdBy"] == "editor-uid" for s in snapshots)


@pytest.mark.parametrize("case,error", [("stale", ConflictError),
    ("other_document", PermissionDeniedError),
    ("invalid_content", ValidationFailedError), ("missing_document", NotFoundError), ("missing_version", NotFoundError)])
def test_rejected_restore_does_not_write_anything(restore_store, case, error):
    current, previous, document_ref, version_ref, transaction = restore_store
    if case == "stale":
        current["revision"] = 6
    elif case == "other_document":
        previous["documentId"] = "someone-elses-document"
    elif case == "invalid_content":
        previous["content"] = {"type": "doc", "content": ["invalid"]}
    elif case == "missing_document":
        document_ref.get.return_value.exists = False
    else:
        version_ref.get.return_value.exists = False
    with pytest.raises(error):
        VersionRepository().restore("doc", "version", "owner", 5, "Owner")
    transaction.set.assert_not_called()
    transaction.update.assert_not_called()


def test_restore_endpoint_requires_auth(client):
    response = client.post("/documents/doc/versions/version/restore", json={"base_revision": 5})
    assert response.status_code == 401


def test_restore_endpoint_requires_revision(client):
    with patch("app.api.deps.verify_id_token", return_value={"uid": "owner"}):
        response = client.post("/documents/doc/versions/version/restore", json={}, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_restore_endpoint_uses_authenticated_actor(client):
    restored = DocumentModel(id="doc", owner_id="owner", title="Older", revision=6)
    fake_doc = DocumentModel(id="doc", owner_id="owner", title="Current", revision=5)
    with patch("app.api.deps.verify_id_token", return_value={"uid": "owner", "name": "Owner"}), patch(
        "app.api.routers.versions.require_editor", return_value=(fake_doc, "owner")
    ), patch(
        "app.api.routers.versions.version_repository.restore", create=True, return_value=restored
    ) as restore:
        response = client.post("/documents/doc/versions/version/restore", json={"base_revision": 5}, headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()["revision"] == 6
    restore.assert_called_once_with("doc", "version", "owner", 5, "Owner")
