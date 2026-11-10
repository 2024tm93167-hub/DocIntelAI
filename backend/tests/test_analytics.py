"""Tests for analytics, evaluation, and export endpoints."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.models.document import DocumentModel
from app.repositories.base import utcnow
from app.utils.content import prosemirror_to_html

FAKE_DECODED_TOKEN = {"uid": "owner-uid", "email": "owner@example.com", "name": "Owner"}
AUTH_HEADERS = {"Authorization": "Bearer good-token"}


@pytest.fixture(autouse=True)
def isolated_analytics_repositories():
    document = DocumentModel(
        id="analytics-test", owner_id="owner-uid", title="Analytics Test", created_at=utcnow()
    )
    with patch("app.api.routers.documents.document_repository.create", return_value=document), patch(
        "app.api.routers.analytics.document_repository.get", return_value=document
    ), patch(
        "app.services.permissions.document_repository"
    ) as permissions_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo, patch(
        "app.api.routers.analytics.document_repository.list_by_owner", return_value=[document]
    ), patch(
        "app.api.routers.analytics.version_repository.list_all_by_owner", return_value=[]
    ):
        permissions_repo.get.return_value = document
        collab_repo.find.return_value = None
        yield document


def _create_test_document(client: TestClient) -> str:
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        response = client.post(
            "/documents",
            json={"title": "Analytics Test"},
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 201
    return response.json()["id"]


def test_user_stats_requires_auth(client):
    response = client.get("/analytics")
    assert response.status_code == 401


def test_document_stats_requires_auth(client):
    response = client.get("/documents/doc-id/stats")
    assert response.status_code == 401


def test_export_requires_auth(client):
    response = client.get("/documents/doc-id/export?format=markdown")
    assert response.status_code == 401


def test_user_stats_success(client):
    _create_test_document(client)
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        response = client.get("/analytics", headers=AUTH_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["total_documents"] >= 1
    assert "total_words" in body
    assert "total_versions" in body


def test_document_stats_success(client):
    doc_id = _create_test_document(client)
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        response = client.get(f"/documents/{doc_id}/stats", headers=AUTH_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["word_count"] == 0
    assert body["char_count"] == 0
    assert body["sentence_count"] == 0


def test_evaluate_document_success(client):
    doc_id = _create_test_document(client)
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        response = client.get(f"/documents/{doc_id}/evaluate", headers=AUTH_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert "flesch_reading_ease" in body
    assert "flesch_kincaid_grade" in body


def test_export_markdown_success(client):
    doc_id = _create_test_document(client)
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        response = client.get(f"/documents/{doc_id}/export?format=markdown", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert 'attachment; filename="' in response.headers["content-disposition"]
    assert "# Analytics Test" in response.text


def test_export_text_success(client):
    doc_id = _create_test_document(client)
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        response = client.get(f"/documents/{doc_id}/export?format=text", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "Analytics Test" in response.text


def test_html_export_escapes_title(client, isolated_analytics_repositories):
    isolated_analytics_repositories.title = '<img src=x onerror="alert(1)">'
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        response = client.get("/documents/analytics-test/export?format=html", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert "<img" not in response.text
    assert "&lt;img" in response.text


@pytest.mark.parametrize("href", ["javascript:alert(1)", "JaVaScRiPt:alert(1)", "java\nscript:alert(1)", "data:text/html,<script>alert(1)</script>", "//untrusted.example"])
def test_html_export_rejects_unsafe_links(href):
    content = {"type": "doc", "content": [{"type": "paragraph", "content": [
        {"type": "text", "text": "Read more", "marks": [{"type": "link", "attrs": {"href": href}}]}
    ]}]}
    html = prosemirror_to_html(content)
    assert "href=" not in html
    assert "Read more" in html


def test_html_export_preserves_safe_links():
    content = {"type": "doc", "content": [{"type": "paragraph", "content": [
        {"type": "text", "text": "Read more", "marks": [{"type": "link", "attrs": {"href": "https://example.com/?a=1&b=2"}}]}
    ]}]}
    assert 'href="https://example.com/?a=1&amp;b=2"' in prosemirror_to_html(content)


@pytest.mark.parametrize("level", [0, 7, "1><script>alert(1)</script><h1", None])
def test_html_export_validates_heading_level(level):
    content = {"type": "doc", "content": [{"type": "heading", "attrs": {"level": level},
        "content": [{"type": "text", "text": "Heading"}]}]}
    assert prosemirror_to_html(content) == "<h1>Heading</h1>\n"


def test_export_supports_unicode_filenames(client, isolated_analytics_repositories):
    isolated_analytics_repositories.title = "వ్యవసాయం"
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        response = client.get("/documents/analytics-test/export?format=text", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert "filename*=UTF-8''" in response.headers["content-disposition"]
    assert "వ్యవసాయం" in response.text


# --- DOCX / PDF export ---


def test_export_docx_success(client):
    doc_id = _create_test_document(client)
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        response = client.get(f"/documents/{doc_id}/export?format=docx", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert "wordprocessingml" in response.headers["content-type"]
    assert response.content[:2] == b"PK"
    assert response.headers["content-disposition"].endswith('filename*=UTF-8\'\'Analytics%20Test.docx')


def test_export_pdf_success(client):
    doc_id = _create_test_document(client)
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        response = client.get(f"/documents/{doc_id}/export?format=pdf", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert "application/pdf" in response.headers["content-type"]
    assert response.content[:4] == b"%PDF"


def _shared_document() -> DocumentModel:
    return DocumentModel(
        id="doc-1", owner_id="owner-uid", title="Shared Doc",
        content={"type": "doc", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "shared text"}]},
        ]},
    )


def test_export_allows_shared_collaborator(client):
    from app.models.collaborator import CollaboratorModel

    with patch("app.api.deps.verify_id_token", return_value={"uid": "viewer-uid", "email": "v@example.com"}), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = _shared_document()
        collab_repo.find.return_value = CollaboratorModel(
            id="c1", document_id="doc-1", user_id="viewer-uid", role="viewer"
        )
        for fmt in ("markdown", "html", "text", "docx", "pdf"):
            response = client.get(f"/documents/doc-1/export?format={fmt}", headers=AUTH_HEADERS)
            assert response.status_code == 200, fmt


def test_export_denies_stranger(client):
    with patch("app.api.deps.verify_id_token", return_value={"uid": "stranger-uid", "email": "s@example.com"}), patch(
        "app.services.permissions.document_repository"
    ) as doc_repo, patch(
        "app.services.permissions.collaborator_repository"
    ) as collab_repo:
        doc_repo.get.return_value = _shared_document()
        collab_repo.find.return_value = None
        response = client.get("/documents/doc-1/export?format=docx", headers=AUTH_HEADERS)
    assert response.status_code == 403


# --- Exporter unit coverage ---


def _rich_content():
    return {"type": "doc", "content": [
        {"type": "heading", "attrs": {"level": 2, "textAlign": "center"},
         "content": [{"type": "text", "text": "Intro"}]},
        {"type": "paragraph", "attrs": {"indent": 2}, "content": [
            {"type": "text", "text": "Bold", "marks": [{"type": "bold"}]},
            {"type": "text", "text": " link ", "marks": [{"type": "link", "attrs": {"href": "https://example.com"}}]},
            {"type": "text", "text": "evil", "marks": [{"type": "link", "attrs": {"href": "javascript:alert(1)"}}]},
            {"type": "hardBreak"},
            {"type": "text", "text": "tail", "marks": [{"type": "strike"}, {"type": "highlight", "attrs": {"color": "#ffee00"}}]},
        ]},
        {"type": "bulletList", "content": [
            {"type": "listItem", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Item"}]},
                {"type": "bulletList", "content": [
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Nested"}]}]},
                ]},
            ]},
        ]},
        {"type": "taskList", "content": [
            {"type": "taskItem", "attrs": {"checked": True}, "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Done"}]}]},
        ]},
        {"type": "blockquote", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "quoted"}]}]},
        {"type": "codeBlock", "content": [{"type": "text", "text": "a=1\nb=2"}]},
        {"type": "horizontalRule"},
        {"type": "table", "content": [
            {"type": "tableRow", "content": [
                {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "H"}]}]},
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "c"}]}]},
            ]},
        ]},
        {"type": "image", "attrs": {"src": "javascript:alert(1)", "alt": "diagram"}},
        {"type": "mysteryBlock", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "mystery"}]}]},
    ]}


def test_docx_export_roundtrip():
    import io as _io

    from docx import Document

    from app.utils.exporters import prosemirror_to_docx

    payload = prosemirror_to_docx("My <Title>", _rich_content())
    assert payload[:4] == b"PK\x03\x04"
    doc = Document(_io.BytesIO(payload))
    text = "\n".join(p.text for p in doc.paragraphs)
    for expected in ("My <Title>", "Intro", "Bold", "link", "evil", "tail", "Item", "Nested", "Done", "quoted", "a=1", "mystery"):
        assert expected in text, expected
    assert "javascript:" not in text
    assert len(doc.tables) == 1


def test_pdf_export_renders_without_error():
    from app.utils.exporters import prosemirror_to_pdf

    payload = prosemirror_to_pdf("My <Title>", _rich_content())
    assert payload[:4] == b"%PDF"
    assert len(payload) > 1000
