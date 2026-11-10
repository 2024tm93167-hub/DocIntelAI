"""Internal domain representation of a document collaborator membership."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Role = Literal["owner", "editor", "viewer"]


class CollaboratorModel(BaseModel):
    id: str
    document_id: str
    user_id: str
    role: Role
    email: str | None = None
    name: str | None = None
    created_at: datetime | None = None
    created_by: str | None = None
