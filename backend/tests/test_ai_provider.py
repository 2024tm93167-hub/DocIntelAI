from unittest.mock import patch

import httpx
import pytest

from app.config.settings import Settings
from app.services.ai_provider import OllamaProvider, OpenAIProvider
from app.utils.exceptions import AIProviderError


@pytest.mark.parametrize("provider_type,body,expected", [
    (OllamaProvider, '{"response":"Hello"}\n{"response":" world","done":true}\n', "Hello world"),
    (OpenAIProvider, 'data: {"choices":[{"delta":{"reasoning":"private"}}]}\n\ndata: {"choices":[{"delta":{"content":"Hello"}}]}\n\ndata: [DONE]\n\n', "Hello"),
])
async def test_provider_streams_content_only(provider_type, body, expected):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=body))
    client = httpx.AsyncClient(transport=transport)
    provider = provider_type(Settings(_env_file=None))
    with patch("app.services.ai_provider.httpx.AsyncClient", return_value=client):
        chunks = [chunk async for chunk in provider.generate_stream("System", "Prompt")]
    assert "".join(chunks) == expected
    assert client.is_closed


@pytest.mark.parametrize("provider_type,body", [
    (OllamaProvider, '{"response":"Partial"}\n'),
    (OllamaProvider, '{"error":"private error"}\n'),
    (OpenAIProvider, 'data: {"choices":[{"delta":{"content":"Partial"}}]}\n\n'),
    (OpenAIProvider, 'data: {"error":{"message":"private error"}}\n\n'),
])
async def test_provider_rejects_truncated_and_error_streams(provider_type, body):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=body))
    client = httpx.AsyncClient(transport=transport)
    provider = provider_type(Settings(_env_file=None))
    with patch("app.services.ai_provider.httpx.AsyncClient", return_value=client):
        with pytest.raises(AIProviderError):
            async for _ in provider.generate_stream("System", "Prompt"):
                pass
    assert client.is_closed
