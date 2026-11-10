"""API request/response contracts for document sharing."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RoleLiteral = Literal["editor", "viewer"]


class CollaboratorInvite(BaseModel):
    """Request to add or update a collaborator on a document.

    Only ``editor`` and ``viewer`` roles can be granted via this endpoint; the
    owner role is implicit and assigned at document creation.
    """

    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role: RoleLiteral = "viewer"


class CollaboratorOut(BaseModel):
    """Collaborator record returned to the frontend."""

    id: str
    document_id: str
    user_id: str
    role: Literal["owner", "editor", "viewer"]
    email: str | None = None
    name: str | None = None
    created_at: datetime | None = None
    created_by: str | None = None
