from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models.document import DocumentModel
from app.repositories.document_repository import DocumentRepository
from app.utils.exceptions import ConflictError


@pytest.fixture()
def stored_document():
    payload = {"ownerId": "owner", "title": "Original", "content": {"type": "doc", "content": []}, "wordCount": 0}
    ref = MagicMock()
    snapshot = MagicMock(exists=True)
    snapshot.to_dict.side_effect = lambda: dict(payload)
    ref.get.return_value = snapshot
    transaction = MagicMock()
    transaction.update.side_effect = lambda ref, updates: payload.update(updates)
    with patch("app.repositories.document_repository.documents_collection") as collection, patch(
        "app.repositories.document_repository.get_firestore", create=True
    ) as get_db, patch(
        "app.repositories.document_repository.versions_collection", create=True
    ), patch(
        "google.cloud.firestore.transactional", side_effect=lambda callback: callback
    ):
        collection.return_value.document.return_value = ref
        get_db.return_value.transaction.return_value = transaction
        yield payload, ref, transaction


def test_legacy_document_gets_revision_and_actor(stored_document):
    payload, ref, transaction = stored_document
    result = DocumentRepository().update("doc", actor_id="owner", base_revision=0, title="New")
    assert result.revision == 1
    assert result.updated_by == "owner"
    assert payload["revision"] == 1
    ref.get.assert_called_once_with(transaction=transaction)
    transaction.update.assert_called_once()


def test_second_writer_with_same_base_cannot_overwrite(stored_document):
    payload, _, transaction = stored_document
    repo = DocumentRepository()
    repo.update("doc", actor_id="owner", base_revision=0, title="First writer")
    with pytest.raises(ConflictError):
        repo.update("doc", actor_id="owner", base_revision=0, title="Stale writer")
    assert payload["title"] == "First writer"
    assert transaction.update.call_count == 1


def test_editor_actor_can_update_shared_document(stored_document):
    # Role checks live in services/permissions (require_editor); the repository
    # only enforces the optimistic revision guard inside the transaction.
    result = DocumentRepository().update("doc", actor_id="editor-uid", base_revision=0, title="Changed")
    assert result.revision == 1
    assert result.updated_by == "editor-uid"


def test_word_count_is_derived_from_content(stored_document):
    content = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Hello world"}]}]}
    result = DocumentRepository().update("doc", actor_id="owner", base_revision=0, content=content, word_count=999)
    assert result.word_count == 2


def test_patch_requires_revision(client):
    with patch("app.api.deps.verify_id_token", return_value={"uid": "owner"}):
        response = client.patch("/documents/doc", json={"title": "New"}, headers={"Authorization": "Bearer test"})
    assert response.status_code == 422


def test_patch_returns_conflict_without_overwrite(client):
    fake_doc = DocumentModel(id="doc", owner_id="owner", title="Original", content={"type": "doc", "content": []})
    with patch("app.api.deps.verify_id_token", return_value={"uid": "owner"}), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.api.routers.documents.document_repository"
    ) as router_doc_repo:
        doc_repo.get.return_value = fake_doc
        router_doc_repo.update.side_effect = ConflictError("Document changed")
        response = client.patch("/documents/doc", json={"title": "New", "base_revision": 0}, headers={"Authorization": "Bearer test"})
    assert response.status_code == 409


def test_first_changed_save_preserves_pre_edit_document(stored_document):
    payload, _, transaction = stored_document
    now = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)
    with patch("app.repositories.document_repository.utcnow", return_value=now):
        result = DocumentRepository().update("doc", actor_id="owner", base_revision=0, title="Changed")
    transaction.set.assert_called_once()
    checkpoint = transaction.set.call_args.args[1]
    assert checkpoint["title"] == "Original"
    assert checkpoint["documentRevision"] == 0
    assert checkpoint["source"] == "autosave"
    assert checkpoint["createdBy"] == "owner"
    assert checkpoint["createdAt"] == now
    assert result.title == "Changed"
    assert result.last_checkpoint_at == now
    assert payload["lastCheckpointAt"] == now


@pytest.mark.parametrize("seconds,expected", [(0, 0), (299, 0), (300, 1), (600, 1)])
def test_checkpoint_interval_boundary(stored_document, seconds, expected):
    payload, _, transaction = stored_document
    now = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)
    payload["lastCheckpointAt"] = now - timedelta(seconds=seconds)
    with patch("app.repositories.document_repository.utcnow", return_value=now):
        DocumentRepository().update("doc", actor_id="owner", base_revision=0, title="Changed")
    assert transaction.set.call_count == expected
    assert payload["lastCheckpointAt"] == (now if expected else now - timedelta(seconds=seconds))


def test_frequent_saves_do_not_create_one_snapshot_per_save(stored_document):
    _, _, transaction = stored_document
    now = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)
    repo = DocumentRepository()
    for revision in range(10):
        with patch("app.repositories.document_repository.utcnow", return_value=now + timedelta(seconds=revision * 20)):
            repo.update("doc", actor_id="owner", base_revision=revision, title=f"Draft {revision}")
    assert transaction.update.call_count == 10
    assert transaction.set.call_count == 1


def test_unchanged_save_does_not_advance_revision_or_create_history(stored_document):
    payload, _, transaction = stored_document
    result = DocumentRepository().update("doc", actor_id="owner", base_revision=0,
        title=payload["title"], content=payload["content"])
    assert result.revision == 0
    transaction.update.assert_not_called()
    transaction.set.assert_not_called()


def test_checkpoint_failure_prevents_document_update(stored_document):
    payload, _, transaction = stored_document
    transaction.set.side_effect = RuntimeError("Could not queue checkpoint")
    with pytest.raises(RuntimeError, match="Could not queue checkpoint"):
        DocumentRepository().update("doc", actor_id="owner", base_revision=0, title="Changed")
    transaction.update.assert_not_called()
    assert payload["title"] == "Original"


def test_stale_save_cannot_create_checkpoint(stored_document):
    payload, _, transaction = stored_document
    payload["revision"] = 3
    with pytest.raises(ConflictError):
        DocumentRepository().update("doc", actor_id="owner", base_revision=0, title="Changed")
    transaction.set.assert_not_called()
    transaction.update.assert_not_called()


def test_clock_moving_backwards_does_not_disable_checkpoints(stored_document):
    payload, _, transaction = stored_document
    now = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)
    payload["lastCheckpointAt"] = now + timedelta(days=1)
    with patch("app.repositories.document_repository.utcnow", return_value=now):
        DocumentRepository().update("doc", actor_id="owner", base_revision=0, title="Changed")
        DocumentRepository().update("doc", actor_id="owner", base_revision=1, title="Changed again")
    assert transaction.set.call_count == 1


@pytest.mark.parametrize("content", [
    {"type": "paragraph"},
    {"type": "doc", "content": ["invalid"]},
    {"type": "doc", "content": [{"type": "text", "text": 123}]},
    {"type": "doc", "content": [{"type": "paragraph", "attrs": "invalid"}]},
    {"type": "doc", "content": [{"type": "text", "text": "x" * 800000}]},
])
def test_patch_rejects_invalid_or_oversized_content(client, content):
    with patch("app.api.deps.verify_id_token", return_value={"uid": "owner"}):
        response = client.patch("/documents/doc", json={"content": content, "base_revision": 0}, headers={"Authorization": "Bearer test"})
    assert response.status_code == 422
