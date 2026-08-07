import logging
import time

import httpx

from app.config import get_settings
from app.services.rate_limiter import GeminiRateLimiter

settings = get_settings()
logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

_limiter = GeminiRateLimiter(
    user_rpm=settings.groq_user_rpm,
    user_daily=settings.groq_user_daily_limit,
    global_rpm=settings.groq_global_rpm,
    min_interval=settings.groq_min_interval_sec,
)

_groq_down_until: float = 0.0


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


async def generate_content(
    system_prompt: str,
    messages: list[dict[str, str]],
    user_id: str,
    file_uris: list[str] | None = None,
) -> str:
    """Call Groq's OpenAI-compatible chat completions API."""
    global _groq_down_until

    if not settings.groq_api_key:
        raise RuntimeError("Groq API key not configured")

    if time.monotonic() < _groq_down_until:
        raise RuntimeError("Groq API unavailable (cached) - using offline mode")

    allowed, msg, _wait = await _limiter.check(user_id)
    if not allowed:
        raise RuntimeError(msg)

    chat_messages: list[dict[str, str]] = []
    system_prompt = _truncate(system_prompt, settings.groq_max_prompt_chars)
    if system_prompt:
        chat_messages.append({"role": "system", "content": system_prompt})

    for msg in messages[-settings.groq_max_history_messages :]:
        chat_messages.append(
            {
                "role": msg["role"],
                "content": _truncate(msg["content"], settings.groq_max_message_chars),
            }
        )

    payload = {
        "model": settings.groq_model,
        "messages": chat_messages,
        "max_tokens": settings.groq_max_output_tokens,
        "temperature": 0.7,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(GROQ_CHAT_URL, headers=_headers(), json=payload)

    if resp.is_success:
        await _limiter.record(user_id)
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("Groq returned no choices")
        content = choices[0].get("message", {}).get("content", "")
        if content:
            return content.strip()
        raise RuntimeError("Groq returned empty response")

    detail = resp.text
    try:
        detail = resp.json().get("error", {}).get("message", detail)
    except Exception:
        pass

    last_error = f"Groq ({resp.status_code}): {detail[:300]}"
    logger.warning("Groq failed: %s", last_error)

    if resp.status_code in (429, 500, 502, 503, 504):
        _groq_down_until = time.monotonic() + 120

    raise RuntimeError(last_error)
