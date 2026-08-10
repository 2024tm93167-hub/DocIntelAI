"""API request/response contracts for user endpoints."""
from datetime import datetime

from pydantic import BaseModel


class UserOut(BaseModel):
    uid: str
    name: str | None = None
    email: str | None = None
    created_at: datetime | None = None
    last_login_at: datetime | None = None
