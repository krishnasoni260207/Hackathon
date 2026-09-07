import asyncio
import pytest

from backend.audio.interruption import InterruptionController
from backend.audio.playback import PlaybackController, PlaybackState


def test_new_request_becomes_current() -> None:
    controller = InterruptionController()
    request_id = controller.start_request()
    assert controller.is_current(request_id) is True


def test_each_request_gets_a_unique_id() -> None:
    controller = InterruptionController()
    first_id = controller.start_request()
    second_id = controller.start_request()
    assert first_id
    assert second_id
    assert first_id != second_id


def test_new_request_makes_previous_request_stale() -> None:
    controller = InterruptionController()
    first_id = controller.start_request()
    second_id = controller.start_request()
    assert controller.is_current(first_id) is False
    assert controller.is_current(second_id) is True


def test_interrupt_invalidates_current_request() -> None:
    controller = InterruptionController()
    request_id = controller.start_request()
    controller.interrupt()
    assert controller.is_current(request_id) is False


def test_no_current_request_after_interrupt() -> None:
    controller = InterruptionController()
    controller.start_request()
    controller.interrupt()
    assert controller.current_request_id() is None


def test_interrupt_without_active_request_is_safe() -> None:
    controller = InterruptionController()
    controller.interrupt()
    assert controller.current_request_id() is None


def test_old_request_stays_stale_after_new_request() -> None:
    controller = InterruptionController()
    old_request = controller.start_request()
    controller.interrupt()
    new_request = controller.start_request()
    assert controller.is_current(old_request) is False
    assert controller.is_current(new_request) is True
    assert controller.current_request_id() == new_request


# ===========================================================================
# Test 1 — Normal response: Request → response → audio playback
# ===========================================================================

def test_normal_request_response_audio_playback() -> None:
    controller = InterruptionController()
    playback = PlaybackController(interruption_controller=controller)

    req_id = controller.start_request()
    fake_audio = b"RIFFfake-wav-audio-content"

    started = playback.start_playback(req_id, fake_audio)
    assert started is True
    assert playback.is_playing() is True
    assert playback.active_request_id == req_id
    assert playback.state == PlaybackState.PLAYING

    playback.complete_playback(req_id)
    assert playback.is_playing() is False
    assert playback.state == PlaybackState.COMPLETED


# ===========================================================================
# Test 2 — Interrupt during speaking: Request A starts speaking → user interrupts → A stops
# ===========================================================================

def test_interrupt_during_speaking_stops_audio() -> None:
    controller = InterruptionController()
    playback = PlaybackController(interruption_controller=controller)

    req_a = controller.start_request()
    playback.start_playback(req_a, b"RIFF-audio-A")
    assert playback.is_playing() is True

    # User speaks while AI is speaking -> real interruption
    interrupted_id = playback.on_user_speech_detected()

    assert interrupted_id == req_a
    assert playback.is_playing() is False
    assert playback.state == PlaybackState.INTERRUPTED
    assert controller.is_current(req_a) is False
    assert controller.current_request_id() is None


# ===========================================================================
# Test 3 — New request after interruption: A interrupted → B requested → B speaks correctly
# ===========================================================================

def test_new_request_after_interruption_speaks_correctly() -> None:
    controller = InterruptionController()
    playback = PlaybackController(interruption_controller=controller)

    # Turn A
    req_a = controller.start_request()
    playback.start_playback(req_a, b"RIFF-audio-A")

    # Interruption
    playback.on_user_speech_detected()
    assert playback.is_playing() is False

    # Turn B (new user request)
    req_b = controller.start_request()
    started_b = playback.start_playback(req_b, b"RIFF-audio-B")

    assert started_b is True
    assert playback.is_playing() is True
    assert playback.active_request_id == req_b
    assert controller.is_current(req_b) is True
    assert controller.is_current(req_a) is False


# ===========================================================================
# Test 6 — No overlapping audio: Old and new responses cannot play simultaneously
# ===========================================================================

def test_no_overlapping_audio_playback() -> None:
    controller = InterruptionController()
    playback = PlaybackController(interruption_controller=controller)

    req_1 = controller.start_request()
    playback.start_playback(req_1, b"RIFF-audio-1")
    assert playback.active_request_id == req_1

    # Starting request 2 immediately halts request 1's audio
    req_2 = controller.start_request()
    started_2 = playback.start_playback(req_2, b"RIFF-audio-2")

    assert started_2 is True
    assert playback.active_request_id == req_2
    assert controller.is_current(req_1) is False

    # Attempting to resume or play req_1's audio must fail and not overlap
    stale_play = playback.start_playback(req_1, b"RIFF-audio-1-stale")
    assert stale_play is False
    # Only req_2 remains playing
    assert playback.active_request_id == req_2
    assert playback.is_playing() is True


# ===========================================================================
# Async Task Cancellation upon Interruption
# ===========================================================================

def test_interrupt_cancels_running_async_tasks() -> None:
    async def _test():
        controller = InterruptionController()
        req_id = controller.start_request()

        task_cancelled = False

        async def long_running_work():
            nonlocal task_cancelled
            try:
                await asyncio.sleep(10.0)
            except asyncio.CancelledError:
                task_cancelled = True
                raise

        task = asyncio.create_task(long_running_work(), name="mock_llm_task")
        controller.register_task(req_id, task)

        # Trigger interruption
        controller.interrupt(req_id)

        # Allow event loop to process cancellation
        await asyncio.sleep(0.01)

        assert task.cancelled() or task_cancelled is True
        assert controller.is_current(req_id) is False

    asyncio.run(_test())


# ===========================================================================
# Latency & Instrumentation Tests (Section 12)
# ===========================================================================

def test_latency_tracker_records_pipeline_timestamps() -> None:
    from backend.metrics.interruption_metrics import LatencyTracker

    tracker = LatencyTracker()
    req_id = "req-12345"

    t0 = 1000.0
    tracker.start_turn(req_id, speech_end_ts=t0, input_received_ts=t0 + 0.05)
    tracker.record_stt_completed(req_id, ts=t0 + 0.35)
    tracker.record_llm_started(req_id, ts=t0 + 0.36)
    tracker.record_llm_first_token(req_id, ts=t0 + 0.55)
    tracker.record_tts_started(req_id, ts=t0 + 0.60)
    tracker.record_first_audio(req_id, ts=t0 + 0.90)
    tracker.record_playback_started(req_id, ts=t0 + 0.95)

    metrics = tracker.get_metrics(req_id)
    assert metrics is not None
    # End of user speech -> first audible Rime audio
    assert metrics.speech_end_to_first_audio_ms == 950.0
    # STT duration
    assert metrics.stt_duration_ms == 300.0
    # LLM first token
    assert metrics.llm_first_token_ms == 190.0
    # TTS first chunk
    assert metrics.tts_first_chunk_ms == 300.0


def test_latency_summary_table_format() -> None:
    from backend.metrics.interruption_metrics import LatencyTracker

    tracker = LatencyTracker()
    tracker.start_turn("req-abc12345", speech_end_ts=100.0)
    tracker.record_first_audio("req-abc12345", ts=100.45)

    table = tracker.format_summary_table()
    assert len(table) == 1
    row = table[0]
    assert "Request" in row
    assert "Speech End" in row
    assert "First Rime Audio" in row
    assert "Latency" in row
    assert row["Latency"] == "450.0 ms"

