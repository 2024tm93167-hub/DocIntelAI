"""Endpoints for sharing documents and managing collaborator access."""
from fastapi import APIRouter, Depends, status

from app.api.deps import AuthenticatedUser, get_current_user
from app.repositories.base import users_collection
from app.repositories.collaborator_repository import collaborator_repository
from app.repositories.document_repository import document_repository
from app.schemas.collaborator import CollaboratorInvite, CollaboratorOut
from app.services.permissions import require_owner
from app.utils.exceptions import NotFoundError, PermissionDeniedError
from google.cloud.firestore_v1.base_query import FieldFilter

router = APIRouter(prefix="/documents/{document_id}/collaborators", tags=["sharing"])


def _resolve_user_by_email(email: str) -> tuple[str, str | None]:
    """Resolve an email to a Firebase UID via the users collection.

    Returns (uid, name). Raises NotFoundError if no user with that email exists.
    """
    query = users_collection().where(filter=FieldFilter("email", "==", email))
    for snap in query.limit(1).stream():
        data = snap.to_dict() or {}
        return snap.id, data.get("name")
    raise NotFoundError(f"No user found with email {email}. They must register first.")


@router.get("", response_model=list[CollaboratorOut])
def list_collaborators(
    document_id: str, current_user: AuthenticatedUser = Depends(get_current_user)
) -> list[CollaboratorOut]:
    require_owner(document_id, current_user)
    collabs = collaborator_repository.list_by_document(document_id)
    return [CollaboratorOut(**c.model_dump()) for c in collabs]


@router.post("", response_model=CollaboratorOut, status_code=status.HTTP_201_CREATED)
def invite_collaborator(
    document_id: str,
    payload: CollaboratorInvite,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CollaboratorOut:
    document = require_owner(document_id, current_user)
    uid, name = _resolve_user_by_email(payload.email)
    if uid == current_user.uid:
        raise PermissionDeniedError("You cannot share a document with yourself.")
    if uid == document.owner_id:
        raise PermissionDeniedError("The document owner already has full access.")
    collab = collaborator_repository.upsert(
        document_id=document_id,
        user_id=uid,
        role=payload.role,
        email=payload.email,
        name=name,
        created_by=current_user.uid,
    )
    return CollaboratorOut(**collab.model_dump())


@router.delete("/{collaborator_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_collaborator(
    document_id: str,
    collaborator_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> None:
    require_owner(document_id, current_user)
    collaborator_repository.delete(collaborator_id)
