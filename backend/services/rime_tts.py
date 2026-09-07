"""Rime TTS service — converts text to spoken audio.

Uses Rime's REST API when BACKEND_MODE=real,
or returns a silent WAV clip when BACKEND_MODE=mock.

Long text is automatically split into chunks and each chunk is
synthesized separately, then the WAV audio is concatenated.
"""
from __future__ import annotations

import os
import struct

RIME_TTS_URL = "https://users.rime.ai/v1/rime-tts"

# Rime has a character limit per request (~1000 chars).
# We split at sentence boundaries to stay well under the limit.
MAX_CHUNK_CHARS = 800


class TTSError(Exception):
    """Raised when Rime speech synthesis fails."""

from typing import Any, AsyncGenerator, Optional

from backend.audio.interruption import InterruptionController


def _new_client():
    import httpx

    return httpx.AsyncClient(
        timeout=httpx.Timeout(60.0, connect=5.0),
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
    )


def _mode() -> str:
    return os.environ.get("BACKEND_MODE", "mock").strip().lower()


async def synthesize_chunk(
    chunk_text: str,
    request_id: Optional[str] = None,
    interruption_controller: Optional[InterruptionController] = None,
    client: Optional[Any] = None,
) -> bytes:
    """Synthesize a single text chunk into speech.
    
    Checks interruption before and after the API call.
    """
    if not chunk_text.strip():
        raise ValueError("chunk_text cannot be empty.")

    if interruption_controller and request_id:
        interruption_controller.assert_current(request_id)

    if _mode() == "mock":
        return _make_silent_wav(duration_ms=600)

    if client is not None:
        audio = await _synthesize_one_chunk(chunk_text, client=client)
    else:
        async with _new_client() as http_client:
            audio = await _synthesize_one_chunk(chunk_text, client=http_client)

    if interruption_controller and request_id:
        interruption_controller.assert_current(request_id)

    return audio


async def synthesize_speech_stream(
    text: str,
    request_id: Optional[str] = None,
    interruption_controller: Optional[InterruptionController] = None,
) -> AsyncGenerator[bytes, None]:
    """Yield synthesized audio chunks as they become available.
    
    Allows early playback of initial audio before later chunks finish.
    """
    if not text.strip():
        raise ValueError("text cannot be empty.")

    if interruption_controller and request_id:
        interruption_controller.assert_current(request_id)

    chunks = _split_text(text, MAX_CHUNK_CHARS)
    client = None if _mode() == "mock" else _new_client()

    for chunk in chunks:
        if interruption_controller and request_id:
            interruption_controller.assert_current(request_id)
        audio = await synthesize_chunk(
            chunk,
            request_id=request_id,
            interruption_controller=interruption_controller,
            client=client,
        )
        yield audio


async def synthesize_speech(
    text: str,
    request_id: Optional[str] = None,
    interruption_controller: Optional[InterruptionController] = None,
) -> bytes:
    """Synthesize speech audio from text.

    Long text is automatically chunked into segments of ~800 chars
    (splitting at sentence boundaries) and each chunk is synthesized
    separately. The resulting WAV audio is concatenated.

    Args:
        text: The text to convert to speech.
        request_id: Optional request ID for cancellation tracking.
        interruption_controller: Optional controller to check for stale/interrupted requests.

    Returns:
        Raw audio bytes (WAV format by default).

    Raises:
        ValueError: If text is empty.
        StaleRequestError: If the request was interrupted or became stale.
        TTSError: If the API call fails.
    """
    if not text.strip():
        raise ValueError("text cannot be empty.")

    if interruption_controller and request_id:
        interruption_controller.assert_current(request_id)

    if _mode() == "mock":
        return _make_silent_wav(duration_ms=800)

    # Split long text into chunks that Rime can handle
    chunks = _split_text(text, MAX_CHUNK_CHARS)
    client = _new_client()

    # Synthesize each chunk
    audio_parts: list[bytes] = []
    for chunk in chunks:
        if interruption_controller and request_id:
            interruption_controller.assert_current(request_id)
        part = await _synthesize_one_chunk(chunk, client=client)
        audio_parts.append(part)

    if interruption_controller and request_id:
        interruption_controller.assert_current(request_id)

    # If only one chunk, return it directly
    if len(audio_parts) == 1:
        return audio_parts[0]

    # Multiple chunks — concatenate the WAV data
    return _concatenate_wav(audio_parts)


def _split_text(text: str, max_chars: int) -> list[str]:
    """Split text into chunks at sentence boundaries.

    Tries to split at '. ', '! ', '? ' first, then falls back to
    ', ' and finally hard-splits at max_chars if needed.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining.strip())
            break

        # Find the best split point within max_chars
        split_at = -1

        # Try sentence-ending punctuation first
        for sep in [". ", "! ", "? "]:
            idx = remaining.rfind(sep, 0, max_chars)
            if idx > split_at:
                split_at = idx + len(sep) - 1  # include the punctuation

        # Fall back to comma
        if split_at < 0:
            idx = remaining.rfind(", ", 0, max_chars)
            if idx > 0:
                split_at = idx + 1

        # Fall back to any space
        if split_at < 0:
            idx = remaining.rfind(" ", 0, max_chars)
            if idx > 0:
                split_at = idx

        # Hard split as last resort
        if split_at < 0:
            split_at = max_chars

        chunk = remaining[:split_at + 1].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at + 1:].strip()

    return [c for c in chunks if c]


async def _synthesize_one_chunk(text: str, client: Optional[Any] = None) -> bytes:
    """Call Rime's REST TTS API for a single text chunk."""
    import httpx

    api_key = os.environ.get("RIME_API_KEY")
    if not api_key:
        raise RuntimeError("RIME_API_KEY is not set in environment.")

    audio_format = os.environ.get("RIME_AUDIO_FORMAT", "audio/wav")
    payload = {
        "text": text,
        "speaker": os.environ.get("RIME_SPEAKER", "celeste"),
        "modelId": os.environ.get("RIME_MODEL_ID", "coda"),
    }

    lang = os.environ.get("RIME_LANG")
    if lang:
        payload["lang"] = lang

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": audio_format,
    }

    http_client = client or _get_client()

    try:
        response = await http_client.post(RIME_TTS_URL, json=payload, headers=headers)
        response.raise_for_status()

        if len(response.content) < 100:
            raise TTSError(
                f"Rime TTS returned suspiciously small audio ({len(response.content)} bytes). "
                f"Response: {response.text[:200]}"
            )

        return response.content

    except httpx.HTTPStatusError as exc:
        raise TTSError(
            f"Rime TTS HTTP {exc.response.status_code}: {exc.response.text[:300]}"
        ) from exc
    except httpx.HTTPError as exc:
        raise TTSError(f"Rime TTS request failed: {exc}") from exc


def _concatenate_wav(wav_parts: list[bytes]) -> bytes:
    """Concatenate multiple WAV byte arrays into one.

    Assumes all parts have the same sample rate, bit depth, and channels.
    Reads the header from the first part and appends all data sections.
    """
    if not wav_parts:
        return b""
    if len(wav_parts) == 1:
        return wav_parts[0]

    # Extract the header (44 bytes) from the first WAV
    first = wav_parts[0]
    if len(first) < 44 or first[:4] != b"RIFF":
        # Not a standard WAV — just return the first part
        return first

    header = bytearray(first[:44])
    all_data = bytearray()

    for part in wav_parts:
        if len(part) > 44 and part[:4] == b"RIFF":
            # Skip the 44-byte WAV header, keep only audio data
            all_data.extend(part[44:])
        else:
            # Non-WAV chunk — append as-is
            all_data.extend(part)

    # Update the RIFF chunk size (bytes 4-7): file_size - 8
    total_size = 36 + len(all_data)
    header[4:8] = struct.pack("<I", total_size)

    # Update the data chunk size (bytes 40-43)
    header[40:44] = struct.pack("<I", len(all_data))

    return bytes(header) + bytes(all_data)


def _make_silent_wav(duration_ms: int = 800, sample_rate: int = 22050) -> bytes:
    """Generate a short silent WAV clip for mock mode."""
    num_samples = max(1, sample_rate * duration_ms // 1000)
    data_size = num_samples * 2
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,    # chunk size
        1,     # PCM format
        1,     # mono
        sample_rate,
        sample_rate * 2,  # byte rate
        2,     # block align
        16,    # bits per sample
        b"data",
        data_size,
    )
    return header + (b"\x00" * data_size)
