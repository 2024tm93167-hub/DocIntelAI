"""API request/response contracts for document version endpoints."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class VersionCreate(BaseModel):
    """Request body for explicitly saving a version.

    ``base_revision`` is optional but, when supplied, must match the document's
    current revision. This prevents a stale client from snapshotting a document
    state that has since changed on the server.
    """

    label: str | None = Field(default=None, max_length=200)
    base_revision: int | None = Field(default=None, ge=0, strict=True)


class VersionRestore(BaseModel):
    base_revision: int = Field(ge=0, strict=True)


class VersionSummary(BaseModel):
    """Lightweight version used for the history list."""

    id: str
    document_id: str
    title: str
    word_count: int
    label: str | None = None
    created_at: datetime | None = None
    created_by: str | None = None
    author_name: str | None = None
    source: Literal["manual", "autosave", "before_restore", "restore"] = "manual"
    document_revision: int = 0
    restored_from_version_id: str | None = None


class VersionOut(VersionSummary):
    """Full version, including the snapshot content."""

    content: dict[str, Any]


class DiffChunk(BaseModel):
    """A single diff operation between two pieces of text."""

    op: str = Field(pattern="^(equal|insert|delete|replace)$")
    old_text: str | None = None
    new_text: str | None = None


class DiffOut(BaseModel):
    """Diff between two document contents."""

    from_version_id: str | None = None
    to_version_id: str | None = None
    chunks: list[DiffChunk]
