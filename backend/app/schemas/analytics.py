"""API schemas for analytics, evaluation, and export endpoints."""
from enum import Enum

from pydantic import BaseModel


class UserStats(BaseModel):
    """Aggregate writing statistics for the authenticated user."""

    total_documents: int
    total_words: int
    total_versions: int
    average_words_per_document: float
    documents_last_7_days: int
    documents_last_30_days: int


class DocumentStats(BaseModel):
    """Computed statistics for a single document."""

    word_count: int
    char_count: int
    sentence_count: int
    paragraph_count: int
    estimated_reading_time_minutes: float


class ReadabilityResult(DocumentStats):
    """Readability evaluation for a single document."""

    flesch_reading_ease: float
    flesch_kincaid_grade: float
    suggestions: list[str]


class ExportFormat(str, Enum):
    markdown = "markdown"
    html = "html"
    text = "text"
    docx = "docx"
    pdf = "pdf"
