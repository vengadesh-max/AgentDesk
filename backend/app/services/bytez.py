import logging
import time

import httpx

from app.config import get_settings
from app.services.rate_limiter import GeminiRateLimiter

settings = get_settings()
logger = logging.getLogger(__name__)

BYTEZ_CHAT_URL = "https://api.bytez.com/models/v2/openai/v1/chat/completions"
MAX_BYTEZ_WAIT_SEC = 30

_limiter = GeminiRateLimiter(
    user_rpm=settings.bytez_user_rpm,
    user_daily=settings.bytez_user_daily_limit,
    global_rpm=settings.bytez_global_rpm,
    min_interval=settings.bytez_min_interval_sec,
)

_bytez_down_until: float = 0.0


def _headers() -> dict[str, str]:
    return {
        "Authorization": settings.bytez_api_key,
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
    """Call Bytez chat completions API. Raises RuntimeError on failure."""
    global _bytez_down_until

    if not settings.bytez_api_key:
        raise RuntimeError("Bytez API key not configured")

    if time.monotonic() < _bytez_down_until:
        raise RuntimeError("Bytez API unavailable (cached) — using offline mode")

    allowed, msg, _wait = await _limiter.check(user_id)
    if not allowed:
        raise RuntimeError(msg)

    system_prompt = _truncate(system_prompt, settings.bytez_max_prompt_chars)
    trimmed = messages[-settings.bytez_max_history_messages :]

    chat_messages: list[dict[str, str]] = []
    if system_prompt:
        chat_messages.append({"role": "system", "content": system_prompt})
    for msg in trimmed:
        chat_messages.append(
            {
                "role": msg["role"],
                "content": _truncate(msg["content"], settings.bytez_max_message_chars),
            }
        )

    payload = {
        "model": settings.bytez_model,
        "messages": chat_messages,
        "max_tokens": settings.bytez_max_output_tokens,
        "temperature": 0.7,
        "stream": False,
    }

    last_error: str | None = None
    deadline = time.monotonic() + MAX_BYTEZ_WAIT_SEC

    async with httpx.AsyncClient(timeout=60.0) as client:
        if time.monotonic() >= deadline:
            raise RuntimeError("Bytez request timed out before send")

        resp = await client.post(BYTEZ_CHAT_URL, headers=_headers(), json=payload)

        if resp.is_success:
            await _limiter.record(user_id)
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("Bytez returned no choices")
            content = choices[0].get("message", {}).get("content", "")
            if content:
                return content.strip()
            raise RuntimeError("Bytez returned empty response")

        detail = resp.text
        try:
            detail = resp.json().get("error", {}).get("message", detail)
        except Exception:
            pass
        last_error = f"Bytez ({resp.status_code}): {detail[:300]}"
        logger.warning("Bytez failed: %s", last_error)

        if resp.status_code in (401, 400):
            raise RuntimeError(last_error)

        if resp.status_code in (403, 429, 503):
            _bytez_down_until = time.monotonic() + 120

    _bytez_down_until = time.monotonic() + 120
    raise RuntimeError(last_error or "Bytez unavailable")
