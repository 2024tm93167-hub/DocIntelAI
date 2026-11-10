import json
from unittest.mock import AsyncMock, patch

import pytest

from app.utils.exceptions import AIProviderError

FAKE_DECODED_TOKEN = {"uid": "owner-uid", "email": "owner@example.com", "name": "Owner"}
AUTH_HEADERS = {"Authorization": "Bearer good-token"}


def test_rewrite_requires_auth(client):
    response = client.post("/ai/rewrite", json={"text": "Hello"})
    assert response.status_code == 401


def test_summarize_requires_auth(client):
    response = client.post("/ai/summarize", json={"text": "Hello world", "max_words": 50})
    assert response.status_code == 401


def test_generate_requires_auth(client):
    response = client.post("/ai/generate", json={"prompt": "Write about agriculture"})
    assert response.status_code == 401


async def test_rewrite_success(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.ai.get_ai_provider"
    ) as mock_get_provider:
        provider = AsyncMock()
        provider.generate.return_value = "Greetings."
        mock_get_provider.return_value = provider

        response = client.post(
            "/ai/rewrite",
            json={"text": "Hello", "instruction": "make formal"},
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["output"] == "Greetings."


async def test_summarize_success(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.ai.get_ai_provider"
    ) as mock_get_provider:
        provider = AsyncMock()
        provider.generate.return_value = "A greeting."
        mock_get_provider.return_value = provider

        response = client.post(
            "/ai/summarize",
            json={"text": "Hello world, this is a test.", "max_words": 10},
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["output"] == "A greeting."


async def test_generate_success(client):
    async def fake_stream(system, prompt):
        yield "Agriculture "
        yield "feeds the world."

    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.ai.get_ai_provider"
    ) as mock_get_provider:
        provider = AsyncMock()
        provider.generate_stream = lambda system, prompt: fake_stream(system, prompt)
        mock_get_provider.return_value = provider

        response = client.post(
            "/ai/generate",
            json={"prompt": "Write about agriculture in 100 words"},
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200
    assert response.text == "Agriculture feeds the world."


@pytest.mark.parametrize("fail_after_chunk", [False, True])
def test_generate_event_stream_reports_completion_or_error(client, fail_after_chunk):
    async def fake_stream(system, prompt):
        yield "Hello\nworld"
        if fail_after_chunk:
            raise AIProviderError("private provider error")

    provider = AsyncMock()
    provider.generate_stream = fake_stream
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.ai.get_ai_provider", return_value=provider
    ):
        response = client.post("/ai/generate", json={"prompt": "Write a greeting"},
            headers={**AUTH_HEADERS, "Accept": "application/x-ndjson"})
    assert response.status_code == 200
    assert "application/x-ndjson" in response.headers["content-type"]
    events = [json.loads(line) for line in response.text.splitlines()]
    if fail_after_chunk:
        assert all(event["type"] != "delta" for event in events)
    else:
        assert events[0] == {"type": "delta", "text": "Hello\nworld"}
    assert events[-1]["type"] == ("error" if fail_after_chunk else "done")
    assert "private provider error" not in response.text


def test_generate_empty_stream_is_not_success(client):
    async def fake_stream(system, prompt):
        if False:
            yield ""

    provider = AsyncMock()
    provider.generate_stream = fake_stream
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.ai.get_ai_provider", return_value=provider
    ):
        response = client.post("/ai/generate", json={"prompt": "Write a greeting"}, headers=AUTH_HEADERS)
    assert response.status_code == 502


def test_generate_rejects_blank_prompt(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        response = client.post("/ai/generate", json={"prompt": "   \n "}, headers=AUTH_HEADERS)
    assert response.status_code == 422
