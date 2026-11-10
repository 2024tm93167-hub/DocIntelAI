"""API request/response contracts for document endpoints."""
from datetime import datetime
import json
from typing import Any

from pydantic import BaseModel, Field, field_validator


class DocumentCreate(BaseModel):
    title: str = Field(default="Untitled Document", max_length=200)


class DocumentUpdate(BaseModel):
    """Partial update used by the editor's autosave. All fields optional."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: dict[str, Any] | None = None
    word_count: int | None = Field(default=None, ge=0)
    base_revision: int = Field(ge=0, strict=True)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return value
        if value.get("type") != "doc":
            raise ValueError("Content must be a TipTap document")
        pending = [(value, 0)]
        count = 0
        while pending:
            node, depth = pending.pop()
            count += 1
            if depth > 64 or count > 20000:
                raise ValueError("Document structure is too large or deeply nested")
            if not isinstance(node, dict) or not isinstance(node.get("type"), str):
                raise ValueError("Each document node must have a type")
            if "text" in node and not isinstance(node["text"], str):
                raise ValueError("Node text must be a string")
            if not isinstance(node.get("attrs", {}), dict):
                raise ValueError("Node attributes must be an object")
            marks = node.get("marks", [])
            if not isinstance(marks, list) or any(
                not isinstance(mark, dict) or not isinstance(mark.get("type"), str)
                or not isinstance(mark.get("attrs", {}), dict) for mark in marks
            ):
                raise ValueError("Invalid text marks")
            children = node.get("content", [])
            if not isinstance(children, list):
                raise ValueError("Node content must be a list")
            pending.extend((child, depth + 1) for child in children)
        if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > 750000:
            raise ValueError("Document content exceeds the 750 KB limit")
        return value


class DocumentSummary(BaseModel):
    """Lightweight representation used for the dashboard document list."""

    id: str
    title: str
    word_count: int
    revision: int = 0
    owner_id: str = ""
    updated_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DocumentOut(DocumentSummary):
    """Full document representation, including editor content."""

    owner_id: str
    content: dict[str, Any]
