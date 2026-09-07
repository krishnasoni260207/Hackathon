from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TurnMetrics:
    """Latency and timestamp instrumentation for a single voice turn or request."""

    request_id: str
    speech_end_ts: Optional[float] = None
    input_received_ts: Optional[float] = None
    stt_completed_ts: Optional[float] = None
    llm_started_ts: Optional[float] = None
    llm_first_token_ts: Optional[float] = None
    tts_started_ts: Optional[float] = None
    first_audio_ts: Optional[float] = None
    playback_started_ts: Optional[float] = None
    interruption_ts: Optional[float] = None
    playback_stopped_ts: Optional[float] = None
    interrupted: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def speech_end_to_first_audio_ms(self) -> Optional[float]:
        """Core target metric: end of user speech -> first audible Rime audio."""
        ref_start = self.speech_end_ts or self.input_received_ts
        ref_end = self.playback_started_ts or self.first_audio_ts
        if ref_start is not None and ref_end is not None and ref_end >= ref_start:
            return round((ref_end - ref_start) * 1000, 1)
        return None

    @property
    def stt_duration_ms(self) -> Optional[float]:
        if self.input_received_ts is not None and self.stt_completed_ts is not None:
            return round((self.stt_completed_ts - self.input_received_ts) * 1000, 1)
        return None

    @property
    def llm_first_token_ms(self) -> Optional[float]:
        if self.llm_started_ts is not None and self.llm_first_token_ts is not None:
            return round((self.llm_first_token_ts - self.llm_started_ts) * 1000, 1)
        return None

    @property
    def tts_first_chunk_ms(self) -> Optional[float]:
        if self.tts_started_ts is not None and self.first_audio_ts is not None:
            return round((self.first_audio_ts - self.tts_started_ts) * 1000, 1)
        return None

    @property
    def total_response_latency_ms(self) -> Optional[float]:
        ref_start = self.input_received_ts or self.speech_end_ts
        ref_end = self.playback_started_ts or self.first_audio_ts
        if ref_start is not None and ref_end is not None and ref_end >= ref_start:
            return round((ref_end - ref_start) * 1000, 1)
        return None

    @property
    def interruption_latency_ms(self) -> Optional[float]:
        """Interruption detected -> old playback stopped."""
        if self.interruption_ts is not None and self.playback_stopped_ts is not None:
            return round(max(0.0, (self.playback_stopped_ts - self.interruption_ts) * 1000), 1)
        return None


class LatencyTracker:
    """Thread-safe collector for voice turn latency metrics and timestamps."""

    def __init__(self) -> None:
        self._turns: dict[str, TurnMetrics] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def start_turn(
        self,
        request_id: str,
        speech_end_ts: Optional[float] = None,
        input_received_ts: Optional[float] = None,
    ) -> TurnMetrics:
        with self._lock:
            metrics = TurnMetrics(
                request_id=request_id,
                speech_end_ts=speech_end_ts,
                input_received_ts=input_received_ts or time.monotonic(),
            )
            self._turns[request_id] = metrics
            if request_id not in self._order:
                self._order.append(request_id)
            return metrics

    def record_stt_completed(self, request_id: str, ts: Optional[float] = None) -> None:
        with self._lock:
            if request_id in self._turns:
                self._turns[request_id].stt_completed_ts = ts or time.monotonic()

    def record_llm_started(self, request_id: str, ts: Optional[float] = None) -> None:
        with self._lock:
            if request_id in self._turns:
                self._turns[request_id].llm_started_ts = ts or time.monotonic()

    def record_llm_first_token(self, request_id: str, ts: Optional[float] = None) -> None:
        with self._lock:
            if request_id in self._turns:
                self._turns[request_id].llm_first_token_ts = ts or time.monotonic()

    def record_tts_started(self, request_id: str, ts: Optional[float] = None) -> None:
        with self._lock:
            if request_id in self._turns:
                self._turns[request_id].tts_started_ts = ts or time.monotonic()

    def record_first_audio(self, request_id: str, ts: Optional[float] = None) -> None:
        with self._lock:
            if request_id in self._turns:
                self._turns[request_id].first_audio_ts = ts or time.monotonic()

    def record_playback_started(self, request_id: str, ts: Optional[float] = None) -> None:
        with self._lock:
            if request_id in self._turns:
                self._turns[request_id].playback_started_ts = ts or time.monotonic()

    def record_interruption(
        self,
        request_id: str,
        interruption_ts: Optional[float] = None,
        stopped_ts: Optional[float] = None,
    ) -> None:
        with self._lock:
            if request_id in self._turns:
                metrics = self._turns[request_id]
                metrics.interrupted = True
                metrics.interruption_ts = interruption_ts or time.monotonic()
                metrics.playback_stopped_ts = stopped_ts or time.monotonic()

    def get_metrics(self, request_id: str) -> Optional[TurnMetrics]:
        with self._lock:
            return self._turns.get(request_id)

    def get_all_metrics(self) -> list[TurnMetrics]:
        with self._lock:
            return [self._turns[req_id] for req_id in self._order if req_id in self._turns]

    def format_summary_table(self) -> list[dict[str, str]]:
        """Format metrics into a table matching the requirement:
        Request | Speech End | First Rime Audio | Latency
        """
        rows: list[dict[str, str]] = []
        metrics_list = self.get_all_metrics()
        for idx, m in enumerate(metrics_list, start=1):
            speech_end_str = (
                f"{m.speech_end_ts:.3f}" if m.speech_end_ts is not None else (
                    f"{m.input_received_ts:.3f}" if m.input_received_ts is not None else "-"
                )
            )
            first_audio_str = (
                f"{m.first_audio_ts:.3f}" if m.first_audio_ts is not None else (
                    f"{m.playback_started_ts:.3f}" if m.playback_started_ts is not None else "-"
                )
            )
            lat = m.speech_end_to_first_audio_ms
            lat_str = f"{lat} ms" if lat is not None else ("Interrupted" if m.interrupted else "-")

            rows.append({
                "Request": f"#{idx} ({m.request_id[:6]})",
                "Speech End": speech_end_str,
                "First Rime Audio": first_audio_str,
                "Latency": lat_str,
                "Status": "Interrupted" if m.interrupted else "Completed",
            })
        return rows


_global_tracker = LatencyTracker()


def get_latency_tracker() -> LatencyTracker:
    return _global_tracker


def record_interruption_latency(latency_ms: float) -> None:
    """Phase 1 placeholder compatibility function."""
    logger.info("Interruption latency recorded: %.1f ms", latency_ms)

