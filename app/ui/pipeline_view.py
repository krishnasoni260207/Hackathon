from __future__ import annotations

import asyncio
import base64
import os
from typing import Any

import streamlit as st
from streamlit.typing import ChatInputValue

from backend.agents import VoiceAgent
from backend.audio.interruption import InterruptionController, StaleRequestError, get_interruption_controller
from backend.audio.playback import get_playback_controller
from backend.metrics.interruption_metrics import get_latency_tracker
from backend.services import llm, rime_tts


def _get_interruption_controller() -> InterruptionController:
    if "interruption_controller" not in st.session_state or st.session_state.interruption_controller is None:
        st.session_state.interruption_controller = get_interruption_controller()
    return st.session_state.interruption_controller


# ---------------------------------------------------------------------------
# Input widgets
# ---------------------------------------------------------------------------

def render_voice_input() -> str | ChatInputValue | None:
    """Render the text chat input box (alternative to voice)."""
    return st.chat_input(
        "Type a study question…",
        key="voice_chat_input",
        accept_audio=False,
        submit_mode="disable",
    )


# ---------------------------------------------------------------------------
# Output display
# ---------------------------------------------------------------------------

def render_voice_console() -> None:
    """Render the main voice bot status panel with orb and stage indicators."""
    active = st.session_state.get("voice_session_active", False)
    recording = st.session_state.get("recording_active", False)
    status = st.session_state.get("voice_status", "Ready to listen")
    latest_type = st.session_state.get("latest_input_type") or "Waiting"
    current_stage = st.session_state.get("current_stage", "Idle")
    mode = os.environ.get("BACKEND_MODE", "mock").strip().lower()

    with st.container(border=True):
        st.subheader("Voice bot", icon=":material/graphic_eq:")
        st.html(
            _voice_hero_html(
                status=status,
                active=active,
                recording=recording,
                mode=mode,
                latest_type=latest_type,
            )
        )

        # Stage progression dots
        stages = ["Recording", "Transcribing", "Thinking", "Speaking", "Complete"]
        stage_map = {
            "Listening": 0,
            "Input captured": 0,
            "Transcribing speech": 1,
            "Generating answer": 2,
            "Synthesizing speech": 3,
            "Speaking": 3,
            "Output ready": 4,
            "Interrupted": -1,
            "Recovering": 0,
        }
        active_idx = stage_map.get(current_stage, -1)

        dots_html = '<div style="display:flex;gap:1rem;margin-top:1rem;font-size:0.9rem;">'
        for i, stage in enumerate(stages):
            is_on = i == active_idx
            color = "#0f766e" if is_on else "#dce2ea"
            weight = "600" if is_on else "400"
            text_color = "var(--ink)" if is_on else "var(--muted)"
            anim = "animation:stage-pulse 1s ease-in-out infinite;" if is_on else ""
            dots_html += (
                f'<div style="display:flex;align-items:center;gap:0.4rem;">'
                f'<div style="width:8px;height:8px;border-radius:50%;background:{color};{anim}"></div>'
                f'<span style="color:{text_color};font-weight:{weight}">{stage}</span>'
                f'</div>'
            )
        dots_html += "</div>"
        st.html(dots_html)

        cols = st.columns(3)
        cols[0].metric("Session", "Active" if active else "Idle")
        cols[1].metric("Stage", current_stage)
        cols[2].metric("Recording", "On" if recording else "Off")


def render_latest_output() -> None:
    """Render the output panel showing transcript, response, and audio."""
    with st.container(border=True):
        st.subheader("Output", icon=":material/speaker_notes:")

        # Show any error
        if st.session_state.latest_error:
            st.error(st.session_state.latest_error, icon=":material/error:")

        # Show the user's input recording
        if st.session_state.latest_user_audio_bytes:
            st.markdown("**Your recording**")
            name = st.session_state.latest_user_audio_name or "recording.webm"
            ext = name.rsplit(".", 1)[-1]
            st.audio(st.session_state.latest_user_audio_bytes, format=f"audio/{ext}")

        # Show transcript
        if st.session_state.latest_transcript:
            st.markdown("**Transcript** ✓")
            with st.container(border=True):
                st.write(st.session_state.latest_transcript)

        # Show LLM response
        if st.session_state.latest_response_text:
            st.markdown("**Assistant response** ✓")
            with st.container(border=True):
                st.write(st.session_state.latest_response_text)

        # Show generated speech audio (guarded against stale responses)
        controller = _get_interruption_controller()
        audio_bytes = st.session_state.latest_audio_bytes
        latest_req = st.session_state.get("latest_request_id", "")

        if audio_bytes and controller.is_current(latest_req):
            st.markdown("**Generated speech (Rime TTS)** ✓")
            st.audio(audio_bytes, format=_detect_audio_format(audio_bytes), autoplay=True)
        elif st.session_state.get("current_stage") in (
            "Input captured", "Transcribing speech",
            "Generating answer", "Synthesizing speech",
        ):
            with st.spinner(f"Processing: {st.session_state.get('current_stage')}…"):
                st.caption("Generating response…")
        elif st.session_state.get("current_stage") == "Interrupted":
            st.info("Previous speech was interrupted. Ready for your next question.", icon=":material/pause_circle:")
        elif not st.session_state.latest_error:
            st.caption("No generated speech yet.")

        # Display Latency & Interruption Measurement Table
        tracker = get_latency_tracker()
        summary_rows = tracker.format_summary_table()
        if summary_rows:
            st.markdown("**Latency & Interruption Instrumentation**")
            st.dataframe(
                summary_rows,
                column_config={
                    "Request": st.column_config.TextColumn("Request"),
                    "Speech End": st.column_config.TextColumn("Speech End (s)"),
                    "First Rime Audio": st.column_config.TextColumn("First Rime Audio (s)"),
                    "Latency": st.column_config.TextColumn("Latency (Speech → First Audio)"),
                    "Status": st.column_config.TextColumn("Status"),
                },
                hide_index=True,
                width="stretch",
            )


# ---------------------------------------------------------------------------
# Submission handling
# ---------------------------------------------------------------------------

def handle_voice_submission(submission: str | ChatInputValue | dict[str, Any]) -> None:
    """Route a user submission (text, chat input, or recorded audio dict) to the pipeline."""
    # Handle dict events from voice_recorder
    if isinstance(submission, dict):
        event_type = submission.get("type")
        if event_type == "interrupted":
            _handle_interruption_event(submission)
            return
        elif event_type == "playback_ended":
            _handle_playback_ended(submission)
            return
        _handle_recorded_audio(submission)
        return

    # Chat input may be text or have audio attached
    text, audio = _extract_chat_input(submission)
    st.session_state.last_pipeline_steps = []
    st.session_state.latest_error = ""

    if audio is not None:
        audio_bytes = audio.getvalue()
        st.session_state.latest_user_audio_bytes = audio_bytes
        st.session_state.latest_user_audio_name = getattr(audio, "name", "recording.wav")
        st.session_state.latest_input_type = "Voice recording"
        _run_audio_pipeline(audio_bytes, st.session_state.latest_user_audio_name)
        return

    if text:
        st.session_state.latest_user_audio_bytes = b""
        st.session_state.latest_user_audio_name = ""
        st.session_state.latest_input_type = "Typed prompt"
        _run_text_pipeline(text)
        return

    st.warning("Add text or record audio before submitting.", icon=":material/info:")


def _handle_interruption_event(event: dict[str, Any]) -> None:
    """Handle instant voice interruption emitted by browser microphone monitor."""
    req_id = event.get("request_id") or st.session_state.get("latest_request_id")
    controller = _get_interruption_controller()
    controller.interrupt(req_id)
    get_playback_controller().stop_playback(reason="interrupted")
    if req_id:
        get_latency_tracker().record_interruption(req_id, interruption_ts=event.get("timestamp"))

    st.session_state.latest_audio_bytes = b""
    st.session_state.latest_play_audio_base64 = ""
    st.session_state.cancel_playback = True
    st.session_state.current_stage = "Interrupted"
    st.session_state.voice_status = "Interrupted"
    st.session_state.microphone_status = "Listening"


def _handle_playback_ended(event: dict[str, Any]) -> None:
    """Handle clean playback completion emitted by browser audio player."""
    req_id = event.get("request_id") or st.session_state.get("latest_request_id")
    if req_id:
        get_playback_controller().complete_playback(req_id)
    if st.session_state.get("current_stage") == "Speaking":
        st.session_state.current_stage = "Output ready"
        st.session_state.voice_status = "Ready for next question"


# ---------------------------------------------------------------------------
# Pipeline runners
# ---------------------------------------------------------------------------

def _run_text_pipeline(question: str) -> None:
    """Run the LLM → TTS pipeline for a typed question (no STT needed)."""
    controller = _get_interruption_controller()
    request_id = controller.start_request()
    st.session_state.latest_request_id = request_id
    st.session_state.cancel_playback = False
    playback_controller = get_playback_controller()

    try:
        with st.status("Processing voice turn", expanded=True) as status:
            _set_stage("Input captured", "Listening")
            st.write("✓ Text input received")

            if not controller.is_current(request_id):
                st.write(f"⚠ Request {request_id[:6]} was superseded.")
                return

            _set_stage("Generating answer", "Thinking")
            st.write("→ Generating response…")
            response_text = _run_async(
                llm.generate_response(
                    question,
                    history=_conversation_history(),
                    request_id=request_id,
                    interruption_controller=controller,
                )
            )

            if not controller.is_current(request_id):
                st.write(f"⚠ Request {request_id[:6]} was interrupted. Stale audio discarded.")
                return

            st.write("✓ Response generated")

            _set_stage("Synthesizing speech", "Speaking")
            st.write("→ Converting to speech…")
            audio_bytes = _run_async(
                rime_tts.synthesize_speech(
                    response_text,
                    request_id=request_id,
                    interruption_controller=controller,
                )
            )

            if not controller.is_current(request_id):
                st.write(f"⚠ Request {request_id[:6]} was interrupted. Stale audio discarded.")
                return

            st.write("✓ Speech synthesized")
            _set_stage("Output ready", "Speaking")
            status.update(label="✓ Voice turn complete", state="complete", expanded=False)

        if controller.is_current(request_id):
            if playback_controller.start_playback(request_id, audio_bytes):
                get_latency_tracker().record_playback_started(request_id)
                st.session_state.latest_play_audio_base64 = base64.b64encode(audio_bytes).decode("ascii")
                st.session_state.latest_audio_bytes = audio_bytes

            _append_turn(question, response_text)
            st.session_state.latest_transcript = ""
            st.session_state.latest_response_text = response_text
            st.session_state.latest_error = ""
            st.session_state.voice_status = "Speaking"
            st.session_state.current_stage = "Speaking"
        else:
            st.session_state.latest_audio_bytes = b""
            st.session_state.latest_play_audio_base64 = ""

    except StaleRequestError:
        st.session_state.current_stage = "Interrupted"
        st.session_state.voice_status = "Interrupted"
        st.session_state.latest_audio_bytes = b""
        st.session_state.latest_play_audio_base64 = ""
    except Exception as exc:
        _handle_pipeline_error(exc)


def _run_audio_pipeline(audio_data: bytes, filename: str) -> None:
    """Run the full STT → LLM → TTS pipeline for recorded audio."""
    controller = _get_interruption_controller()
    request_id = controller.start_request()
    st.session_state.latest_request_id = request_id
    st.session_state.cancel_playback = False
    playback_controller = get_playback_controller()

    try:
        with st.status("Processing voice turn", expanded=True) as status:
            _set_stage("Input captured", "Listening")
            st.write("✓ Voice recording captured")

            if not controller.is_current(request_id):
                st.write(f"⚠ Request {request_id[:6]} was superseded.")
                return

            _set_stage("Transcribing speech", "Transcribing")
            st.write("→ Transcribing audio…")

            # VoiceAgent runs all 3 steps: STT → LLM → TTS with early sentence pipelining
            agent = VoiceAgent(interruption_controller=controller)
            result = _run_async(
                agent.process_audio(
                    audio_data,
                    history=_conversation_history(),
                    filename=filename,
                    request_id=request_id,
                )
            )

            # STALE CHECK: Before updating UI or playing, verify request is still current!
            if not controller.is_current(request_id):
                st.write(f"⚠ Request {request_id[:6]} was interrupted/superseded. Stale audio discarded.")
                return

            st.write(f"✓ Transcript: {result.transcript[:120]}")

            _set_stage("Generating answer", "Thinking")
            st.write(f"✓ Response: {result.response_text[:120]}")

            _set_stage("Synthesizing speech", "Speaking")
            st.write(f"✓ Speech generated ({len(result.audio_bytes):,} bytes)")

            _set_stage("Output ready", "Speaking")
            status.update(label="✓ Voice turn complete", state="complete", expanded=False)

        # STALE CHECK: Only allow the latest current request to reach playback!
        if controller.is_current(request_id):
            if playback_controller.start_playback(request_id, result.audio_bytes):
                get_latency_tracker().record_playback_started(request_id)
                st.session_state.latest_play_audio_base64 = base64.b64encode(result.audio_bytes).decode("ascii")
                st.session_state.latest_audio_bytes = result.audio_bytes

            _append_turn(result.transcript, result.response_text)
            st.session_state.latest_transcript = result.transcript
            st.session_state.latest_response_text = result.response_text
            st.session_state.latest_error = ""
            st.session_state.voice_status = "Speaking"
            st.session_state.microphone_status = "Ready"
            st.session_state.current_stage = "Speaking"
        else:
            st.session_state.latest_audio_bytes = b""
            st.session_state.latest_play_audio_base64 = ""

    except StaleRequestError:
        st.session_state.current_stage = "Interrupted"
        st.session_state.voice_status = "Interrupted"
        st.session_state.latest_audio_bytes = b""
        st.session_state.latest_play_audio_base64 = ""
    except Exception as exc:
        _handle_pipeline_error(exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _handle_recorded_audio(recording: dict[str, Any]) -> None:
    """Process audio captured by the voice recorder component."""
    if not st.session_state.get("voice_session_active"):
        return
    audio_bytes = recording.get("audio_data", b"")
    filename = recording.get("filename", "recording.webm")
    if not audio_bytes:
        return

    st.session_state.recording_active = False
    st.session_state.recording_stop_requested = False
    st.session_state.voice_status = "Processing recording"
    st.session_state.latest_user_audio_bytes = audio_bytes
    st.session_state.latest_user_audio_name = filename
    st.session_state.latest_input_type = "Voice recording"
    _run_audio_pipeline(audio_bytes, filename)


def _handle_pipeline_error(exc: Exception) -> None:
    """Store error info in session state and log traceback."""
    import traceback
    st.session_state.latest_error = f"Pipeline error: {exc}"
    st.session_state.voice_status = "Error — try again"
    st.session_state.current_stage = "Error"
    traceback.print_exc()


def _extract_chat_input(submission: str | ChatInputValue) -> tuple[str, Any | None]:
    """Extract text and optional audio from a Streamlit chat input value."""
    if isinstance(submission, str):
        return submission.strip(), None
    text = getattr(submission, "text", "") or ""
    audio = getattr(submission, "audio", None)
    return text.strip(), audio


def _set_stage(stage: str, status: str) -> None:
    """Update the current pipeline stage in session state."""
    st.session_state.current_stage = stage
    st.session_state.voice_status = status
    steps = st.session_state.setdefault("last_pipeline_steps", [])
    if stage not in steps:
        steps.append(stage)


def _conversation_history() -> list[dict[str, str]]:
    """Build conversation history list for the LLM from session messages."""
    return [
        {"role": msg["role"], "content": msg["text"]}
        for msg in st.session_state.get("messages", [])
    ]


def _append_turn(student_text: str, assistant_text: str) -> None:
    """Add a student/assistant exchange to session state messages."""
    st.session_state.messages.append(
        {"speaker": "Student", "role": "user", "text": student_text}
    )
    st.session_state.messages.append(
        {"speaker": "AI Assistant", "role": "assistant", "text": assistant_text}
    )


def _detect_audio_format(audio_bytes: bytes) -> str:
    """Detect audio format from file magic bytes."""
    if audio_bytes[:4] == b"RIFF":
        return "audio/wav"
    if audio_bytes[:3] == b"ID3" or audio_bytes[:2] == b"\xff\xfb":
        return "audio/mpeg"
    if audio_bytes[:4] == b"OggS":
        return "audio/ogg"
    return "audio/wav"


def _run_async(coro):
    """Run an async coroutine synchronously. Safe for Streamlit context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an existing event loop — create a new thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


def _voice_hero_html(
    status: str,
    active: bool,
    recording: bool,
    mode: str,
    latest_type: str,
) -> str:
    """Generate the HTML for the voice orb hero section."""
    active_class = (
        "active"
        if active or recording or status in {"Listening", "Recording", "Thinking", "Speaking"}
        else ""
    )
    stage = st.session_state.get("current_stage", "Idle")
    return f"""
    <div class="voice-hero">
        <div class="voice-hero-grid">
            <div class="voice-orb-wrap">
                <div class="voice-orb {active_class}">Voice</div>
                <div class="waveform {active_class}">
                    <span></span><span></span><span></span><span></span>
                    <span></span><span></span><span></span>
                </div>
            </div>
            <div class="voice-copy">
                <h2>{status}</h2>
                <p>Speak your question — the assistant will transcribe, answer, and read the response aloud.</p>
                <div class="signal-grid">
                    <div class="signal-card">
                        <div class="signal-label">Input</div>
                        <div class="signal-value">{latest_type}</div>
                    </div>
                    <div class="signal-card">
                        <div class="signal-label">Stage</div>
                        <div class="signal-value">{stage}</div>
                    </div>
                    <div class="signal-card">
                        <div class="signal-label">Mode</div>
                        <div class="signal-value">{mode}</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """
