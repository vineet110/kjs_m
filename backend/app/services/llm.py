"""One small door to any LLM provider. Koko calls `chat()`; it doesn't know or care
which company answers. Switch with LLM_PROVIDER / LLM_MODEL in .env (backlog D4)."""
import httpx
import structlog

from app.core.config import settings

log = structlog.get_logger()


class LLMUnavailable(Exception):
    pass


async def chat(system: str, messages: list[dict], max_tokens: int = 700) -> str:
    provider = settings.LLM_PROVIDER
    if provider == "groq":
        return await _openai_compatible(
            "https://api.groq.com/openai/v1/chat/completions", settings.GROQ_API_KEY,
            system, messages, max_tokens,
        )
    if provider == "anthropic":
        return await _anthropic(system, messages, max_tokens)
    raise LLMUnavailable(f"LLM provider '{provider}' is not configured")


async def _openai_compatible(url: str, key: str, system: str, messages: list[dict], max_tokens: int) -> str:
    if not key:
        raise LLMUnavailable("missing API key")
    payload = {
        "model": settings.LLM_MODEL,
        "messages": [{"role": "system", "content": system}, *messages],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, json=payload, headers={"Authorization": f"Bearer {key}"})
        r.raise_for_status()
        return (r.json()["choices"][0]["message"]["content"] or "").strip()
    except (httpx.HTTPError, KeyError, IndexError) as e:
        log.warning("llm_call_failed", provider=settings.LLM_PROVIDER, error=str(e)[:300])
        raise LLMUnavailable(str(e)) from e


async def _anthropic(system: str, messages: list[dict], max_tokens: int) -> str:
    if not settings.ANTHROPIC_API_KEY:
        raise LLMUnavailable("missing API key")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                json={"model": settings.LLM_MODEL, "system": system, "messages": messages,
                      "max_tokens": max_tokens},
                headers={"x-api-key": settings.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
            )
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json()["content"]).strip()
    except (httpx.HTTPError, KeyError) as e:
        log.warning("llm_call_failed", provider="anthropic", error=str(e)[:300])
        raise LLMUnavailable(str(e)) from e
