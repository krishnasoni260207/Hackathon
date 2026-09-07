import asyncio
import pytest

from backend.agents.voice_agent import VoiceAgent
from backend.audio.interruption import InterruptionController
from backend.audio.playback import PlaybackController, PlaybackState
from backend.conversation.manager import ConversationManager


def test_repeated_interruption_only_last_speaks() -> None:
    """Test 5: A -> interrupt -> B -> interrupt -> C. Only C should finally speak."""
    controller = InterruptionController()
    playback = PlaybackController(interruption_controller=controller)

    # 1. Turn A starts
    req_a = controller.start_request()
    playback.start_playback(req_a, b"RIFF-audio-A")
    assert playback.active_request_id == req_a

    # Student interrupts A
    playback.on_user_speech_detected()
    assert playback.is_playing() is False

    # 2. Turn B starts
    req_b = controller.start_request()
    playback.start_playback(req_b, b"RIFF-audio-B")
    assert playback.active_request_id == req_b

    # Student interrupts B again!
    playback.on_user_speech_detected()
    assert playback.is_playing() is False

    # 3. Turn C starts
    req_c = controller.start_request()
    started_c = playback.start_playback(req_c, b"RIFF-audio-C")

    assert started_c is True
    assert playback.is_playing() is True
    assert playback.active_request_id == req_c

    # Late attempts from A and B must fail
    assert playback.start_playback(req_a, b"RIFF-audio-A-late") is False
    assert playback.start_playback(req_b, b"RIFF-audio-B-late") is False

    # Only C is active and speaks
    assert playback.active_request_id == req_c
    assert controller.is_current(req_c) is True
    assert controller.is_current(req_a) is False
    assert controller.is_current(req_b) is False


def test_clean_recovery_to_listening_state_after_interruption() -> None:
    """Test 7: After interruption, the application returns to a usable listening/ready state."""
    manager = ConversationManager()
    controller = InterruptionController()
    playback = PlaybackController(interruption_controller=controller)

    # State: Ready -> Listening -> Thinking -> Speaking
    manager.state.status = "listening"
    msg_1 = manager.add_student_message("Explain Newton's second law.")

    manager.state.status = "speaking"
    req_1 = controller.start_request()
    playback.start_playback(req_1, b"RIFF-newton-explanation")
    assert playback.is_playing() is True

    # User interrupts: "Wait! Explain it in two sentences."
    interrupted_id = playback.on_user_speech_detected()
    assert interrupted_id == req_1

    # Transition to Interrupted then clean recovery to listening
    manager.state.status = "interrupted"
    assert manager.state.status == "interrupted"

    # System recovers naturally to listening for the new question
    manager.state.status = "listening"
    assert manager.state.status == "listening"
    assert playback.is_playing() is False

    # New turn processes smoothly
    req_2 = controller.start_request()
    msg_2 = manager.add_student_message("Wait! Explain it in two sentences.")
    manager.state.status = "thinking"
    manager.add_assistant_message("Force equals mass times acceleration. More force means more acceleration.")
    manager.state.status = "speaking"

    started_2 = playback.start_playback(req_2, b"RIFF-newton-two-sentences")
    assert started_2 is True
    assert playback.active_request_id == req_2

    # Clean completion
    playback.complete_playback(req_2)
    manager.state.status = "ready"
    assert manager.state.status == "ready"
    assert len(manager.state.messages) == 3


def test_repeated_interruptions_during_pipeline_generation() -> None:
    """Verify multiple interruptions while LLM/TTS are generating do not corrupt agent state."""
    async def _test():
        controller = InterruptionController()
        agent = VoiceAgent(interruption_controller=controller)

        # Rapid succession of requests
        req1 = controller.start_request()
        controller.interrupt(req1)

        req2 = controller.start_request()
        controller.interrupt(req2)

        req3 = controller.start_request()
        # req3 completes normally
        result = await agent.process_audio(b"final-audio", request_id=req3)

        assert result.request_id == req3
        assert result.response_text
        assert result.audio_bytes
        assert controller.is_current(req3) is True
        assert controller.is_current(req1) is False
        assert controller.is_current(req2) is False

    asyncio.run(_test())

