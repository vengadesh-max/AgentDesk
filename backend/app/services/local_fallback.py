"""Offline fallback when the LLM API is unavailable."""

import re


def local_chat_response(
    user_message: str,
    project_name: str,
    system_prompt: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> str:
    msg = user_message.strip()
    lower = msg.lower()
    personality = _extract_personality(system_prompt, project_name)

    # Greetings
    if re.match(r"^(hi|hello|hey|yo|hiya)\b", lower):
        return (
            f"{personality}\n\n"
            f"Hello! How can I help you today?"
        )

    # Identity questions
    if any(p in lower for p in ["who are you", "what are you", "your name"]):
        return (
            f"I'm **{project_name}**, your AI agent on this platform.\n\n"
            f"{personality}\n\n"
            f"_Note: The LLM API is unavailable right now, so I'm running in offline mode._"
        )

    # Help
    if any(p in lower for p in ["help", "what can you do", "how do you work"]):
        return (
            f"I can chat with you, answer questions, and follow instructions based on my system prompt.\n\n"
            f"**Tips:**\n"
            f"• Wait a few seconds between messages\n"
            f"• Keep messages short\n"
            f"• Check your Bytez API key in `.env` if responses stay offline\n\n"
            f"{personality}"
        )

    # Math simple
    math_match = re.match(r"what(?:'s| is)\s+(\d+)\s*([+\-*/])\s*(\d+)", lower)
    if math_match:
        a, op, b = int(math_match.group(1)), math_match.group(2), int(math_match.group(3))
        ops = {"+": a + b, "-": a - b, "*": a * b, "/": a / b if b else "undefined"}
        return f"The answer is **{ops[op]}**."

    # Question mark — attempt contextual reply
    if "?" in msg:
        return (
            f"Good question! Here's my best answer in offline mode:\n\n"
            f"Based on your question — _\"{msg}\"_ — I'd suggest breaking it into smaller parts "
            f"and being specific about what you need.\n\n"
            f"{personality}\n\n"
            f"_For full AI responses, add a working Bytez API key to `.env` and restart Docker._"
        )

    # Default: acknowledge and reflect
    context_hint = ""
    if history and len(history) >= 2:
        prev = history[-2].get("content", "")[:80]
        context_hint = f"\n\n(Following up on our conversation about: \"{prev}...\")"

    return (
        f"I received your message: _\"{msg}\"_\n\n"
        f"{personality}\n\n"
        f"In offline mode I can hold basic conversations but can't access full AI intelligence. "
        f"Try asking a specific question, or update your Bytez API key for real AI responses."
        f"{context_hint}"
    )


def _extract_personality(system_prompt: str | None, project_name: str) -> str:
    if system_prompt and len(system_prompt.strip()) > 10:
        snippet = system_prompt.strip()[:300]
        return f"My instructions: {snippet}{'...' if len(system_prompt) > 300 else ''}"
    return f"I'm configured as **{project_name}**, a helpful assistant."
