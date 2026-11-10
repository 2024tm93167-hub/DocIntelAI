"""Pluggable AI provider layer for text generation."""
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config.settings import Settings, get_settings
from app.utils.exceptions import AIProviderError


class AIProvider(ABC):
    """Abstract interface for generating text from a prompt."""

    @abstractmethod
    async def generate(self, system: str, prompt: str, json_mode: bool = False) -> str:
        """Return the model's response to the given prompt.

        When ``json_mode`` is true, providers that support structured output are
        asked to emit valid JSON (Ollama ``format: "json"``, OpenAI-compatible
        ``response_format: {"type": "json_object"}``).
        """

    @abstractmethod
    def generate_stream(self, system: str, prompt: str) -> AsyncIterator[str]:
        """Yield the model's response to the given prompt in chunks."""


class OllamaProvider(AIProvider):
    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.temperature = settings.ai_temperature
        self.timeout = settings.ai_timeout_seconds

    async def generate(self, system: str, prompt: str, json_mode: bool = False) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        if json_mode:
            payload["format"] = "json"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "").strip()
        except httpx.HTTPStatusError as exc:
            raise AIProviderError(f"Ollama returned an error: {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            raise AIProviderError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc
        except Exception as exc:
            raise AIProviderError(f"Unexpected Ollama error: {exc}") from exc

    async def generate_stream(self, system: str, prompt: str) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": True,
            "options": {"temperature": self.temperature},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/generate", json=payload
                ) as response:
                    response.raise_for_status()
                    completed = False
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        if data.get("error"):
                            raise AIProviderError("Ollama could not complete generation")
                        chunk = data.get("response", "")
                        if chunk:
                            yield chunk
                        if data.get("done"):
                            completed = True
                            break
                    if not completed:
                        raise AIProviderError("Ollama stream ended before completion")
        except httpx.HTTPStatusError as exc:
            raise AIProviderError(f"Ollama returned an error: {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            raise AIProviderError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc
        except AIProviderError:
            raise
        except Exception as exc:
            raise AIProviderError(f"Unexpected Ollama error: {exc}") from exc


class OpenAIProvider(AIProvider):
    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.openai_base_url.rstrip("/")
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.temperature = settings.ai_temperature
        self.timeout = settings.ai_timeout_seconds

    async def generate(self, system: str, prompt: str, json_mode: bool = False) -> str:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
        except httpx.HTTPStatusError as exc:
            raise AIProviderError(f"OpenAI provider returned an error: {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            raise AIProviderError(f"Could not reach OpenAI provider: {exc}") from exc
        except Exception as exc:
            raise AIProviderError(f"Unexpected OpenAI error: {exc}") from exc

    async def generate_stream(self, system: str, prompt: str) -> AsyncIterator[str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    completed = False
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            completed = True
                            break
                        data = json.loads(data_str)
                        if data.get("error"):
                            raise AIProviderError("AI provider could not complete generation")
                        choices = data.get("choices") or []
                        if not choices:
                            continue
                        chunk = choices[0].get("delta", {}).get("content")
                        if chunk:
                            yield chunk
                    if not completed:
                        raise AIProviderError("AI stream ended before completion")
        except httpx.HTTPStatusError as exc:
            raise AIProviderError(f"OpenAI provider returned an error: {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            raise AIProviderError(f"Could not reach OpenAI provider: {exc}") from exc
        except AIProviderError:
            raise
        except Exception as exc:
            raise AIProviderError(f"Unexpected OpenAI error: {exc}") from exc


def get_ai_provider(settings: Settings | None = None) -> AIProvider:
    settings = settings or get_settings()
    if settings.ai_provider == "openai":
        return OpenAIProvider(settings)
    return OllamaProvider(settings)
