"""
Unified LLM service — Gemini / Groq / OpenAI
Provider is set at runtime via POST /api/settings/llm
"""
from __future__ import annotations
import os
from typing import AsyncGenerator, Literal

from loguru import logger

LLMProvider = Literal["gemini", "groq", "openai"]

PROVIDER_MODELS: dict[LLMProvider, str] = {
    "gemini": "gemini-2.5-flash",
    "groq": "llama-3.3-70b-versatile",
    "openai": "gpt-4o-mini",
}

PROVIDER_LABELS: dict[LLMProvider, str] = {
    "gemini": "Gemini 2.5 Flash",
    "groq": "Groq Llama 3.3 70B",
    "openai": "OpenAI GPT-4o Mini",
}


def _default_provider() -> LLMProvider:
    """Pick active chat/extraction provider from env (LLM_PROVIDER or available keys)."""
    configured = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if configured in ("openai", "gemini", "groq"):
        key_env = {
            "openai": "OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "groq": "GROQ_API_KEY",
        }[configured]
        if os.getenv(key_env) or os.getenv("LLM_API_KEY"):
            return configured  # type: ignore[return-value]
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    return "openai"


_active_provider: LLMProvider = _default_provider()


def get_active_provider() -> LLMProvider:
    return _active_provider


def set_active_provider(provider: LLMProvider) -> None:
    global _active_provider
    _active_provider = provider


def get_available_providers() -> list[LLMProvider]:
    available: list[LLMProvider] = []
    if os.getenv("OPENAI_API_KEY"):
        available.append("openai")
    if os.getenv("GEMINI_API_KEY"):
        available.append("gemini")
    if os.getenv("GROQ_API_KEY"):
        available.append("groq")
    return available


async def complete_llm(
    provider: LLMProvider,
    messages: list[dict],
    system_prompt: str | None = None,
) -> str:
    """Return full text from the chosen LLM provider (non-streaming)."""
    parts: list[str] = []
    async for chunk in stream_llm(provider, messages, system_prompt):
        parts.append(chunk)
    return "".join(parts)


async def stream_llm(
    provider: LLMProvider,
    messages: list[dict],
    system_prompt: str | None = None,
) -> AsyncGenerator[str, None]:
    """Yield text chunks from the chosen LLM provider."""
    if provider == "gemini":
        async for chunk in _stream_gemini(messages, system_prompt):
            yield chunk
    elif provider == "groq":
        async for chunk in _stream_groq(messages, system_prompt):
            yield chunk
    elif provider == "openai":
        async for chunk in _stream_openai(messages, system_prompt):
            yield chunk
    else:
        raise ValueError(f"Unknown provider: {provider}")


async def _stream_gemini(messages: list[dict], system_prompt: str | None) -> AsyncGenerator[str, None]:
    from google import genai  # type: ignore
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=key)
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
        for m in messages
    ]
    config: dict = {"max_output_tokens": 8192}
    if system_prompt:
        config["system_instruction"] = system_prompt

    async for chunk in await client.aio.models.generate_content_stream(
        model=PROVIDER_MODELS["gemini"],
        contents=contents,
        config=config,
    ):
        if chunk.text:
            yield chunk.text


async def _stream_groq(messages: list[dict], system_prompt: str | None) -> AsyncGenerator[str, None]:
    from groq import AsyncGroq  # type: ignore
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY not set")

    client = AsyncGroq(api_key=key)
    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    msgs.extend(messages)

    stream = await client.chat.completions.create(
        model=PROVIDER_MODELS["groq"],
        messages=msgs,  # type: ignore
        max_tokens=8192,
        stream=True,
    )
    async for chunk in stream:
        text = chunk.choices[0].delta.content
        if text:
            yield text


async def _stream_openai(messages: list[dict], system_prompt: str | None) -> AsyncGenerator[str, None]:
    from openai import AsyncOpenAI  # type: ignore
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")

    client = AsyncOpenAI(api_key=key)
    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    msgs.extend(messages)

    stream = await client.chat.completions.create(
        model=PROVIDER_MODELS["openai"],
        messages=msgs,  # type: ignore
        max_tokens=8192,
        stream=True,
    )
    async for chunk in stream:
        text = chunk.choices[0].delta.content
        if text:
            yield text
