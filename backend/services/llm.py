"""LLM service — generates study assistant responses.

Uses OpenRouter (OpenAI-compatible API) when BACKEND_MODE=real,
or returns mock text when BACKEND_MODE=mock.
"""
from __future__ import annotations

import os
from typing import Any

SYSTEM_PROMPT = (
    "You are a friendly, patient study assistant helping a student who is "
    "talking to you out loud and will hear your answer read aloud by a "
    "text-to-speech voice. Keep your responses SHORT — 2 to 4 sentences max. "
    "Explain concepts clearly in plain conversational language. "
    "Never use bullet points, numbered lists, or markdown formatting. "
    "If the topic is complex, give a brief overview and ask if they want more detail."
)


class LLMError(Exception):
    """Raised when the LLM request fails."""


import threading
from typing import AsyncGenerator, Callable, Optional

from backend.audio.interruption import InterruptionController, StaleRequestError

_client_lock = threading.Lock()
_shared_openai_client: Optional[Any] = None


def _get_openai_client():
    global _shared_openai_client
    from openai import AsyncOpenAI
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set in environment.")
    base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    if _shared_openai_client is None:
        with _client_lock:
            if _shared_openai_client is None:
                _shared_openai_client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    return _shared_openai_client


def _mode() -> str:
    return os.environ.get("BACKEND_MODE", "mock").strip().lower()


async def generate_response_stream(
    user_text: str,
    history: list[dict] | None = None,
    request_id: Optional[str] = None,
    interruption_controller: Optional[InterruptionController] = None,
    on_first_token: Optional[Callable[[], None]] = None,
) -> AsyncGenerator[str, None]:
    """Stream LLM response sentence-by-sentence as tokens are generated.

    Yields complete sentences or natural phrase chunks early so TTS synthesis
    can begin before the full answer finishes. Checks for cancellation at each step.
    """
    if not user_text.strip():
        raise ValueError("user_text cannot be empty.")

    if interruption_controller and request_id:
        interruption_controller.assert_current(request_id)

    if _mode() == "mock":
        first = True
        sentences = [
            f"Mock study answer for {user_text.strip()}.",
            "In real mode this comes from OpenRouter.",
            "The pipeline is working and returning text to TTS.",
        ]
        for sentence in sentences:
            if interruption_controller and request_id:
                interruption_controller.assert_current(request_id)
            if first:
                if on_first_token:
                    on_first_token()
                first = False
            yield sentence
        return

    client = _get_openai_client()
    model = os.environ.get("LLM_MODEL", "openai/gpt-4o-mini")
    max_tokens = int(os.environ.get("LLM_MAX_OUTPUT_TOKENS", "600"))
    messages = _build_messages(user_text, history)

    from openai import OpenAIError
    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            stream=True,
        )
    except OpenAIError as exc:
        raise LLMError(f"OpenRouter LLM request failed: {exc}") from exc

    buffer = ""
    first_token_seen = False
    sentence_ends = (". ", "? ", "! ", ".\n", "?\n", "!\n", "\n\n")

    async for chunk in stream:
        if interruption_controller and request_id:
            interruption_controller.assert_current(request_id)

        delta = chunk.choices[0].delta if chunk.choices else None
        content = delta.content if delta else None
        if not content:
            continue

        if not first_token_seen:
            first_token_seen = True
            if on_first_token:
                on_first_token()

        buffer += content

        # Check for sentence boundary to yield early chunk
        split_pos = -1
        for sep in sentence_ends:
            pos = buffer.find(sep)
            if pos != -1 and (split_pos == -1 or pos < split_pos):
                split_pos = pos + len(sep)

        if split_pos != -1:
            ready_sentence = buffer[:split_pos].strip()
            buffer = buffer[split_pos:].lstrip()
            if ready_sentence:
                yield ready_sentence

    if buffer.strip():
        if interruption_controller and request_id:
            interruption_controller.assert_current(request_id)
        yield buffer.strip()


async def generate_response(
    user_text: str,
    history: list[dict] | None = None,
    request_id: Optional[str] = None,
    interruption_controller: Optional[InterruptionController] = None,
    on_first_token: Optional[Callable[[], None]] = None,
) -> str:
    """Generate an assistant reply to the user's study question.

    Args:
        user_text: The student's question or message.
        history: Prior conversation turns as [{"role": ..., "content": ...}].
        request_id: Optional request tracking ID.
        interruption_controller: Optional controller to check for stale/interrupted requests.
        on_first_token: Optional callback invoked when the first token arrives.

    Returns:
        The assistant's response text.

    Raises:
        ValueError: If user_text is empty.
        StaleRequestError: If the request was interrupted.
        LLMError: If the API call fails.
    """
    chunks: list[str] = []
    async for chunk in generate_response_stream(
        user_text,
        history=history,
        request_id=request_id,
        interruption_controller=interruption_controller,
        on_first_token=on_first_token,
    ):
        chunks.append(chunk)

    return " ".join(chunks).strip()


def _build_messages(
    user_text: str,
    history: list[dict] | None,
) -> list[dict[str, str]]:
    """Build the messages array for chat completions.

    Returns a list starting with the system prompt, followed by
    conversation history, and ending with the latest user message.
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    for item in history or []:
        role = str(item.get("role", "user")).lower()
        content = _extract_text(item)
        if not content:
            continue
        if role not in ("user", "assistant"):
            role = "user"
        messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_text.strip()})

    return messages


def _extract_text(item: dict[str, Any]) -> str:
    """Extract text content from a message dict."""
    raw = item.get("content", item.get("text", ""))
    if isinstance(raw, list):
        return " ".join(str(part) for part in raw).strip()
    return str(raw).strip()
