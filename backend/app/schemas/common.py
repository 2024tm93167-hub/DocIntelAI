"""Shared API response schemas."""
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str


class ErrorResponse(BaseModel):
    detail: str
