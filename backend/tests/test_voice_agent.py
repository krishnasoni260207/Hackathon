import asyncio

from backend.agents.voice_agent import VoiceAgent


def test_voice_agent_mock_pipeline() -> None:
    agent = VoiceAgent()

    result = asyncio.run(agent.process_audio(b"fake-audio-bytes"))

    assert result.transcript
    assert result.response_text
    assert result.audio_bytes
    assert result.request_id


def test_voice_agent_creates_a_new_request_id_per_call() -> None:
    agent = VoiceAgent()

    first = asyncio.run(agent.process_audio(b"first-audio"))
    second = asyncio.run(agent.process_audio(b"second-audio"))

    assert first.request_id != second.request_id
