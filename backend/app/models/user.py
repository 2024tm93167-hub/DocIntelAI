"""Internal domain representation of a Firestore users/{uid} document."""
from datetime import datetime

from pydantic import BaseModel


class UserModel(BaseModel):
    uid: str
    name: str | None = None
    email: str | None = None
    created_at: datetime | None = None
    last_login_at: datetime | None = None
