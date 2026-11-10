"""Internal domain representation of a Firestore documents/{documentId} document."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

EMPTY_DOCUMENT_CONTENT: dict[str, Any] = {"type": "doc", "content": [{"type": "paragraph"}]}


class DocumentModel(BaseModel):
    id: str
    owner_id: str
    title: str
    content: dict[str, Any] = Field(default_factory=lambda: dict(EMPTY_DOCUMENT_CONTENT))
    word_count: int = 0
    revision: int = 0
    updated_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_checkpoint_at: datetime | None = None
