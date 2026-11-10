"""Role-based access control for documents.

Replaces the owner-only ``_get_owned_document`` pattern with role-aware access.
The owner is always implicit (stored on the document); collaborators are stored
in the ``documentCollaborators`` collection. Only the owner can share, delete,
or manage access; editors can edit and create versions/suggestions; viewers
can read.
"""
from typing import Literal

from app.api.deps import AuthenticatedUser
from app.models.collaborator import CollaboratorModel
from app.models.document import DocumentModel
from app.repositories.collaborator_repository import collaborator_repository
from app.repositories.document_repository import document_repository
from app.utils.exceptions import NotFoundError, PermissionDeniedError

Role = Literal["owner", "editor", "viewer"]


def get_document_with_role(
    document_id: str,
    current_user: AuthenticatedUser,
    min_role: Role = "viewer",
) -> tuple[DocumentModel, Role]:
    """Fetch a document and verify the user has at least ``min_role``.

    Returns the document and the user's effective role. Raises NotFoundError if
    the document does not exist, PermissionDeniedError if the user has no access
    or insufficient role.
    """
    document = document_repository.get(document_id)
    if document is None:
        raise NotFoundError("Document not found")

    if document.owner_id == current_user.uid:
        role: Role = "owner"
    else:
        collab = collaborator_repository.find(document_id, current_user.uid)
        if collab is None:
            raise PermissionDeniedError("You do not have access to this document")
        role = collab.role  # type: ignore[assignment]

    role_rank = {"viewer": 0, "editor": 1, "owner": 2}
    if role_rank[role] < role_rank[min_role]:
        raise PermissionDeniedError("You do not have permission to perform this action")

    return document, role


def require_owner(document_id: str, current_user: AuthenticatedUser) -> DocumentModel:
    document, role = get_document_with_role(document_id, current_user, min_role="owner")
    return document


def require_editor(document_id: str, current_user: AuthenticatedUser) -> tuple[DocumentModel, Role]:
    return get_document_with_role(document_id, current_user, min_role="editor")


def require_viewer(document_id: str, current_user: AuthenticatedUser) -> tuple[DocumentModel, Role]:
    return get_document_with_role(document_id, current_user, min_role="viewer")


def list_accessible_documents(current_user: AuthenticatedUser) -> list[DocumentModel]:
    """Return documents owned by or shared with the user."""
    owned = document_repository.list_by_owner(current_user.uid)
    shared_ids: set[str] = set()
    for collab in collaborator_repository.list_by_user(current_user.uid):
        shared_ids.add(collab.document_id)
    shared = [document_repository.get(doc_id) for doc_id in shared_ids]
    shared = [doc for doc in shared if doc is not None]
    all_docs = owned + shared
    all_docs.sort(key=lambda doc: doc.updated_at or __import__("app.repositories.base", fromlist=["utcnow"]).utcnow(), reverse=True)
    return all_docs
