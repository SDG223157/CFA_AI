from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Protocol

import httpx


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMClient(Protocol):
    def name(self) -> str: ...

    def chat(self, messages: list[ChatMessage]) -> str: ...


class NoopClient:
    def name(self) -> str:
        return "stub"

    def chat(self, messages: list[ChatMessage]) -> str:
        # Deterministic, safe fallback.
        user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return (
            "AI is not configured (no provider credentials found).\n\n"
            "Here’s a structured non-AI suggestion based on your prompt:\n"
            f"- What you asked: {user[:800]}\n"
            "- Next steps: Configure `OPENAI_API_KEY` or `OLLAMA_BASE_URL` + `OLLAMA_MODEL` to enable real insights."
        )


class OpenAIClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = "https://api.openai.com/v1",
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._extra_headers = extra_headers or {}

    def name(self) -> str:
        return f"openai:{self._model}"

    def chat(self, messages: list[ChatMessage]) -> str:
        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {self._api_key}", **self._extra_headers}

        with httpx.Client(timeout=60) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]


class OllamaClient:
    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    def name(self) -> str:
        return f"ollama:{self._model}"

    def chat(self, messages: list[ChatMessage]) -> str:
        url = f"{self._base_url}/api/chat"
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
        }
        with httpx.Client(timeout=120) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        # Ollama returns {message: {role, content}, ...}
        msg = data.get("message", {})
        return str(msg.get("content", "")).strip()


def build_default_client(
    *,
    openai_api_key: str | None,
    openai_model: str,
    openrouter_api_key: str | None,
    openrouter_model: str,
    openrouter_base_url: str,
    ollama_base_url: str,
    ollama_model: str,
) -> LLMClient:
    if openrouter_api_key:
        # OpenRouter is OpenAI-compatible. Optional headers are recommended by OpenRouter.
        # https://openrouter.ai/docs
        extra = {}
        referer = os.getenv("OPENROUTER_HTTP_REFERER", "").strip()
        title = os.getenv("OPENROUTER_X_TITLE", "").strip()
        if referer:
            extra["HTTP-Referer"] = referer
        if title:
            extra["X-Title"] = title
        return OpenAIClient(
            api_key=openrouter_api_key,
            model=openrouter_model,
            base_url=openrouter_base_url,
            extra_headers=extra,
        )

    if openai_api_key:
        return OpenAIClient(api_key=openai_api_key, model=openai_model)

    # Allow explicit disable
    if os.getenv("DISABLE_OLLAMA", "").strip().lower() in {"1", "true", "yes"}:
        return NoopClient()

    # Ollama is optional; if not running, UI will show error on call.
    return OllamaClient(base_url=ollama_base_url, model=ollama_model)


