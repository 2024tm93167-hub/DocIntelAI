"""Endpoints for creating, listing, editing and deleting documents.

All application data access goes through this router using the Firebase
Admin SDK-backed repository. Access is role-aware: the owner has full control,
editors can edit, and viewers can read. See ``app/services/permissions.py``.
"""
from fastapi import APIRouter, Depends, status

from app.api.deps import AuthenticatedUser, get_current_user
from app.models.document import DocumentModel
from app.repositories.collaborator_repository import collaborator_repository
from app.repositories.document_repository import document_repository
from app.schemas.document import DocumentCreate, DocumentOut, DocumentSummary, DocumentUpdate
from app.services.permissions import list_accessible_documents, require_editor, require_owner, require_viewer
from app.services.connection_manager import connection_manager
from app.utils.exceptions import NotFoundError

router = APIRouter(prefix="/documents", tags=["documents"])


def _get_owned_document(document_id: str, current_user: AuthenticatedUser) -> DocumentModel:
    """Backward-compatible owner-only accessor used by version/suggestion routers."""
    return require_owner(document_id, current_user)


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: DocumentCreate, current_user: AuthenticatedUser = Depends(get_current_user)
) -> DocumentOut:
    document = document_repository.create(current_user.uid, payload.title)
    return DocumentOut(**document.model_dump())


@router.get("", response_model=list[DocumentSummary])
def list_documents(current_user: AuthenticatedUser = Depends(get_current_user)) -> list[DocumentSummary]:
    documents = list_accessible_documents(current_user)
    return [DocumentSummary(**doc.model_dump()) for doc in documents]


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: str, current_user: AuthenticatedUser = Depends(get_current_user)
) -> DocumentOut:
    document, _ = require_viewer(document_id, current_user)
    return DocumentOut(**document.model_dump())


@router.patch("/{document_id}", response_model=DocumentOut)
async def update_document(
    document_id: str,
    payload: DocumentUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> DocumentOut:
    require_editor(document_id, current_user)
    updated = document_repository.update(
        document_id,
        actor_id=current_user.uid,
        base_revision=payload.base_revision,
        title=payload.title,
        content=payload.content,
        word_count=payload.word_count,
    )
    if updated is None:
        raise NotFoundError("Document not found")
    await connection_manager.broadcast_document_update(
        document_id, updated.revision, current_user.uid, current_user.name
    )
    return DocumentOut(**updated.model_dump())


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str, current_user: AuthenticatedUser = Depends(get_current_user)
) -> None:
    require_owner(document_id, current_user)
    collaborator_repository.delete_all_for_document(document_id)
    document_repository.delete(document_id)
