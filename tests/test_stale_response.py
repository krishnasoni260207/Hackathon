import asyncio
import pytest

from backend.agents.voice_agent import VoiceAgent
from backend.audio.interruption import InterruptionController, StaleRequestError
from backend.audio.playback import PlaybackController, PlaybackState


def test_stale_audio_is_rejected_by_playback() -> None:
    """Test 4: Request A starts -> B interrupts A -> A finishes later -> A must NOT play."""
    controller = InterruptionController()
    playback = PlaybackController(interruption_controller=controller)

    # Request A starts
    req_a = controller.start_request()
    assert controller.is_current(req_a) is True

    # While A is processing, Request B interrupts / supersedes A
    req_b = controller.start_request()
    assert controller.is_current(req_a) is False
    assert controller.is_current(req_b) is True

    # Request A finishes late and tries to play its audio
    audio_a = b"RIFF-audio-A-finished-late"
    played_a = playback.start_playback(req_a, audio_a)

    # Verify A's result is discarded
    assert played_a is False
    assert playback.active_request_id is None

    # Only Request B can reach playback
    audio_b = b"RIFF-audio-B-valid"
    played_b = playback.start_playback(req_b, audio_b)

    assert played_b is True
    assert playback.active_request_id == req_b
    assert playback.is_playing() is True


def test_stale_response_never_resumes_old_audio() -> None:
    """Guarantees the system NEVER produces: A audio → B audio → A audio again."""
    controller = InterruptionController()
    playback = PlaybackController(interruption_controller=controller)

    # 1. Request A starts and plays
    req_a = controller.start_request()
    assert playback.start_playback(req_a, b"RIFF-audio-A-chunk1") is True

    # 2. Student interrupts A: "Wait! Explain respiration instead"
    playback.on_user_speech_detected()
    assert playback.is_playing() is False
    assert controller.is_current(req_a) is False

    # 3. Request B starts and plays
    req_b = controller.start_request()
    assert playback.start_playback(req_b, b"RIFF-audio-B") is True
    assert playback.active_request_id == req_b

    # 4. Old delayed chunk from Request A arrives
    old_delayed_chunk = b"RIFF-audio-A-chunk2-late"
    resumed = playback.start_playback(req_a, old_delayed_chunk)

    # Verify A's late chunk is strictly rejected and never resumes
    assert resumed is False
    assert playback.active_request_id == req_b
    assert playback.is_playing() is True


def test_stale_async_agent_pipeline_is_cancelled_and_discarded() -> None:
    """Verify that late async pipeline runs for stale requests raise StaleRequestError and cannot play."""
    async def _test():
        controller = InterruptionController()
        playback = PlaybackController(interruption_controller=controller)
        agent = VoiceAgent(interruption_controller=controller)

        req_a = controller.start_request()

        # Launch task A
        async def run_turn_a():
            await asyncio.sleep(0.05)
            controller.assert_current(req_a)
            return b"RIFF-audio-A"

        task_a = asyncio.create_task(run_turn_a())
        controller.register_task(req_a, task_a)

        # Immediately interrupt with request B
        req_b = controller.start_request()

        # Task A should raise StaleRequestError or be cancelled
        with pytest.raises((StaleRequestError, asyncio.CancelledError)):
            await task_a

        # Request B proceeds normally to playback
        b_result = await agent.process_audio(b"fake-audio-b", request_id=req_b)
        assert playback.start_playback(req_b, b_result.audio_bytes) is True
        assert playback.active_request_id == req_b

    asyncio.run(_test())
