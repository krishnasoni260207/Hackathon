from __future__ import annotations


class SpeechToTextService:
    def transcribe(self, _audio_bytes: bytes) -> str:
        raise NotImplementedError("Realtime STT is not implemented in Phase 1.")
