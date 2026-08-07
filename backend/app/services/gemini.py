import asyncio
import logging
import mimetypes
import re
import time
from pathlib import Path

import httpx

from app.config import get_settings
from app.services.rate_limiter import GeminiRateLimiter

settings = get_settings()
logger = logging.getLogger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
MAX_GEMINI_WAIT_SEC = 8

FREE_TIER_MODELS = [
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
]

_limiter = GeminiRateLimiter(
    user_rpm=settings.gemini_user_rpm,
    user_daily=settings.gemini_user_daily_limit,
    global_rpm=settings.gemini_global_rpm,
    min_interval=settings.gemini_min_interval_sec,
)

# Circuit breaker: skip Gemini calls when quota is dead
_gemini_down_until: float = 0.0


def _headers() -> dict[str, str]:
    return {"x-goog-api-key": settings.gemini_api_key}


def _model_url(model: str) -> str:
    return f"{GEMINI_BASE}/models/{model}:generateContent"


def _models_to_try() -> list[str]:
    models = [settings.gemini_model]
    for m in FREE_TIER_MODELS:
        if m not in models:
            models.append(m)
    return models


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _parse_retry_seconds(error_message: str) -> float | None:
    match = re.search(r"retry in ([0-9.]+)s", error_message, re.IGNORECASE)
    return float(match.group(1)) if match else None


async def generate_content(
    system_prompt: str,
    messages: list[dict[str, str]],
    user_id: str,
    file_uris: list[str] | None = None,
) -> str:
    """Call Gemini with strict timeout. Raises RuntimeError on failure."""
    global _gemini_down_until

    if time.monotonic() < _gemini_down_until:
        raise RuntimeError("Gemini quota exhausted (cached) — using offline mode")

    allowed, msg, _wait = await _limiter.check(user_id)
    if not allowed:
        raise RuntimeError(msg)

    system_prompt = _truncate(system_prompt, settings.gemini_max_prompt_chars)
    trimmed = messages[-settings.gemini_max_history_messages :]
    contents = []
    for msg in trimmed:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": _truncate(msg["content"], settings.gemini_max_message_chars)}]})

    payload: dict = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": settings.gemini_max_output_tokens,
            "temperature": 0.7,
        },
    }
    if system_prompt:
        payload["system_instruction"] = {"parts": [{"text": system_prompt}]}

    last_error: str | None = None
    deadline = time.monotonic() + MAX_GEMINI_WAIT_SEC

    async with httpx.AsyncClient(timeout=30.0) as client:
        for model in _models_to_try():
            if time.monotonic() >= deadline:
                break

            resp = await client.post(_model_url(model), headers=_headers(), json=payload)

            if resp.is_success:
                await _limiter.record(user_id)
                data = resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    last_error = f"{model}: no candidates"
                    continue
                parts = candidates[0].get("content", {}).get("parts", [])
                text_parts = [p["text"] for p in parts if "text" in p]
                if text_parts:
                    return "\n".join(text_parts)
                last_error = f"{model}: empty response"
                continue

            detail = resp.text
            try:
                detail = resp.json().get("error", {}).get("message", detail)
            except Exception:
                pass
            last_error = f"{model} ({resp.status_code}): {detail[:200]}"
            logger.warning("Gemini failed: %s", last_error)

            if resp.status_code in (401, 400):
                raise RuntimeError(last_error)

            if resp.status_code in (403, 429):
                _gemini_down_until = time.monotonic() + 300  # skip Gemini for 5 min

            continue

    _gemini_down_until = time.monotonic() + 300
    raise RuntimeError(last_error or "Gemini unavailable")


async def upload_file(file_path: Path, display_name: str) -> str | None:
    if not settings.gemini_api_key or not settings.gemini_enable_file_context:
        return None
    mime_type = mimetypes.guess_type(display_name)[0] or "application/octet-stream"
    file_bytes = file_path.read_bytes()
    num_bytes = len(file_bytes)
    async with httpx.AsyncClient(timeout=60.0) as client:
        start_resp = await client.post(
            "https://generativelanguage.googleapis.com/upload/v1beta/files",
            headers={
                **_headers(),
                "X-Goog-Upload-Protocol": "resumable",
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": str(num_bytes),
                "X-Goog-Upload-Header-Content-Type": mime_type,
                "Content-Type": "application/json",
            },
            json={"file": {"display_name": display_name}},
        )
        if not start_resp.is_success:
            return None
        upload_url = start_resp.headers.get("x-goog-upload-url")
        if not upload_url:
            return None
        upload_resp = await client.post(
            upload_url,
            headers={
                "Content-Length": str(num_bytes),
                "X-Goog-Upload-Offset": "0",
                "X-Goog-Upload-Command": "upload, finalize",
            },
            content=file_bytes,
        )
        if not upload_resp.is_success:
            return None
        return upload_resp.json().get("file", {}).get("uri")


async def delete_file(file_uri: str) -> None:
    if not settings.gemini_api_key or not file_uri:
        return
    file_name = file_uri.rstrip("/").split("/files/")[-1]
    if not file_name.startswith("files/"):
        file_name = f"files/{file_name}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        await client.delete(f"{GEMINI_BASE}/{file_name}", headers=_headers())
