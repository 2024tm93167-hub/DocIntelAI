"""Internal domain representation of a persistent AI writing suggestion."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


SuggestionType = Literal[
    "grammar", "clarity", "tone", "wordiness", "repetition", "alternative", "rewrite", "other",
    "spelling", "conciseness", "readability", "word_choice",
]
SuggestionStatus = Literal["pending", "accepted", "rejected"]


class SuggestionModel(BaseModel):
    id: str
    document_id: str
    user_id: str
    type: SuggestionType = "other"
    original_text: str = ""
    suggested_text: str = ""
    reason: str | None = None
    status: SuggestionStatus = "pending"
    document_revision: int = 0
    created_at: datetime | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
