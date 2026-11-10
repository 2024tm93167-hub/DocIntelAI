"""Shared FastAPI dependencies, primarily Firebase authentication."""
from fastapi import Header
from pydantic import BaseModel

from app.firebase.admin import verify_id_token
from app.utils.exceptions import AuthenticationError


class AuthenticatedUser(BaseModel):
    """Minimal identity extracted from a verified Firebase ID token."""

    uid: str
    email: str | None = None
    name: str | None = None


def get_current_user(authorization: str | None = Header(default=None)) -> AuthenticatedUser:
    """Verify the Firebase ID token from the Authorization header.

    Expected header: ``Authorization: Bearer <firebase-id-token>``
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthenticationError("Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise AuthenticationError("Missing bearer token")

    try:
        decoded = verify_id_token(token)
    except Exception as exc:  # noqa: BLE001 - any verification failure is an auth error
        raise AuthenticationError("Invalid or expired authentication token") from exc

    return AuthenticatedUser(
        uid=decoded["uid"],
        email=decoded.get("email"),
        name=decoded.get("name"),
    )
