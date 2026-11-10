"""Endpoints for saving, listing and diffing document versions.

A version is an explicit, user-saved snapshot of a document at a point in time.
Versions can be compared with each other or with the current document.

Access is role-aware: viewers can list/read/diff versions, editors can create
and restore versions, only the owner can delete version history.
"""
from fastapi import APIRouter, Depends, status

from app.api.deps import AuthenticatedUser, get_current_user
from app.models.version import VersionModel
from app.repositories.version_repository import version_repository
from app.schemas.document import DocumentOut
from app.schemas.version import DiffChunk, DiffOut, VersionCreate, VersionOut, VersionRestore, VersionSummary
from app.services.permissions import require_editor, require_owner, require_viewer
from app.services.connection_manager import connection_manager
from app.utils.diff import diff_texts, prosemirror_to_text
from app.utils.exceptions import ConflictError, NotFoundError, PermissionDeniedError

router = APIRouter(prefix="/documents/{document_id}/versions", tags=["versions"])


def _get_accessible_version(
    document_id: str, version_id: str, current_user: AuthenticatedUser
) -> VersionModel:
    """Fetch a version, requiring viewer access to the document and verifying linkage."""
    require_viewer(document_id, current_user)
    version = version_repository.get(version_id)
    if version is None:
        raise NotFoundError("Version not found")
    if version.document_id != document_id:
        raise PermissionDeniedError("You do not have access to this version")
    return version


@router.post("", response_model=VersionOut, status_code=status.HTTP_201_CREATED)
async def create_version(
    document_id: str,
    payload: VersionCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> VersionOut:
    document, _ = require_editor(document_id, current_user)
    if payload.base_revision is not None and payload.base_revision != document.revision:
        raise ConflictError(
            "This document changed elsewhere. Reload the latest document before saving a version."
        )
    version = version_repository.create(
        document_id=document_id,
        owner_id=current_user.uid,
        title=document.title,
        content=document.content,
        word_count=document.word_count,
        label=payload.label,
        document_revision=document.revision,
        author_name=current_user.name,
    )
    await connection_manager.broadcast_version_created(
        document_id, version.id, version.label, current_user.uid
    )
    return VersionOut(**version.model_dump())


@router.get("", response_model=list[VersionSummary])
def list_versions(
    document_id: str, current_user: AuthenticatedUser = Depends(get_current_user)
) -> list[VersionSummary]:
    require_viewer(document_id, current_user)
    versions = version_repository.list_by_document(document_id)
    return [VersionSummary(**v.model_dump()) for v in versions]


@router.get("/{version_id}", response_model=VersionOut)
def get_version(
    document_id: str,
    version_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> VersionOut:
    version = _get_accessible_version(document_id, version_id, current_user)
    return VersionOut(**version.model_dump())


@router.delete("/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_version(
    document_id: str,
    version_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> None:
    require_owner(document_id, current_user)
    version = version_repository.get(version_id)
    if version is None:
        raise NotFoundError("Version not found")
    if version.document_id != document_id:
        raise PermissionDeniedError("You do not have access to this version")
    version_repository.delete(version_id)


@router.post("/{version_id}/restore", response_model=DocumentOut)
async def restore_version(
    document_id: str, version_id: str, payload: VersionRestore,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> DocumentOut:
    require_editor(document_id, current_user)
    document = version_repository.restore(document_id, version_id, current_user.uid, payload.base_revision, current_user.name)
    await connection_manager.broadcast_document_update(
        document_id, document.revision, current_user.uid, current_user.name
    )
    return DocumentOut(**document.model_dump())


@router.get("/{version_id}/diff", response_model=DiffOut)
def diff_version(
    document_id: str,
    version_id: str,
    compare_to: str | None = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> DiffOut:
    from_version = _get_accessible_version(document_id, version_id, current_user)
    from_text = prosemirror_to_text(from_version.content)

    if compare_to:
        to_version = _get_accessible_version(document_id, compare_to, current_user)
        to_text = prosemirror_to_text(to_version.content)
        to_version_id = to_version.id
    else:
        document, _ = require_viewer(document_id, current_user)
        to_text = prosemirror_to_text(document.content)
        to_version_id = None

    opcodes = diff_texts(from_text, to_text)
    chunks = [
        DiffChunk(op=op, old_text=old or None, new_text=new or None) for op, old, new in opcodes
    ]
    return DiffOut(
        from_version_id=from_version.id,
        to_version_id=to_version_id,
        chunks=chunks,
    )
