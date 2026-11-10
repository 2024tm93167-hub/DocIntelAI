"""Firestore-backed persistence for persistent AI writing suggestions."""
from datetime import datetime
from copy import deepcopy

from google.cloud import firestore
from app.schemas.document import DocumentUpdate
from app.services.ai_actions import clean_writing
from app.firebase.admin import get_firestore
from app.repositories.base import versions_collection
from app.repositories.document_repository import _to_model as document_model, _checkpoint_payload
from app.utils.content import prosemirror_to_text


def find_suggested_matches(content: dict, original: str) -> list[tuple[dict, int, int]]:
    """Locate `original` inside single-node text runs — the same rule apply uses."""
    matches: list[tuple[dict, int, int]] = []
    if not original:
        return matches

    def visit(node):
        children = node.get("content", [])
        if node.get("type") in ("paragraph", "heading") and all(c.get("type") == "text" for c in children):
            text = "".join(c.get("text", "") for c in children)
            start = text.find(original)
            while start >= 0:
                matches.append((node, start, start + len(original)))
                start = text.find(original, start + 1)
        for child in children:
            visit(child)

    visit(content)
    return matches


def replace_suggested_text(content: dict, original: str, replacement: str) -> dict:
    result = deepcopy(content)
    matches = find_suggested_matches(result, original)
    if len(matches) != 1:
        raise ConflictError("The suggested passage is missing or ambiguous. Analyze again.")
    node, start, end = matches[0]
    children = []
    offset = 0
    inserted = False
    for child in node["content"]:
        text = child["text"]
        stop = offset + len(text)
        if stop <= start or offset >= end:
            children.append(child)
        else:
            prefix = text[:max(0, start - offset)]
            suffix = text[max(0, end - offset):]
            if prefix:
                children.append({**child, "text": prefix})
            if not inserted:
                children.append({**child, "text": replacement})
                inserted = True
            if suffix:
                children.append({**child, "text": suffix})
        offset = stop
    node["content"] = children
    return result
from typing import Any

from google.cloud.firestore_v1.base_query import FieldFilter

from app.models.suggestion import SuggestionModel
from app.repositories.base import documents_collection, suggestions_collection, utcnow
from app.utils.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError


def _to_model(suggestion_id: str, data: dict[str, Any]) -> SuggestionModel:
    return SuggestionModel(
        id=suggestion_id,
        document_id=data.get("documentId", ""),
        user_id=data.get("userId", ""),
        type=data.get("type", "other"),
        original_text=data.get("originalText", ""),
        suggested_text=data.get("suggestedText", ""),
        reason=data.get("reason"),
        status=data.get("status", "pending"),
        document_revision=data.get("documentRevision", 0),
        created_at=data.get("createdAt"),
        resolved_at=data.get("resolvedAt"),
        resolved_by=data.get("resolvedBy"),
    )


def _payload(model: SuggestionModel) -> dict[str, Any]:
    return {
        "documentId": model.document_id,
        "userId": model.user_id,
        "type": model.type,
        "originalText": model.original_text,
        "suggestedText": model.suggested_text,
        "reason": model.reason,
        "status": model.status,
        "documentRevision": model.document_revision,
        "createdAt": model.created_at,
        "resolvedAt": model.resolved_at,
        "resolvedBy": model.resolved_by,
    }


class SuggestionRepository:
    def create(
        self,
        document_id: str,
        user_id: str,
        type_: str,
        original_text: str,
        suggested_text: str,
        reason: str | None,
        document_revision: int,
    ) -> SuggestionModel:
        now = utcnow()
        model = SuggestionModel(
            id="",
            document_id=document_id,
            user_id=user_id,
            type=type_,
            original_text=original_text,
            suggested_text=suggested_text,
            reason=reason,
            status="pending",
            document_revision=document_revision,
            created_at=now,
        )
        doc_ref = suggestions_collection().document()
        payload = _payload(model)
        payload["createdAt"] = now
        doc_ref.set(payload)
        model.id = doc_ref.id
        return model

    def get(self, suggestion_id: str) -> SuggestionModel | None:
        snap = suggestions_collection().document(suggestion_id).get()
        if not snap.exists:
            return None
        return _to_model(snap.id, snap.to_dict() or {})

    def list_by_document(
        self, document_id: str, user_id: str, status: str | None = None
    ) -> list[SuggestionModel]:
        query = suggestions_collection().where(filter=FieldFilter("documentId", "==", document_id))
        models = [_to_model(snap.id, snap.to_dict() or {}) for snap in query.stream()]
        # Enforce ownership: only return suggestions owned by the requesting user.
        models = [m for m in models if m.user_id == user_id]
        if status:
            models = [m for m in models if m.status == status]
        models.sort(key=lambda m: m.created_at or utcnow(), reverse=True)
        return models

    def update_status(
        self,
        suggestion_id: str,
        actor_id: str,
        status: str,
        base_revision: int | None,
    ) -> SuggestionModel:
        suggestion_ref = suggestions_collection().document(suggestion_id)
        snap = suggestion_ref.get()
        if not snap.exists:
            raise NotFoundError("Suggestion not found")
        data = snap.to_dict() or {}
        suggestion = _to_model(suggestion_id, data)
        if suggestion.user_id != actor_id:
            raise PermissionDeniedError("You do not have access to this suggestion")
        if suggestion.status != "pending":
            raise ConflictError("This suggestion has already been resolved.")
        if status == "accepted":
            if base_revision is None:
                raise ValidationFailedError("base_revision is required to accept a suggestion.")
            doc_snap = documents_collection().document(suggestion.document_id).get()
            if not doc_snap.exists:
                raise NotFoundError("Document not found")
            current_revision = (doc_snap.to_dict() or {}).get("revision", 0)
            if current_revision != base_revision:
                raise ConflictError(
                    "The document changed after this suggestion was created. "
                    "Reload the document and try again."
                )
        now = utcnow()
        updates = {"status": status, "resolvedAt": now, "resolvedBy": actor_id}
        suggestion_ref.update(updates)
        return _to_model(suggestion_id, {**data, **updates})

    def apply(self, document_id: str, suggestion_id: str, actor_id: str, base_revision: int):
        doc_ref = documents_collection().document(document_id)
        suggestion_ref = suggestions_collection().document(suggestion_id)

        @firestore.transactional
        def apply_in_transaction(transaction):
            doc_snap = doc_ref.get(transaction=transaction)
            suggestion_snap = suggestion_ref.get(transaction=transaction)
            if not doc_snap.exists or not suggestion_snap.exists:
                raise NotFoundError("Document or suggestion not found")
            data = doc_snap.to_dict() or {}
            suggestion_data = suggestion_snap.to_dict() or {}
            suggestion = _to_model(suggestion_id, suggestion_data)
            if suggestion.document_id != document_id or suggestion.user_id != actor_id:
                raise PermissionDeniedError("You do not have access to this suggestion")
            if suggestion.status != "pending" or data.get("revision", 0) != base_revision:
                raise ConflictError("The document or suggestion changed. Reload before applying.")
            replacement = clean_writing(suggestion.suggested_text)
            content = replace_suggested_text(data["content"], suggestion.original_text, replacement)
            try:
                DocumentUpdate.validate_content(content)
            except ValueError as exc:
                raise ValidationFailedError("The suggested edit exceeds document limits.") from exc
            now = utcnow()
            updates = {"content": content, "wordCount": len(prosemirror_to_text(content).split()),
                       "revision": base_revision + 1, "updatedBy": actor_id, "updatedAt": now,
                       "lastCheckpointAt": now}
            resolved = {"status": "accepted", "resolvedBy": actor_id, "resolvedAt": now}
            transaction.set(versions_collection().document(), _checkpoint_payload(document_model(document_id, data), actor_id, now))
            transaction.update(doc_ref, updates)
            transaction.update(suggestion_ref, resolved)
            return document_model(document_id, {**data, **updates}), _to_model(suggestion_id, {**suggestion_data, **resolved})

        return apply_in_transaction(get_firestore().transaction())

    def delete(self, suggestion_id: str) -> None:
        suggestions_collection().document(suggestion_id).delete()


suggestion_repository = SuggestionRepository()
