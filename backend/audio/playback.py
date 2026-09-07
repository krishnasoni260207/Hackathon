from __future__ import annotations

import enum
import logging
import threading
from typing import Optional

from backend.audio.interruption import InterruptionController, get_interruption_controller

logger = logging.getLogger(__name__)


class PlaybackState(str, enum.Enum):
    IDLE = "idle"
    PLAYING = "playing"
    INTERRUPTED = "interrupted"
    STOPPED = "stopped"
    COMPLETED = "completed"


class PlaybackController:
    """Interruption-aware audio playback manager.
    
    Ensures that only the latest, non-stale audio is played, stops playback
    immediately upon interruption, and guarantees that multiple audio responses
    never play concurrently.
    """

    def __init__(self, interruption_controller: Optional[InterruptionController] = None) -> None:
        self.interruption_controller = interruption_controller or get_interruption_controller()
        self._state = PlaybackState.IDLE
        self._active_request_id: str | None = None
        self._current_audio: bytes | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> PlaybackState:
        with self._lock:
            return self._state

    @property
    def active_request_id(self) -> str | None:
        with self._lock:
            return self._active_request_id

    def is_playing(self) -> bool:
        with self._lock:
            return self._state == PlaybackState.PLAYING

    def start_playback(self, request_id: str, audio_bytes: bytes) -> bool:
        """Start playing audio for the specified request.
        
        Rejects stale audio if request_id is no longer current. Stops any
        currently playing audio to prevent overlapping speech.
        
        Returns:
            True if playback was started, False if rejected as stale or invalid.
        """
        if not audio_bytes:
            logger.warning("Rejecting playback: empty audio bytes.")
            return False

        with self._lock:
            # Stale response protection
            if not self.interruption_controller.is_current(request_id):
                logger.info(
                    "Rejecting stale audio playback for request %s (current is %s)",
                    request_id,
                    self.interruption_controller.current_request_id(),
                )
                return False

            # Stop prior audio if currently playing — guarantees no overlap
            if self._state == PlaybackState.PLAYING:
                logger.info("Stopping previous playback for request %s", self._active_request_id)
                self._state = PlaybackState.STOPPED

            self._active_request_id = request_id
            self._current_audio = audio_bytes
            self._state = PlaybackState.PLAYING
            logger.info("Playback started for request %s (%d bytes)", request_id, len(audio_bytes))
            return True

    def stop_playback(self, reason: str = "stopped") -> None:
        """Stop current audio playback immediately and clear active audio."""
        with self._lock:
            if self._state == PlaybackState.PLAYING:
                logger.info("Playback %s for request %s", reason, self._active_request_id)
                self._state = PlaybackState.INTERRUPTED if reason == "interrupted" else PlaybackState.STOPPED
                self._current_audio = None

    def complete_playback(self, request_id: str) -> None:
        """Mark playback as cleanly finished for a request."""
        with self._lock:
            if self._active_request_id == request_id and self._state == PlaybackState.PLAYING:
                self._state = PlaybackState.COMPLETED
                self._current_audio = None
                logger.info("Playback cleanly completed for request %s", request_id)

    def on_user_speech_detected(self) -> str | None:
        """Handle real-time user speech detected while audio is playing.
        
        Instantly halts playback, invalidates the active request in the
        InterruptionController, and transitions state to INTERRUPTED.
        
        Returns:
            The interrupted request ID if an active response was interrupted, else None.
        """
        interrupted_id = None
        with self._lock:
            if self._state == PlaybackState.PLAYING:
                interrupted_id = self._active_request_id
                self._state = PlaybackState.INTERRUPTED
                self._current_audio = None
                logger.info("Voice interruption detected! Silencing request %s immediately", interrupted_id)

        if interrupted_id:
            self.interruption_controller.interrupt(interrupted_id)

        return interrupted_id


_global_playback_controller = PlaybackController()


def get_playback_controller() -> PlaybackController:
    return _global_playback_controller


def play_audio(audio_bytes: bytes, request_id: str | None = None) -> bool:
    """Convenience helper to play audio through the global controller."""
    controller = get_playback_controller()
    req_id = request_id or controller.interruption_controller.start_request()
    return controller.start_playback(req_id, audio_bytes)

