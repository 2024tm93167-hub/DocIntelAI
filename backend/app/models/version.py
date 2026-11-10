"""Internal domain representation of a Firestore documents/{docId}/versions/{versionId} snapshot."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class VersionModel(BaseModel):
    id: str
    document_id: str
    owner_id: str
    title: str
    content: dict[str, Any]
    word_count: int = 0
    label: str | None = None
    created_at: datetime | None = None
    created_by: str | None = None
    author_name: str | None = None
    source: Literal["manual", "autosave", "before_restore", "restore"] = "manual"
    document_revision: int = 0
    restored_from_version_id: str | None = None
