"""Public health-check endpoint."""
from fastapi import APIRouter

from app.config.settings import get_settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", app=settings.app_name, environment=settings.environment)
