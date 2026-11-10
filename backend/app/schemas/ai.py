"""API request/response contracts for the AI assistant endpoints."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Annotated

from app.schemas.suggestion import SuggestionTypeLiteral


class AiTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=30000)


class TitleSuggestions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    titles: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(min_length=3, max_length=5)


class WritingSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: SuggestionTypeLiteral
    original: str = Field(min_length=1, max_length=2000)
    suggested: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=1, max_length=500)


class WritingAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    suggestions: list[WritingSuggestion] = Field(max_length=20)


class AiRewriteRequest(BaseModel):
    """Request to rewrite a piece of text."""

    text: str = Field(min_length=1, max_length=30000)
    instruction: str = Field(
        default="",
        max_length=500,
        description="Optional custom instruction, e.g. 'make this more formal'.",
    )


class AiSummarizeRequest(BaseModel):
    """Request to summarize a piece of text."""

    text: str = Field(min_length=1, max_length=50000)
    max_words: int = Field(default=100, ge=10, le=1000)


class AiGenerateRequest(BaseModel):
    """Request to generate new text from a free-form prompt."""

    prompt: str = Field(
        min_length=1,
        max_length=2000,
        description="What to write, e.g. 'write about agriculture in 100 words'.",
    )

    @field_validator("prompt")
    @classmethod
    def nonblank_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter a prompt before generating content")
        return value.strip()


class AiActionRequest(BaseModel):
    """Request to run a named AI writing action.

    ``text`` is the selected text (or full document text when nothing is
    selected) for text-based actions. ``prompt`` is used by ``generate`` and
    ``outline``. ``instruction`` is a free-form modifier; ``tone`` selects a
    preset tone for the ``tone`` action. Lightweight context (``document_title``,
    ``before``, ``after``) is optional and trimmed server-side to bound tokens.
    """

    action: Literal[
        "rewrite", "improve", "expand", "condense", "summarize",
        "grammar", "tone", "continue", "outline", "custom", "generate", "heading", "headings",
    ]
    text: str = Field(default="", max_length=30000)
    instruction: str = Field(default="", max_length=500)
    tone: str | None = Field(default=None, max_length=50)
    max_words: int | None = Field(default=None, ge=10, le=1000)
    prompt: str = Field(default="", max_length=2000)
    document_title: str = Field(default="", max_length=200)
    before: str = Field(default="", max_length=4000)
    after: str = Field(default="", max_length=4000)

    @field_validator("tone")
    @classmethod
    def nonblank_tone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class AiResponse(BaseModel):
    """Output from the AI assistant."""

    output: str


class AiActionInfo(BaseModel):
    """Metadata for a supported AI action, used by the discovery endpoint."""

    action: str
    label: str
    needs_text: bool
