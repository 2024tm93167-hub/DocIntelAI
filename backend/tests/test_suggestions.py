from unittest.mock import AsyncMock, MagicMock, patch
import json

import pytest

from app.models.document import DocumentModel, EMPTY_DOCUMENT_CONTENT
from app.models.suggestion import SuggestionModel

FAKE_DECODED_TOKEN = {"uid": "owner-uid", "email": "owner@example.com", "name": "Owner"}
AUTH_HEADERS = {"Authorization": "Bearer good-token"}


def _make_document(**overrides) -> DocumentModel:
    defaults = dict(
        id="doc-1", owner_id="owner-uid", title="Doc", content=dict(EMPTY_DOCUMENT_CONTENT),
        word_count=0, revision=2, created_at=None, updated_at=None,
    )
    defaults.update(overrides)
    return DocumentModel(**defaults)


def _make_suggestion(**overrides) -> SuggestionModel:
    defaults = dict(
        id="sug-1", document_id="doc-1", user_id="owner-uid", type="grammar",
        original_text="hello", suggested_text="Hello", reason="Capitalize",
        status="pending", document_revision=2, created_at=None,
    )
    defaults.update(overrides)
    return SuggestionModel(**defaults)


@pytest.mark.parametrize("result,expected", [
    ({"suggestions": []}, 200),
    ({"suggestions": [{"type": "grammar", "original": "He go", "suggested": "He went", "reason": "Past tense"}]}, 200),
    ({"suggestions": [{"type": "grammar", "original": "not in passage", "suggested": "He went", "reason": "Past tense"}]}, 502),
    ({"suggestions": [{"type": "invented"}]}, 502),
])
def test_analyze_validates_and_persists(client, result, expected):
    doc = _make_document(content={"type": "doc", "content": [{"type": "paragraph", "content": [
        {"type": "text", "text": "He go to the market yesterday and buy many thing."}]}]})
    provider = AsyncMock()
    provider.generate.return_value = json.dumps(result)
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.suggestions.require_editor", return_value=(doc, "owner")
    ), patch("app.api.routers.suggestions.get_ai_provider", return_value=provider), patch(
        "app.api.routers.suggestions.suggestion_repository.create", return_value=_make_suggestion()
    ) as create:
        response = client.post("/documents/doc-1/suggestions/analyze", json={"base_revision": 2}, headers=AUTH_HEADERS)
    assert response.status_code == expected
    assert create.call_count == (len(result["suggestions"]) if expected == 200 else 0)


def test_analyze_rejects_cross_paragraph_original(client):
    doc = _make_document(content={"type": "doc", "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "First part."}]},
        {"type": "paragraph", "content": [{"type": "text", "text": "Second part."}]},
    ]})
    provider = AsyncMock()
    provider.generate.return_value = json.dumps({"suggestions": [
        {"type": "grammar", "original": "First part.\nSecond part.", "suggested": "Fixed.", "reason": "x"}]})
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.suggestions.require_editor", return_value=(doc, "owner")
    ), patch("app.api.routers.suggestions.get_ai_provider", return_value=provider), patch(
        "app.api.routers.suggestions.suggestion_repository.create"
    ) as create:
        response = client.post("/documents/doc-1/suggestions/analyze", json={"base_revision": 2}, headers=AUTH_HEADERS)
    assert response.status_code == 502
    create.assert_not_called()


def test_analyze_requires_auth(client):
    assert client.post("/documents/doc-1/suggestions/analyze", json={"base_revision": 2}).status_code == 401


def test_replacement_preserves_marks_and_other_paragraphs():
    from app.repositories.suggestion_repository import replace_suggested_text
    content = {"type": "doc", "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "He "},
          {"type": "text", "text": "go", "marks": [{"type": "bold"}]}, {"type": "text", "text": " yesterday."}]},
        {"type": "paragraph", "content": [{"type": "text", "text": "Unchanged."}]},
    ]}
    result = replace_suggested_text(content, "go yesterday", "went yesterday")
    assert result["content"][0]["content"][1] == {"type": "text", "text": "went yesterday", "marks": [{"type": "bold"}]}
    assert result["content"][1] == content["content"][1]
    assert content["content"][0]["content"][1]["text"] == "go"


@pytest.mark.parametrize("original", ["", "absent", "He"])
def test_replacement_rejects_missing_or_ambiguous_spans(original):
    from app.repositories.suggestion_repository import replace_suggested_text
    from app.utils.exceptions import ConflictError
    content = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "He said He"}]}]}
    with pytest.raises(ConflictError):
        replace_suggested_text(content, original, "They")


@pytest.fixture()
def application_transaction():
    document_data = {"ownerId": "owner-uid", "title": "Doc", "revision": 2, "content": {
        "type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "He go yesterday."}]}]}}
    suggestion_data = {"documentId": "doc-1", "userId": "owner-uid", "type": "grammar", "status": "pending",
                       "originalText": "He go", "suggestedText": "He went", "documentRevision": 2}
    doc_ref, sug_ref, transaction = MagicMock(), MagicMock(), MagicMock()
    doc_ref.get.return_value.to_dict.return_value = document_data
    sug_ref.get.return_value.to_dict.return_value = suggestion_data
    with patch("app.repositories.suggestion_repository.documents_collection") as docs, patch(
        "app.repositories.suggestion_repository.suggestions_collection"
    ) as suggestions, patch("app.repositories.suggestion_repository.get_firestore") as db, patch(
        "app.repositories.suggestion_repository.versions_collection"
    ), patch("google.cloud.firestore.transactional", side_effect=lambda callback: callback):
        docs.return_value.document.return_value = doc_ref
        suggestions.return_value.document.return_value = sug_ref
        db.return_value.transaction.return_value = transaction
        yield document_data, suggestion_data, transaction


def test_application_transaction_updates_document_status_and_checkpoint(application_transaction):
    from app.repositories.suggestion_repository import SuggestionRepository
    data, _, transaction = application_transaction
    document, suggestion = SuggestionRepository().apply("doc-1", "sug-1", "owner-uid", 2)
    assert document.revision == 3
    assert document.content["content"][0]["content"][0]["text"] == "He went"
    assert suggestion.status == "accepted"
    assert transaction.set.call_args.args[1]["content"] == data["content"]
    assert transaction.update.call_count == 2


@pytest.mark.parametrize("change", ["revision", "resolved", "wrong_document", "wrong_user"])
def test_application_rejects_stale_or_unauthorized_without_writes(application_transaction, change):
    from app.repositories.suggestion_repository import SuggestionRepository
    from app.utils.exceptions import ConflictError, PermissionDeniedError
    data, suggestion, transaction = application_transaction
    if change == "revision": data["revision"] = 3
    if change == "resolved": suggestion["status"] = "accepted"
    if change == "wrong_document": suggestion["documentId"] = "other"
    if change == "wrong_user": suggestion["userId"] = "other"
    with pytest.raises((ConflictError, PermissionDeniedError)):
        SuggestionRepository().apply("doc-1", "sug-1", "owner-uid", 2)
    transaction.set.assert_not_called()
    transaction.update.assert_not_called()


def test_application_checkpoint_failure_prevents_document_and_status_writes(application_transaction):
    from app.repositories.suggestion_repository import SuggestionRepository
    _, _, transaction = application_transaction
    transaction.set.side_effect = RuntimeError("checkpoint failed")
    with pytest.raises(RuntimeError):
        SuggestionRepository().apply("doc-1", "sug-1", "owner-uid", 2)
    transaction.update.assert_not_called()


def test_apply_requires_auth(client):
    assert client.post("/documents/doc-1/suggestions/sug-1/apply", json={"base_revision": 2}).status_code == 401


def test_create_suggestion_requires_auth(client):
    assert client.post("/documents/doc-1/suggestions", json={"type": "grammar"}).status_code == 401


def test_create_suggestion_success(client):
    fake_doc = _make_document(revision=3)
    fake_suggestion = _make_suggestion(document_revision=3)
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.suggestions.require_editor", return_value=(fake_doc, "owner")
    ), patch(
        "app.api.routers.suggestions.suggestion_repository.create", return_value=fake_suggestion
    ) as create:
        response = client.post(
            "/documents/doc-1/suggestions",
            json={"type": "grammar", "original_text": "hello", "suggested_text": "Hello", "reason": "Capitalize"},
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["document_revision"] == 3
    assert create.call_args.kwargs["document_revision"] == 3


def test_list_suggestions_filters_by_status(client):
    pending = _make_suggestion(id="s1", status="pending")
    accepted = _make_suggestion(id="s2", status="accepted")
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.suggestions.require_viewer", return_value=(_make_document(), "owner")
    ), patch(
        "app.api.routers.suggestions.suggestion_repository.list_by_document", return_value=[pending]
    ) as list_fn:
        response = client.get("/documents/doc-1/suggestions?status=pending", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert list_fn.call_args.args[2] == "pending"


def test_list_suggestions_rejects_invalid_status(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        response = client.get("/documents/doc-1/suggestions?status=invalid", headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_accept_suggestion_requires_base_revision(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.suggestions.require_editor", return_value=(_make_document(), "owner")
    ), patch(
        "app.api.routers.suggestions.suggestion_repository.update_status",
        side_effect=__import__("app.utils.exceptions", fromlist=["ValidationFailedError"]).ValidationFailedError("base_revision is required to accept a suggestion.")
    ):
        response = client.patch(
            "/documents/doc-1/suggestions/sug-1",
            json={"status": "accepted"}, headers=AUTH_HEADERS,
        )
    assert response.status_code == 422


def test_accept_suggestion_rejects_stale_document(client):
    from app.utils.exceptions import ConflictError
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.suggestions.require_editor", return_value=(_make_document(), "owner")
    ), patch(
        "app.api.routers.suggestions.suggestion_repository.update_status",
        side_effect=ConflictError("The document changed after this suggestion was created.")
    ):
        response = client.patch(
            "/documents/doc-1/suggestions/sug-1",
            json={"status": "accepted", "base_revision": 1}, headers=AUTH_HEADERS,
        )
    assert response.status_code == 409


def test_accept_suggestion_success(client):
    accepted = _make_suggestion(status="accepted", resolved_by="owner-uid")
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.suggestions.require_editor", return_value=(_make_document(), "owner")
    ), patch(
        "app.api.routers.suggestions.suggestion_repository.update_status", return_value=accepted
    ) as update:
        response = client.patch(
            "/documents/doc-1/suggestions/sug-1",
            json={"status": "accepted", "base_revision": 2}, headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert update.call_args.kwargs["base_revision"] == 2


def test_reject_suggestion_success(client):
    rejected = _make_suggestion(status="rejected", resolved_by="owner-uid")
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.suggestions.require_editor", return_value=(_make_document(), "owner")
    ), patch(
        "app.api.routers.suggestions.suggestion_repository.update_status", return_value=rejected
    ) as update:
        response = client.patch(
            "/documents/doc-1/suggestions/sug-1",
            json={"status": "rejected"}, headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert update.call_args.kwargs["base_revision"] is None


def test_cannot_resolve_already_resolved_suggestion(client):
    from app.utils.exceptions import ConflictError
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.suggestions.require_editor", return_value=(_make_document(), "owner")
    ), patch(
        "app.api.routers.suggestions.suggestion_repository.update_status",
        side_effect=ConflictError("This suggestion has already been resolved.")
    ):
        response = client.patch(
            "/documents/doc-1/suggestions/sug-1",
            json={"status": "accepted", "base_revision": 2}, headers=AUTH_HEADERS,
        )
    assert response.status_code == 409


def test_delete_suggestion_success(client):
    suggestion = _make_suggestion()
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.suggestions.require_editor", return_value=(_make_document(), "owner")
    ), patch(
        "app.api.routers.suggestions.suggestion_repository.get", return_value=suggestion
    ), patch(
        "app.api.routers.suggestions.suggestion_repository.delete"
    ) as delete:
        response = client.delete("/documents/doc-1/suggestions/sug-1", headers=AUTH_HEADERS)
    assert response.status_code == 204
    delete.assert_called_once_with("sug-1")


def test_delete_suggestion_forbidden_for_other_user(client):
    suggestion = _make_suggestion(user_id="someone-else")
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.suggestions.require_editor", return_value=(_make_document(), "owner")
    ), patch(
        "app.api.routers.suggestions.suggestion_repository.get", return_value=suggestion
    ):
        response = client.delete("/documents/doc-1/suggestions/sug-1", headers=AUTH_HEADERS)
    assert response.status_code == 403
