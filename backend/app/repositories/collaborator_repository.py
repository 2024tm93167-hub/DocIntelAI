"""Firestore-backed persistence for document collaborator memberships."""
from typing import Any

from google.cloud.firestore_v1.base_query import FieldFilter

from app.models.collaborator import CollaboratorModel
from app.repositories.base import collaborators_collection, documents_collection, utcnow
from app.utils.exceptions import NotFoundError, PermissionDeniedError, ValidationFailedError


def _to_model(collab_id: str, data: dict[str, Any]) -> CollaboratorModel:
    return CollaboratorModel(
        id=collab_id,
        document_id=data.get("documentId", ""),
        user_id=data.get("userId", ""),
        role=data.get("role", "viewer"),
        email=data.get("email"),
        name=data.get("name"),
        created_at=data.get("createdAt"),
        created_by=data.get("createdBy"),
    )


class CollaboratorRepository:
    def list_by_document(self, document_id: str) -> list[CollaboratorModel]:
        query = collaborators_collection().where(filter=FieldFilter("documentId", "==", document_id))
        return [_to_model(snap.id, snap.to_dict() or {}) for snap in query.stream()]

    def list_by_user(self, user_id: str) -> list[CollaboratorModel]:
        query = collaborators_collection().where(filter=FieldFilter("userId", "==", user_id))
        return [_to_model(snap.id, snap.to_dict() or {}) for snap in query.stream()]

    def find(self, document_id: str, user_id: str) -> CollaboratorModel | None:
        query = collaborators_collection().where(filter=FieldFilter("documentId", "==", document_id)).where(
            filter=FieldFilter("userId", "==", user_id)
        )
        for snap in query.limit(1).stream():
            return _to_model(snap.id, snap.to_dict() or {})
        return None

    def upsert(
        self,
        document_id: str,
        user_id: str,
        role: str,
        email: str | None,
        name: str | None,
        created_by: str,
    ) -> CollaboratorModel:
        existing = self.find(document_id, user_id)
        now = utcnow()
        if existing:
            collaborators_collection().document(existing.id).update({"role": role, "email": email, "name": name})
            return CollaboratorModel(
                id=existing.id, document_id=document_id, user_id=user_id, role=role,
                email=email, name=name, created_at=existing.created_at, created_by=existing.created_by,
            )
        payload = {
            "documentId": document_id, "userId": user_id, "role": role,
            "email": email, "name": name, "createdAt": now, "createdBy": created_by,
        }
        doc_ref = collaborators_collection().document()
        doc_ref.set(payload)
        return CollaboratorModel(
            id=doc_ref.id, document_id=document_id, user_id=user_id, role=role,
            email=email, name=name, created_at=now, created_by=created_by,
        )

    def delete(self, collaborator_id: str) -> None:
        collaborators_collection().document(collaborator_id).delete()

    def delete_all_for_document(self, document_id: str) -> None:
        query = collaborators_collection().where(filter=FieldFilter("documentId", "==", document_id))
        for snap in query.stream():
            snap.reference.delete()


collaborator_repository = CollaboratorRepository()
