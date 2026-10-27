"""One small door to any LLM provider. Koko calls `chat()`; it doesn't know or care
which company answers. Switch with LLM_PROVIDER / LLM_MODEL in .env (backlog D4)."""
import asyncio
import logging

import httpx

from app.core.config import settings
from app.core.config.ini import cfg

log = logging.getLogger(__name__)


class LLMUnavailable(Exception):
    pass


# The whole call, not each step: nginx gives up after 60 s, and a visitor who sees an error resubmits
# (a duplicate lead). After 25 s we answer "please use the form / WhatsApp" instead.
TOTAL_TIMEOUT_SECONDS = 25
HTTP_TIMEOUT = httpx.Timeout(20, connect=5)


async def chat(system: str, messages: list[dict], max_tokens: int | None = None) -> str:
    max_tokens = max_tokens or cfg().koko.max_tokens  # config/koko.ini
    provider = settings.LLM_PROVIDER
    if provider == "groq":
        call = _openai_compatible(
            "https://api.groq.com/openai/v1/chat/completions", settings.GROQ_API_KEY,
            system, messages, max_tokens,
        )
    elif provider == "anthropic":
        call = _anthropic(system, messages, max_tokens)
    else:
        raise LLMUnavailable(f"LLM provider '{provider}' is not configured")
    try:
        return await asyncio.wait_for(call, TOTAL_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as e:
        log.warning("llm.call_failed", extra={"provider": provider, "reason": "total timeout"})
        raise LLMUnavailable("timeout") from e


async def _openai_compatible(url: str, key: str, system: str, messages: list[dict], max_tokens: int) -> str:
    if not key:
        raise LLMUnavailable("missing API key")
    payload = {
        "model": settings.LLM_MODEL,
        "messages": [{"role": "system", "content": system}, *messages],
        "max_tokens": max_tokens,
        "temperature": cfg().koko.temperature,
    }
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            r = await client.post(url, json=payload, headers={"Authorization": f"Bearer {key}"})
        r.raise_for_status()
        return (r.json()["choices"][0]["message"]["content"] or "").strip()
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as e:  # ValueError: not JSON
        log.warning("llm.call_failed", extra={"provider": settings.LLM_PROVIDER, "reason": str(e)[:300]})
        raise LLMUnavailable(str(e)) from e


async def _anthropic(system: str, messages: list[dict], max_tokens: int) -> str:
    if not settings.ANTHROPIC_API_KEY:
        raise LLMUnavailable("missing API key")
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                json={"model": settings.LLM_MODEL, "system": system, "messages": messages,
                      "max_tokens": max_tokens},
                headers={"x-api-key": settings.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
            )
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json()["content"]).strip()
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as e:
        log.warning("llm.call_failed", extra={"provider": "anthropic", "reason": str(e)[:300]})
        raise LLMUnavailable(str(e)) from e
