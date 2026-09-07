"""Speech-to-Text service — transcribes audio to text using Deepgram.

Uses Deepgram's REST API when BACKEND_MODE=real,
or returns mock text when BACKEND_MODE=mock.
"""
from __future__ import annotations

import os

MOCK_TRANSCRIPT = "Explain backpropagation."

DEEPGRAM_API_URL = "https://api.deepgram.com/v1/listen"


class STTError(Exception):
    """Raised when audio transcription fails."""


import threading
from typing import Optional

from backend.audio.interruption import InterruptionController, StaleRequestError

_client_lock = threading.Lock()
_shared_stt_client: Optional[Any] = None


def _get_stt_client():
    global _shared_stt_client
    import httpx
    if _shared_stt_client is None or _shared_stt_client.is_closed:
        with _client_lock:
            if _shared_stt_client is None or _shared_stt_client.is_closed:
                _shared_stt_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(30.0, connect=5.0),
                    limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                )
    return _shared_stt_client


def _mode() -> str:
    return os.environ.get("BACKEND_MODE", "mock").strip().lower()


async def transcribe_audio(
    audio_data: bytes,
    filename: str = "audio.webm",
    request_id: Optional[str] = None,
    interruption_controller: Optional[InterruptionController] = None,
) -> str:
    """Transcribe audio bytes into text using Deepgram.

    Args:
        audio_data: Raw audio bytes (WAV, WebM, etc.)
        filename: Original filename — the extension helps determine content type.
        request_id: Optional tracking request ID.
        interruption_controller: Optional controller to check for stale/interrupted requests.

    Returns:
        Transcribed text string.

    Raises:
        ValueError: If audio_data is empty.
        StaleRequestError: If the request was interrupted.
        STTError: If the transcription API call fails.
    """
    if not audio_data:
        raise ValueError("audio_data cannot be empty.")

    if interruption_controller and request_id:
        interruption_controller.assert_current(request_id)

    if _mode() == "mock":
        return MOCK_TRANSCRIPT

    transcript = await _transcribe_deepgram(audio_data, filename)

    if interruption_controller and request_id:
        interruption_controller.assert_current(request_id)

    return transcript


async def _transcribe_deepgram(audio_data: bytes, filename: str) -> str:
    """Call Deepgram's REST transcription API.

    Deepgram accepts raw audio bytes via POST and returns a JSON
    response with the transcript. No SDK needed — just httpx.
    """
    import httpx

    api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPGRAM_API_KEY is not set in environment.")

    # Determine content type from filename extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"
    content_type_map = {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
        "ogg": "audio/ogg",
        "webm": "audio/webm",
        "flac": "audio/flac",
        "mp4": "audio/mp4",
    }
    content_type = content_type_map.get(ext, "audio/webm")

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": content_type,
    }

    # Deepgram query parameters for best transcription
    params = {
        "model": "nova-3",         # Latest & most accurate model
        "smart_format": "true",     # Auto-punctuation & formatting
        "language": "en",           # English
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                DEEPGRAM_API_URL,
                content=audio_data,
                headers=headers,
                params=params,
            )
            response.raise_for_status()

            data = response.json()

    except httpx.HTTPStatusError as exc:
        raise STTError(
            f"Deepgram returned HTTP {exc.response.status_code}: {exc.response.text[:300]}"
        ) from exc
    except httpx.HTTPError as exc:
        raise STTError(f"Deepgram request failed: {exc}") from exc

    # Extract transcript from Deepgram's response structure:
    # { "results": { "channels": [{ "alternatives": [{ "transcript": "..." }] }] } }
    try:
        transcript = (
            data["results"]["channels"][0]["alternatives"][0]["transcript"]
        )
    except (KeyError, IndexError) as exc:
        raise STTError(
            f"Unexpected Deepgram response structure: {str(data)[:300]}"
        ) from exc

    transcript = transcript.strip()
    if not transcript:
        raise STTError(
            "Deepgram returned empty transcript — microphone may not have captured audio."
        )

    return transcript
