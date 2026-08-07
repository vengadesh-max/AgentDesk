import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Conversation, Message, Project
from app.services.bytez import generate_content as bytez_generate
from app.services.gemini import delete_file as gemini_delete_file
from app.services.gemini import generate_content as gemini_generate
from app.services.gemini import upload_file as gemini_upload
from app.services.groq import generate_content as groq_generate
from app.services.local_fallback import local_chat_response

settings = get_settings()


def _build_system_prompt(project: Project) -> str:
    parts = []
    if project.system_prompt:
        parts.append(project.system_prompt)
    if project.prompts:
        parts.append("\nAdditional context:")
        for p in project.prompts[:3]:
            parts.append(f"[{p.name}] {p.content[:500]}")
    return "\n".join(parts) if parts else "You are a helpful assistant."


async def generate_chat_response(
    db: Session,
    project: Project,
    conversation: Conversation,
    user_content: str,
    user_id: str,
) -> str:
    system_prompt = _build_system_prompt(project)

    history = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
        .all()
    )

    messages = []
    for msg in history:
        if msg.role in ("user", "assistant"):
            messages.append({"role": msg.role, "content": msg.content})
    if not messages or messages[-1]["role"] != "user" or messages[-1]["content"] != user_content:
        messages.append({"role": "user", "content": user_content})

    file_uris = [f.openai_file_id for f in project.files if f.openai_file_id]

    if settings.llm_provider == "groq" and settings.groq_api_key:
        try:
            return await groq_generate(system_prompt, messages, user_id, file_uris or None)
        except RuntimeError as exc:
            err = str(exc)
            if "wait" in err.lower() or "limit" in err.lower():
                offline = local_chat_response(user_content, project.name, system_prompt, messages)
                return f"{err}\n\n---\n\n{offline}"
            offline = local_chat_response(user_content, project.name, system_prompt, messages)
            return (
                f"Offline mode _(Groq API unavailable - using local fallback)_\n\n"
                f"{offline}"
            )

    if settings.llm_provider == "bytez" and settings.bytez_api_key:
        try:
            return await bytez_generate(system_prompt, messages, user_id, file_uris or None)
        except RuntimeError as exc:
            err = str(exc)
            if "wait" in err.lower() or "limit" in err.lower():
                offline = local_chat_response(user_content, project.name, system_prompt, messages)
                return f"⏳ {err}\n\n---\n\n{offline}"
            offline = local_chat_response(user_content, project.name, system_prompt, messages)
            return (
                f"🔄 **Offline mode** _(Bytez API unavailable — using local fallback)_\n\n"
                f"{offline}"
            )

    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        try:
            return await gemini_generate(system_prompt, messages, user_id, file_uris or None)
        except RuntimeError as exc:
            err = str(exc)
            if "wait" in err.lower() or "limit" in err.lower():
                offline = local_chat_response(user_content, project.name, system_prompt, messages)
                return f"⏳ {err}\n\n---\n\n{offline}"
            offline = local_chat_response(user_content, project.name, system_prompt, messages)
            return (
                f"🔄 **Offline mode** _(Gemini quota unavailable — using local fallback)_\n\n"
                f"{offline}"
            )

    return local_chat_response(user_content, project.name, system_prompt, messages)


async def upload_to_llm(file_path: Path, filename: str) -> str | None:
    if settings.llm_provider == "gemini":
        return await gemini_upload(file_path, filename)
    return None


async def delete_from_llm(file_uri: str) -> None:
    if settings.llm_provider == "gemini":
        await gemini_delete_file(file_uri)


def save_upload_file(project_id: str, original_name: str, content: bytes, content_type: str | None) -> tuple[str, Path]:
    upload_dir = Path(settings.upload_dir) / project_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(original_name).suffix
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = upload_dir / filename
    file_path.write_bytes(content)
    return filename, file_path
