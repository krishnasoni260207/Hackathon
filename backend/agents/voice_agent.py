"""Voice agent — orchestrates one audio-in → audio-out study assistant turn.

Pipeline: STT (transcribe) → LLM (generate answer) → TTS (synthesize speech)
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field

from backend.services import llm, rime_tts, stt

logger = logging.getLogger(__name__)


import asyncio
from typing import Optional

from backend.audio.interruption import InterruptionController, StaleRequestError
from backend.metrics.interruption_metrics import LatencyTracker, get_latency_tracker
from backend.services import llm, rime_tts, stt

logger = logging.getLogger(__name__)


@dataclass
class VoiceAgentResult:
    """Structured result from one STT → LLM → TTS pipeline run."""

    transcript: str
    response_text: str
    audio_bytes: bytes
    request_id: str | None = None
    timings: dict[str, float] = field(default_factory=dict)
    first_audio_bytes: Optional[bytes] = None


class VoiceAgent:
    """Runs one audio-in → audio-out study assistant turn with low-latency pipelining."""

    def __init__(
        self,
        interruption_controller: Optional[InterruptionController] = None,
        latency_tracker: Optional[LatencyTracker] = None,
    ) -> None:
        self.interruption_controller = interruption_controller
        self.latency_tracker = latency_tracker or get_latency_tracker()

    async def process_audio(
        self,
        audio_data: bytes,
        history: list[dict] | None = None,
        filename: str = "audio.webm",
        request_id: str | None = None,
        speech_end_ts: Optional[float] = None,
    ) -> VoiceAgentResult:
        """Run the optimized STT → LLM → TTS pipeline for one audio clip.

        Args:
            audio_data: Raw audio bytes from the microphone.
            history: Prior conversation as [{"role": ..., "content": ...}].
            filename: Original filename (helps STT choose the right decoder).
            request_id: Tracking ID; auto-generated if not provided.
            speech_end_ts: Optional timestamp when the user finished speaking.

        Returns:
            VoiceAgentResult with transcript, response text, audio, and timings.

        Raises:
            ValueError: If audio_data is empty.
            StaleRequestError: If request was interrupted during execution.
        """
        if not audio_data:
            raise ValueError("audio_data cannot be empty.")

        t_input = time.monotonic()
        req_id = request_id or (
            self.interruption_controller.start_request()
            if self.interruption_controller
            else str(uuid.uuid4())
        )

        metrics = self.latency_tracker.start_turn(
            request_id=req_id,
            speech_end_ts=speech_end_ts,
            input_received_ts=t_input,
        )
        timings: dict[str, float] = {}

        if self.interruption_controller:
            self.interruption_controller.assert_current(req_id)

        # ------------------------------------------------------------------
        # Step 1: Speech-to-Text
        # ------------------------------------------------------------------
        logger.info("[%s] STT: transcribing %d bytes…", req_id, len(audio_data))
        t_stt_start = time.monotonic()
        transcript = await stt.transcribe_audio(
            audio_data,
            filename=filename,
            request_id=req_id,
            interruption_controller=self.interruption_controller,
        )
        t_stt_end = time.monotonic()
        self.latency_tracker.record_stt_completed(req_id, t_stt_end)
        timings["stt_ms"] = round((t_stt_end - t_stt_start) * 1000, 1)
        logger.info("[%s] STT done in %.1fms: %s", req_id, timings["stt_ms"], transcript[:80])

        if self.interruption_controller:
            self.interruption_controller.assert_current(req_id)

        # ------------------------------------------------------------------
        # Step 2: LLM Generation with Sentence Pipelining into Rime TTS
        # ------------------------------------------------------------------
        logger.info("[%s] LLM: streaming response with early TTS…", req_id)
        t_llm_start = time.monotonic()
        self.latency_tracker.record_llm_started(req_id, t_llm_start)

        first_token_ts: Optional[float] = None

        def _on_first_token():
            nonlocal first_token_ts
            first_token_ts = time.monotonic()
            self.latency_tracker.record_llm_first_token(req_id, first_token_ts)

        sentence_chunks: list[str] = []
        audio_parts: list[bytes] = []
        first_audio_chunk: Optional[bytes] = None
        first_audio_ts: Optional[float] = None
        t_tts_start: Optional[float] = None

        async for sentence in llm.generate_response_stream(
            transcript,
            history=history,
            request_id=req_id,
            interruption_controller=self.interruption_controller,
            on_first_token=_on_first_token,
        ):
            sentence_chunks.append(sentence)

            # As soon as the first sentence arrives, synthesize it immediately!
            if len(sentence_chunks) == 1:
                t_tts_start = time.monotonic()
                self.latency_tracker.record_tts_started(req_id, t_tts_start)
                logger.info("[%s] Synthesizing initial sentence chunk: %s", req_id, sentence[:60])

                first_audio_chunk = await rime_tts.synthesize_chunk(
                    sentence,
                    request_id=req_id,
                    interruption_controller=self.interruption_controller,
                )
                first_audio_ts = time.monotonic()
                self.latency_tracker.record_first_audio(req_id, first_audio_ts)
                audio_parts.append(first_audio_chunk)

                timings["tts_first_chunk_ms"] = round((first_audio_ts - t_tts_start) * 1000, 1)
                ref_origin = speech_end_ts or t_input
                timings["speech_to_first_audio_ms"] = round((first_audio_ts - ref_origin) * 1000, 1)
                logger.info(
                    "[%s] First Rime audio ready! Time from speech end: %.1fms",
                    req_id,
                    timings["speech_to_first_audio_ms"],
                )
            else:
                # Subsequent sentences synthesized in order
                part = await rime_tts.synthesize_chunk(
                    sentence,
                    request_id=req_id,
                    interruption_controller=self.interruption_controller,
                )
                audio_parts.append(part)

        t_pipeline_end = time.monotonic()
        response_text = " ".join(sentence_chunks).strip()
        timings["llm_total_ms"] = round((t_pipeline_end - t_llm_start) * 1000, 1)
        if first_token_ts:
            timings["llm_first_token_ms"] = round((first_token_ts - t_llm_start) * 1000, 1)

        # Concatenate audio parts if multiple chunks
        if not audio_parts:
            # Fallback if no sentences yielded
            audio_bytes = await rime_tts.synthesize_speech(
                response_text,
                request_id=req_id,
                interruption_controller=self.interruption_controller,
            )
        elif len(audio_parts) == 1:
            audio_bytes = audio_parts[0]
        else:
            audio_bytes = rime_tts._concatenate_wav(audio_parts)

        timings["total_ms"] = round((t_pipeline_end - t_input) * 1000, 1)
        logger.info("[%s] Pipeline complete in %.1fms", req_id, timings["total_ms"])

        return VoiceAgentResult(
            transcript=transcript,
            response_text=response_text,
            audio_bytes=audio_bytes,
            request_id=req_id,
            timings=timings,
            first_audio_bytes=first_audio_chunk,
        )
