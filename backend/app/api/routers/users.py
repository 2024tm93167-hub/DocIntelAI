"""Endpoints for the authenticated user's own profile."""
from fastapi import APIRouter, Depends

from app.api.deps import AuthenticatedUser, get_current_user
from app.repositories.user_repository import user_repository
from app.schemas.user import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def read_current_user(current_user: AuthenticatedUser = Depends(get_current_user)) -> UserOut:
    """Return the current user's profile, auto-provisioning it on first login."""
    user = user_repository.get_or_create(current_user.uid, current_user.email, current_user.name)
    return UserOut(**user.model_dump())
