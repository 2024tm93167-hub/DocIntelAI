from unittest.mock import patch

import pytest

from app.models.document import DocumentModel, EMPTY_DOCUMENT_CONTENT
from app.models.version import VersionModel

FAKE_DECODED_TOKEN = {"uid": "owner-uid", "email": "owner@example.com", "name": "Owner"}
AUTH_HEADERS = {"Authorization": "Bearer good-token"}


def _make_document(**overrides) -> DocumentModel:
    defaults = dict(
        id="doc-1",
        owner_id="owner-uid",
        title="Untitled Document",
        content=dict(EMPTY_DOCUMENT_CONTENT),
        word_count=0,
        created_at=None,
        updated_at=None,
    )
    defaults.update(overrides)
    return DocumentModel(**defaults)


def _make_version(**overrides) -> VersionModel:
    defaults = dict(
        id="ver-1",
        document_id="doc-1",
        owner_id="owner-uid",
        title="Untitled Document",
        content=dict(EMPTY_DOCUMENT_CONTENT),
        word_count=0,
        label=None,
        created_at=None,
    )
    defaults.update(overrides)
    return VersionModel(**defaults)


def test_create_version_requires_auth(client):
    response = client.post("/documents/doc-1/versions", json={})
    assert response.status_code == 401


def test_create_version_success(client):
    fake_doc = _make_document(title="My Doc", word_count=12)
    fake_version = _make_version(title="My Doc", word_count=12, label="Draft v1")
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.versions.require_editor", return_value=(fake_doc, "owner")
    ), patch(
        "app.api.routers.versions.version_repository.create", return_value=fake_version
    ) as mock_create:
        response = client.post(
            "/documents/doc-1/versions", json={"label": "Draft v1"}, headers=AUTH_HEADERS
        )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "ver-1"
    assert body["document_id"] == "doc-1"
    assert body["title"] == "My Doc"
    assert body["label"] == "Draft v1"
    assert body["content"] == EMPTY_DOCUMENT_CONTENT
    mock_create.assert_called_once()


def test_create_version_rejects_stale_revision(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.versions.require_editor", return_value=(_make_document(revision=3), "owner")
    ), patch("app.api.routers.versions.version_repository.create") as create:
        response = client.post("/documents/doc-1/versions", json={"label": "Draft", "base_revision": 2}, headers=AUTH_HEADERS)
    assert response.status_code == 409
    create.assert_not_called()


def test_create_version_captures_matching_revision(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.versions.require_editor", return_value=(_make_document(revision=3), "owner")
    ), patch("app.api.routers.versions.version_repository.create", return_value=_make_version(document_revision=3)) as create:
        response = client.post("/documents/doc-1/versions", json={"label": "Draft", "base_revision": 3}, headers=AUTH_HEADERS)
    assert response.status_code == 201
    assert create.call_args.kwargs["document_revision"] == 3


@pytest.mark.parametrize("revision", [-1, "3", True])
def test_create_version_rejects_invalid_revision(client, revision):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        response = client.post("/documents/doc-1/versions", json={"base_revision": revision}, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_list_versions_success(client):
    versions = [_make_version(id="ver-1"), _make_version(id="ver-2", title="Renamed")]
    fake_doc = _make_document()
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.versions.require_viewer", return_value=(fake_doc, "owner")
    ), patch("app.api.routers.versions.version_repository.list_by_document", return_value=versions):
        response = client.get("/documents/doc-1/versions", headers=AUTH_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert "content" not in body[0]


def test_get_version_success(client):
    fake_version = _make_version()
    fake_doc = _make_document()
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.versions.require_viewer", return_value=(fake_doc, "owner")
    ), patch("app.api.routers.versions.version_repository.get", return_value=fake_version):
        response = client.get("/documents/doc-1/versions/ver-1", headers=AUTH_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "ver-1"
    assert body["content"] == EMPTY_DOCUMENT_CONTENT


def test_get_version_forbidden_for_other_document(client):
    other_version = _make_version(document_id="doc-2")
    fake_doc = _make_document()
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.versions.require_viewer", return_value=(fake_doc, "owner")
    ), patch("app.api.routers.versions.version_repository.get", return_value=other_version):
        response = client.get("/documents/doc-1/versions/ver-1", headers=AUTH_HEADERS)

    assert response.status_code == 403


def test_delete_version_success(client):
    fake_version = _make_version()
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.versions.require_owner", return_value=_make_document()
    ), patch(
        "app.api.routers.versions.version_repository.get", return_value=fake_version
    ), patch(
        "app.api.routers.versions.version_repository.delete", return_value=None
    ) as mock_delete:
        response = client.delete("/documents/doc-1/versions/ver-1", headers=AUTH_HEADERS)

    assert response.status_code == 204
    mock_delete.assert_called_once_with("ver-1")


def test_diff_version_against_current(client):
    old_version = _make_version(
        content={
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Hello"}]}
            ],
        },
        word_count=1,
    )
    current_doc = _make_document(
        content={
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Hello world"}]}
            ],
        },
        word_count=2,
    )
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.versions.require_viewer", return_value=(current_doc, "owner")
    ), patch(
        "app.api.routers.versions.version_repository.get", return_value=old_version
    ):
        response = client.get("/documents/doc-1/versions/ver-1/diff", headers=AUTH_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["from_version_id"] == "ver-1"
    assert body["to_version_id"] is None
    assert any(c["op"] == "insert" for c in body["chunks"])


def test_diff_version_against_version(client):
    from_version = _make_version(
        id="ver-1",
        content={
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Hello"}]}
            ],
        },
        word_count=1,
    )
    to_version = _make_version(
        id="ver-2",
        content={
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Hello world"}]}
            ],
        },
        word_count=2,
    )
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.versions.require_viewer", return_value=(_make_document(), "owner")
    ), patch(
        "app.api.routers.versions.version_repository.get",
        side_effect=[from_version, to_version],
    ):
        response = client.get(
            "/documents/doc-1/versions/ver-1/diff?compare_to=ver-2", headers=AUTH_HEADERS
        )

    assert response.status_code == 200
    body = response.json()
    assert body["from_version_id"] == "ver-1"
    assert body["to_version_id"] == "ver-2"
