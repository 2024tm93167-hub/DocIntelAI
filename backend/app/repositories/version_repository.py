"""Firestore-backed persistence for document versions."""
from typing import Any

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import ValidationError

from app.firebase.admin import get_firestore
from app.models.document import DocumentModel
from app.models.version import VersionModel
from app.repositories.base import documents_collection, utcnow, versions_collection
from app.repositories.document_repository import _to_model as document_from_snapshot
from app.schemas.document import DocumentUpdate
from app.utils.content import prosemirror_to_text
from app.utils.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError


def _to_model(version_id: str, data: dict[str, Any]) -> VersionModel:
    return VersionModel(
        id=version_id,
        document_id=data.get("documentId", ""),
        owner_id=data.get("ownerId", ""),
        title=data.get("title") or "Untitled Document",
        content=data.get("content") or {"type": "doc", "content": [{"type": "paragraph"}]},
        word_count=data.get("wordCount", 0),
        label=data.get("label"),
        created_at=data.get("createdAt"),
        created_by=data.get("createdBy") or data.get("ownerId"),
        author_name=data.get("authorName"),
        source=data.get("source") or "manual",
        document_revision=data.get("documentRevision", 0),
        restored_from_version_id=data.get("restoredFromVersionId"),
    )


def _snapshot_payload(
    document: DocumentModel, actor_id: str, author_name: str | None, source: str,
    label: str | None, restored_from: str | None = None,
) -> dict[str, Any]:
    return {
        "documentId": document.id, "ownerId": document.owner_id,
        "title": document.title, "content": document.content, "wordCount": document.word_count,
        "label": label, "createdAt": utcnow(), "createdBy": actor_id, "authorName": author_name,
        "source": source, "documentRevision": document.revision, "restoredFromVersionId": restored_from,
    }


class VersionRepository:
    def create(
        self,
        document_id: str,
        owner_id: str,
        title: str,
        content: dict[str, Any],
        word_count: int,
        label: str | None = None,
        document_revision: int = 0,
        author_name: str | None = None,
    ) -> VersionModel:
        document = DocumentModel(
            id=document_id, owner_id=owner_id, title=title, content=content,
            word_count=word_count, revision=document_revision,
        )
        payload = _snapshot_payload(document, owner_id, author_name, "manual", label)
        doc_ref = versions_collection().document()
        doc_ref.set(payload)
        return _to_model(doc_ref.id, payload)

    def get(self, version_id: str) -> VersionModel | None:
        snap = versions_collection().document(version_id).get()
        if not snap.exists:
            return None
        return _to_model(snap.id, snap.to_dict() or {})

    def list_by_document(self, document_id: str) -> list[VersionModel]:
        query = versions_collection().where(filter=FieldFilter("documentId", "==", document_id))
        models = [_to_model(snap.id, snap.to_dict() or {}) for snap in query.stream()]
        models.sort(key=lambda v: v.created_at or utcnow(), reverse=True)
        return models

    def list_all_by_owner(self, owner_id: str) -> list[VersionModel]:
        query = versions_collection().where(filter=FieldFilter("ownerId", "==", owner_id))
        return [_to_model(snap.id, snap.to_dict() or {}) for snap in query.stream()]

    def restore(
        self, document_id: str, version_id: str, actor_id: str, base_revision: int,
        author_name: str | None = None,
    ) -> DocumentModel:
        document_ref = documents_collection().document(document_id)
        version_ref = versions_collection().document(version_id)
        before_ref = versions_collection().document()
        restored_ref = versions_collection().document()

        @firestore.transactional
        def restore_document(transaction: firestore.Transaction) -> DocumentModel:
            current_snapshot = document_ref.get(transaction=transaction)
            if not current_snapshot.exists:
                raise NotFoundError("Document not found")
            current = document_from_snapshot(document_id, current_snapshot.to_dict() or {})
            if current.revision != base_revision:
                raise ConflictError("The document changed. Load the latest document before restoring a version.")
            version_snapshot = version_ref.get(transaction=transaction)
            if not version_snapshot.exists:
                raise NotFoundError("Version not found")
            version = _to_model(version_id, version_snapshot.to_dict() or {})
            if version.document_id != document_id:
                raise PermissionDeniedError("You do not have access to this version")
            try:
                DocumentUpdate(base_revision=base_revision, title=version.title, content=version.content)
            except ValidationError as exc:
                raise ValidationFailedError("This saved version has unsupported or oversized content and cannot be restored.") from exc
            updated = current.model_copy(update={
                "title": version.title, "content": version.content,
                "word_count": len(prosemirror_to_text(version.content).split()),
                "revision": current.revision + 1, "updated_by": actor_id, "updated_at": utcnow(),
            })
            transaction.set(before_ref, _snapshot_payload(current, actor_id, author_name, "before_restore", "Before restore"))
            transaction.update(document_ref, {
                "title": updated.title, "content": updated.content, "wordCount": updated.word_count,
                "revision": updated.revision, "updatedBy": actor_id, "updatedAt": updated.updated_at,
                "lastCheckpointAt": updated.updated_at,
            })
            transaction.set(restored_ref, _snapshot_payload(
                updated, actor_id, author_name, "restore", f"Restored: {version.label or version.title}"[:200], version_id,
            ))
            return updated

        return restore_document(get_firestore().transaction())

    def delete(self, version_id: str) -> None:
        versions_collection().document(version_id).delete()


version_repository = VersionRepository()
