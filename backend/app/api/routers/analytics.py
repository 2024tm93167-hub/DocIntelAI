"""Endpoints for writing analytics, readability evaluation, and document export."""
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from starlette.responses import Response

from app.api.deps import AuthenticatedUser, get_current_user
from app.repositories.document_repository import DocumentRepository, document_repository
from app.repositories.version_repository import VersionRepository, version_repository
from app.schemas.analytics import DocumentStats, ExportFormat, ReadabilityResult, UserStats
from app.services.permissions import require_viewer
from app.utils.content import (
    compute_stats,
    escape_html,
    prosemirror_to_html,
    prosemirror_to_markdown,
    prosemirror_to_text,
    readability_suggestions,
)
from app.utils.exporters import prosemirror_to_docx, prosemirror_to_pdf
from app.utils.exceptions import NotFoundError, PermissionDeniedError

router = APIRouter(tags=["analytics"])


def _assert_owner(user: AuthenticatedUser, document: Any) -> None:
    if document is None or document.owner_id != user.uid:
        raise PermissionDeniedError("You do not have access to this document.")


@router.get("/analytics", response_model=UserStats)
def user_stats(
    current_user: AuthenticatedUser = Depends(get_current_user),
    docs_repo: DocumentRepository = Depends(lambda: document_repository),
    versions_repo: VersionRepository = Depends(lambda: version_repository),
) -> UserStats:
    docs = docs_repo.list_by_owner(current_user.uid)
    versions = versions_repo.list_all_by_owner(current_user.uid)

    total_words = sum(doc.word_count for doc in docs)
    now = datetime.now(timezone.utc)
    last_7 = now - timedelta(days=7)
    last_30 = now - timedelta(days=30)

    def within_days(doc: Any, cutoff: datetime) -> bool:
        return doc.created_at is not None and doc.created_at >= cutoff

    return UserStats(
        total_documents=len(docs),
        total_words=total_words,
        total_versions=len(versions),
        average_words_per_document=round(total_words / len(docs), 2) if docs else 0.0,
        documents_last_7_days=sum(1 for doc in docs if within_days(doc, last_7)),
        documents_last_30_days=sum(1 for doc in docs if within_days(doc, last_30)),
    )


@router.get("/documents/{document_id}/stats", response_model=DocumentStats)
def document_stats(
    document_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    repo: DocumentRepository = Depends(lambda: document_repository),
) -> DocumentStats:
    doc = repo.get(document_id)
    if doc is None:
        raise NotFoundError("Document not found.")
    if doc.owner_id != current_user.uid:
        raise PermissionDeniedError("You do not have access to this document.")

    text = prosemirror_to_text(doc.content)
    stats = compute_stats(text)
    return DocumentStats(
        word_count=stats["word_count"],
        char_count=stats["char_count"],
        sentence_count=stats["sentence_count"],
        paragraph_count=stats["paragraph_count"],
        estimated_reading_time_minutes=stats["estimated_reading_time_minutes"],
    )


@router.get("/documents/{document_id}/evaluate", response_model=ReadabilityResult)
def evaluate_document(
    document_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    repo: DocumentRepository = Depends(lambda: document_repository),
) -> ReadabilityResult:
    doc = repo.get(document_id)
    if doc is None:
        raise NotFoundError("Document not found.")
    if doc.owner_id != current_user.uid:
        raise PermissionDeniedError("You do not have access to this document.")

    text = prosemirror_to_text(doc.content)
    stats = compute_stats(text)
    suggestions = readability_suggestions(stats)
    return ReadabilityResult(
        word_count=stats["word_count"],
        char_count=stats["char_count"],
        sentence_count=stats["sentence_count"],
        paragraph_count=stats["paragraph_count"],
        estimated_reading_time_minutes=stats["estimated_reading_time_minutes"],
        flesch_reading_ease=stats["flesch_reading_ease"],
        flesch_kincaid_grade=stats["flesch_kincaid_grade"],
        suggestions=suggestions,
    )


@router.get("/documents/{document_id}/export")
def export_document(
    document_id: str,
    format: ExportFormat = Query(ExportFormat.markdown, alias="format"),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    doc, _ = require_viewer(document_id, current_user)

    safe_title = "".join(c for c in doc.title if c.isalnum() or c in (" ", "-", "_")).rstrip()
    body: str | bytes
    if format == ExportFormat.markdown:
        body = f"# {doc.title}\n\n{prosemirror_to_markdown(doc.content)}"
        media_type = "text/markdown"
        extension = "md"
    elif format == ExportFormat.html:
        title = escape_html(doc.title)
        body = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{title}</title></head><body>\n<h1>{title}</h1>\n{prosemirror_to_html(doc.content)}</body></html>"
        media_type = "text/html"
        extension = "html"
    elif format == ExportFormat.docx:
        body = prosemirror_to_docx(doc.title, doc.content)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        extension = "docx"
    elif format == ExportFormat.pdf:
        body = prosemirror_to_pdf(doc.title, doc.content)
        media_type = "application/pdf"
        extension = "pdf"
    else:
        body = f"{doc.title}\n\n{prosemirror_to_text(doc.content)}"
        media_type = "text/plain"
        extension = "txt"

    filename = f"{safe_title or 'document'}.{extension}"
    ascii_title = safe_title.encode("ascii", "ignore").decode().strip() or "document"
    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{ascii_title}.{extension}"; filename*=UTF-8\'\'{quote(filename, safe="")}',
            "X-Content-Type-Options": "nosniff",
        },
    )
