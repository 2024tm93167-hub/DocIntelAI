from unittest.mock import AsyncMock, patch

import pytest

from app.services import ai_actions
from app.utils.exceptions import ValidationFailedError


@pytest.mark.parametrize("output", ["Document title: About me\nText: hello", "Text before selection:\nhello", "", "Context: private"])
def test_writing_rejects_metadata(output):
    from app.utils.exceptions import AIProviderError
    with pytest.raises(AIProviderError):
        ai_actions.clean_writing(output)


def test_writing_removes_outer_fence_without_changing_prose():
    assert ai_actions.clean_writing("```text\nHello world.\n```") == "Hello world."


@pytest.mark.parametrize("output,expected", [
    ('{"titles":["First title","Second title","Third title"]}', 200),
    ('{"titles":["Only one"]}', 502),
    ('Here are some titles', 502),
    ('{"titles":["Text: bad","Second","Third"]}', 502),
])
def test_title_schema_validation(client, output, expected):
    provider = AsyncMock()
    provider.generate.return_value = output
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.ai.get_ai_provider", return_value=provider
    ):
        response = client.post("/ai/titles", json={"text": "A passage"}, headers=AUTH_HEADERS)
    assert response.status_code == expected


def test_echoed_provider_context_is_not_returned(client):
    provider = AsyncMock()
    provider.generate.return_value = "Document title: About me\nText before selection:\nprivate\nText:\nhello"
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.ai.get_ai_provider", return_value=provider
    ):
        response = client.post("/ai/action", json={"action": "improve", "text": "hello"}, headers=AUTH_HEADERS)
    assert response.status_code == 502
    assert "private" not in response.text


def test_supported_actions_includes_new_actions():
    actions = ai_actions.supported_actions()
    for name in ("rewrite", "improve", "expand", "condense", "summarize",
                 "grammar", "tone", "continue", "outline", "custom", "generate"):
        assert name in actions


def test_get_spec_returns_label_and_needs_text():
    assert ai_actions.get_spec("generate").needs_text is False
    assert ai_actions.get_spec("outline").needs_text is False
    assert ai_actions.get_spec("rewrite").needs_text is True
    assert ai_actions.get_spec("grammar").label == "Fix grammar"


def test_get_spec_rejects_unknown_action():
    with pytest.raises(ValidationFailedError):
        ai_actions.get_spec("translate")


def test_build_prompt_requires_text_for_text_actions():
    with pytest.raises(ValidationFailedError):
        ai_actions.build_prompt("rewrite", text="")


def test_build_prompt_does_not_require_text_for_generate():
    prompt = ai_actions.build_prompt("generate", prompt="Write about agriculture")
    assert "Request: Write about agriculture" in prompt


def test_build_prompt_includes_context_when_supplied():
    prompt = ai_actions.build_prompt(
        "improve", text="Hello", document_title="Greetings", before="Hi", after="World",
    )
    assert "Document title: Greetings" in prompt
    assert "Text before selection:" in prompt
    assert "Text after selection:" in prompt
    assert "Text:\nHello" in prompt


def test_build_prompt_truncates_long_context():
    long = "x" * 10000
    prompt = ai_actions.build_prompt("improve", text="Hi", before=long)
    assert len(prompt) < len(long) + 500


def test_build_prompt_tone_validates_value():
    with pytest.raises(ValidationFailedError):
        ai_actions.build_prompt("tone", text="Hi", tone="sarcastic")
    prompt = ai_actions.build_prompt("tone", text="Hi", tone="professional")
    assert "Tone: professional" in prompt


def test_build_prompt_summarize_includes_max_words():
    prompt = ai_actions.build_prompt("summarize", text="Hello world", max_words=50)
    assert "Maximum words: 50" in prompt


def test_build_prompt_rejects_oversized_text():
    with pytest.raises(ValidationFailedError):
        ai_actions.build_prompt("rewrite", text="x" * (ai_actions.MAX_TEXT_CHARS + 1))


@pytest.mark.parametrize("action,prompt,instruction,expected", [
    ("generate", "write 2 pages about farming", "", "at least 1000 words"),
    ("generate", "write a page on soil health", "", "at least 500 words"),
    ("generate", "draft a 1500 word essay", "", "at least 1500 words"),
    ("custom", "", "expand to 3 pages", "at least 1500 words"),
    ("generate", "write about farming", "", "Request:"),
])
def test_build_prompt_translates_length_requests(action, prompt, instruction, expected):
    built = ai_actions.build_prompt(
        action, prompt=prompt, instruction=instruction, text="seed" if action != "generate" else "")
    assert expected in built


FAKE_DECODED_TOKEN = {"uid": "owner-uid", "email": "owner@example.com", "name": "Owner"}
AUTH_HEADERS = {"Authorization": "Bearer good-token"}


def test_list_actions_requires_auth(client):
    assert client.get("/ai/actions").status_code == 401


def test_list_actions_returns_metadata(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        response = client.get("/ai/actions", headers=AUTH_HEADERS)
    assert response.status_code == 200
    body = response.json()
    names = {item["action"] for item in body}
    assert {"grammar", "tone", "continue", "outline", "generate"} <= names
    generate = next(item for item in body if item["action"] == "generate")
    assert generate["needs_text"] is False
    assert generate["label"] == "Generate"


def test_run_action_requires_auth(client):
    assert client.post("/ai/action", json={"action": "grammar", "text": "Hi"}).status_code == 401


async def test_run_action_grammar_success(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.ai.get_ai_provider"
    ) as mock_get_provider:
        provider = AsyncMock()
        provider.generate.return_value = "Hello, world."
        mock_get_provider.return_value = provider
        response = client.post(
            "/ai/action",
            json={"action": "grammar", "text": "hello world"},
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    assert response.json()["output"] == "Hello, world."
    args, kwargs = provider.generate.await_args
    system, prompt = args
    assert "proofreader" in system.lower()
    assert "hello world" in prompt


async def test_run_action_tone_uses_tone_value(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.ai.get_ai_provider"
    ) as mock_get_provider:
        provider = AsyncMock()
        provider.generate.return_value = "Greetings."
        mock_get_provider.return_value = provider
        response = client.post(
            "/ai/action",
            json={"action": "tone", "text": "hi", "tone": "professional"},
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    _, prompt = provider.generate.await_args.args
    assert "Tone: professional" in prompt


def test_run_action_rejects_unknown_action(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        response = client.post(
            "/ai/action", json={"action": "translate", "text": "hi"}, headers=AUTH_HEADERS
        )
    assert response.status_code == 422


def test_run_action_rejects_text_action_without_text(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        response = client.post(
            "/ai/action", json={"action": "rewrite", "text": ""}, headers=AUTH_HEADERS
        )
    assert response.status_code == 422


def test_run_action_rejects_invalid_tone(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN):
        response = client.post(
            "/ai/action", json={"action": "tone", "text": "hi", "tone": "sarcastic"},
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 422


async def test_existing_rewrite_endpoint_still_works(client):
    with patch("app.api.deps.verify_id_token", return_value=FAKE_DECODED_TOKEN), patch(
        "app.api.routers.ai.get_ai_provider"
    ) as mock_get_provider:
        provider = AsyncMock()
        provider.generate.return_value = "Greetings."
        mock_get_provider.return_value = provider
        response = client.post(
            "/ai/rewrite", json={"text": "Hello", "instruction": "make formal"},
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    assert response.json()["output"] == "Greetings."
