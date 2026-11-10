"""Firestore-backed persistence for documents/{documentId}."""
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.firebase.admin import get_firestore
from app.utils.content import prosemirror_to_text
from app.utils.exceptions import ConflictError

from app.models.document import EMPTY_DOCUMENT_CONTENT, DocumentModel
from app.repositories.base import documents_collection, utcnow, versions_collection

# Automatic checkpoints are created at most once per interval of editing time.
# The first changed save after a checkpoint (or after restore, which resets the
# timer to None) preserves the pre-edit document as an ``autosave`` version.
CHECKPOINT_INTERVAL = timedelta(minutes=5)


def _checkpoint_due(last_checkpoint: datetime | None, now: datetime) -> bool:
    """Return True when an automatic checkpoint should be created.

    A checkpoint is due when there is no previous checkpoint, when the interval
    has elapsed, or when the recorded checkpoint is in the future (clock moved
    backwards), which would otherwise disable checkpoints indefinitely.
    """
    if last_checkpoint is None:
        return True
    if last_checkpoint.tzinfo is None:
        last_checkpoint = last_checkpoint.replace(tzinfo=timezone.utc)
    return last_checkpoint > now or now - last_checkpoint >= CHECKPOINT_INTERVAL


def _checkpoint_payload(document: DocumentModel, actor_id: str, created_at: datetime) -> dict[str, Any]:
    """Build the Firestore payload for an automatic ``autosave`` version.

    The payload captures the *pre-edit* document state so the user can recover
    what the document looked like before the change that triggered the checkpoint.
    """
    return {
        "documentId": document.id,
        "ownerId": document.owner_id,
        "title": document.title,
        "content": document.content,
        "wordCount": document.word_count,
        "label": "Automatic checkpoint",
        "createdAt": created_at,
        "createdBy": actor_id,
        "authorName": None,
        "source": "autosave",
        "documentRevision": document.revision,
        "restoredFromVersionId": None,
    }


def _to_model(doc_id: str, data: dict[str, Any]) -> DocumentModel:
    return DocumentModel(
        id=doc_id,
        owner_id=data.get("ownerId", ""),
        title=data.get("title") or "Untitled Document",
        content=data.get("content") or dict(EMPTY_DOCUMENT_CONTENT),
        word_count=data.get("wordCount", 0),
        revision=data.get("revision", 0),
        updated_by=data.get("updatedBy"),
        created_at=data.get("createdAt"),
        updated_at=data.get("updatedAt"),
        last_checkpoint_at=data.get("lastCheckpointAt"),
    )


class DocumentRepository:
    def create(self, owner_id: str, title: str) -> DocumentModel:
        now = utcnow()
        payload = {
            "ownerId": owner_id,
            "title": title or "Untitled Document",
            "content": dict(EMPTY_DOCUMENT_CONTENT),
            "wordCount": 0,
            "revision": 0,
            "updatedBy": owner_id,
            "createdAt": now,
            "updatedAt": now,
        }
        doc_ref = documents_collection().document()
        doc_ref.set(payload)
        return _to_model(doc_ref.id, payload)

    def get(self, document_id: str) -> DocumentModel | None:
        snap = documents_collection().document(document_id).get()
        if not snap.exists:
            return None
        return _to_model(snap.id, snap.to_dict() or {})

    def list_by_owner(self, owner_id: str) -> list[DocumentModel]:
        query = documents_collection().where(filter=FieldFilter("ownerId", "==", owner_id))
        models = [_to_model(snap.id, snap.to_dict() or {}) for snap in query.stream()]
        models.sort(key=lambda doc: doc.updated_at or utcnow(), reverse=True)
        return models

    def update(
        self,
        document_id: str,
        actor_id: str,
        base_revision: int,
        title: str | None = None,
        content: dict[str, Any] | None = None,
        word_count: int | None = None,
    ) -> DocumentModel | None:
        doc_ref = documents_collection().document(document_id)

        @firestore.transactional
        def save(transaction):
            snap = doc_ref.get(transaction=transaction)
            if not snap.exists:
                return None
            data = snap.to_dict() or {}
            revision = data.get("revision", 0)
            if revision != base_revision:
                raise ConflictError("This document changed elsewhere. Your local draft has not been saved.")
            # Detect no-op saves so unchanged autosaves do not advance the
            # revision or create spurious history entries.
            title_changed = title is not None and title != data.get("title")
            content_changed = content is not None and content != data.get("content")
            if not title_changed and not content_changed:
                return _to_model(document_id, data)
            now = utcnow()
            pre_edit = _to_model(document_id, data)
            updates: dict[str, Any] = {
                "updatedAt": now, "revision": revision + 1, "updatedBy": actor_id,
            }
            if title is not None:
                updates["title"] = title
            if content is not None:
                updates["content"] = content
                updates["wordCount"] = len(prosemirror_to_text(content).split())
            # Preserve the pre-edit document as an automatic checkpoint when one
            # is due. The checkpoint is written before the document update so a
            # failed checkpoint write prevents the update and cannot leave an
            # orphaned history entry pointing at a revision that never existed.
            last_checkpoint = data.get("lastCheckpointAt")
            if isinstance(last_checkpoint, datetime) and last_checkpoint.tzinfo is None:
                last_checkpoint = last_checkpoint.replace(tzinfo=timezone.utc)
            if _checkpoint_due(last_checkpoint, now):
                checkpoint_ref = versions_collection().document()
                transaction.set(checkpoint_ref, _checkpoint_payload(pre_edit, actor_id, now))
                updates["lastCheckpointAt"] = now
            transaction.update(doc_ref, updates)
            return _to_model(document_id, {**data, **updates})

        return save(get_firestore().transaction())

    def delete(self, document_id: str) -> None:
        documents_collection().document(document_id).delete()


document_repository = DocumentRepository()
