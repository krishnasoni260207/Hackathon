"""Shared UI components — styles, header, session controls, and service status."""
from __future__ import annotations

import os
import uuid

import streamlit as st


# ---------------------------------------------------------------------------
# Session control callbacks
# ---------------------------------------------------------------------------

def _start_session() -> None:
    """Initialize a new voice session."""
    st.session_state.voice_session_active = True
    st.session_state.recording_active = False
    st.session_state.recording_stop_requested = False
    st.session_state.cancel_playback = False
    st.session_state.latest_play_audio_base64 = ""
    st.session_state.voice_session_id = str(uuid.uuid4())
    st.session_state.voice_status = "Session started"
    st.session_state.microphone_status = "Ready"
    st.session_state.current_stage = "Idle"


def _toggle_recording() -> None:
    """Start or stop recording based on current state."""
    if not st.session_state.get("voice_session_active"):
        return

    if st.session_state.get("recording_active"):
        # Stop recording → triggers submission
        st.session_state.recording_stop_requested = True
        st.session_state.voice_status = "Processing"
        st.session_state.current_stage = "Input captured"
    else:
        # Start recording
        st.session_state.recording_active = True
        st.session_state.recording_stop_requested = False
        st.session_state.cancel_playback = False
        st.session_state.voice_session_id = str(uuid.uuid4())
        st.session_state.voice_status = "Recording — speak now"
        st.session_state.microphone_status = "Recording"
        st.session_state.current_stage = "Listening"


def _end_session() -> None:
    """End the current voice session."""
    st.session_state.voice_session_active = False
    st.session_state.recording_active = False
    st.session_state.recording_stop_requested = False
    st.session_state.cancel_playback = True
    st.session_state.latest_play_audio_base64 = ""
    st.session_state.voice_status = "Ready to listen"
    st.session_state.microphone_status = "Disconnected"
    st.session_state.current_stage = "Idle"


def _clear_output() -> None:
    """Clear all pipeline output from session state."""
    st.session_state.recording_active = False
    st.session_state.recording_stop_requested = False
    st.session_state.cancel_playback = True
    st.session_state.latest_play_audio_base64 = ""
    st.session_state.latest_input_type = ""
    st.session_state.latest_user_audio_bytes = b""
    st.session_state.latest_user_audio_name = ""
    st.session_state.latest_transcript = ""
    st.session_state.latest_response_text = ""
    st.session_state.latest_audio_bytes = b""
    st.session_state.latest_request_id = ""
    st.session_state.latest_error = ""
    st.session_state.last_pipeline_steps = []
    st.session_state.current_stage = "Idle"
    st.session_state.voice_status = "Ready to listen"


# ---------------------------------------------------------------------------
# Base styles
# ---------------------------------------------------------------------------

def apply_base_styles() -> None:
    """Inject global CSS styles into the Streamlit app."""
    st.html(
        """
        <style>
            :root {
                --surface: #f5f7fb;
                --panel: #ffffff;
                --ink: #1d2733;
                --muted: #647084;
                --line: #dce2ea;
                --teal: #0f766e;
                --blue: #2563eb;
                --amber: #b45309;
                --rose: #be123c;
                --green-soft: #ecfdf5;
                --blue-soft: #eff6ff;
            }

            .stApp {
                background: var(--surface);
                color: var(--ink);
            }

            .block-container {
                max-width: 1180px;
                padding-top: 2rem;
                padding-bottom: 2.5rem;
            }

            h1, h2, h3 { letter-spacing: 0; }

            .app-header {
                border-bottom: 1px solid var(--line);
                padding-bottom: 1.15rem;
                margin-bottom: 1rem;
            }

            .app-subtitle {
                color: var(--muted);
                font-size: 1.05rem;
                margin-top: -0.25rem;
            }

            /* Voice orb */
            .voice-hero {
                background: linear-gradient(135deg, #ffffff 0%, #eef8f5 46%, #f8fbff 100%);
                border: 1px solid var(--line);
                border-radius: 8px;
                padding: 1.25rem;
                margin-bottom: 1rem;
            }

            .voice-hero-grid {
                align-items: center;
                display: grid;
                gap: 1.1rem;
                grid-template-columns: minmax(180px, 0.8fr) minmax(240px, 1.2fr);
            }

            @media (max-width: 760px) {
                .voice-hero-grid { grid-template-columns: 1fr; }
            }

            .voice-orb-wrap {
                align-items: center;
                display: flex;
                flex-direction: column;
                gap: 0.75rem;
                justify-content: center;
                min-height: 230px;
            }

            .voice-orb {
                align-items: center;
                background: radial-gradient(circle at 35% 30%, #ffffff, #a7f3d0 33%, #0f766e 72%);
                border: 1px solid rgba(15, 118, 110, 0.22);
                border-radius: 999px;
                box-shadow: 0 18px 48px rgba(15, 118, 110, 0.23);
                color: #073b35;
                display: flex;
                font-size: 0.82rem;
                font-weight: 800;
                height: 154px;
                justify-content: center;
                letter-spacing: 0.08em;
                position: relative;
                text-transform: uppercase;
                width: 154px;
            }

            .voice-orb.active::before,
            .voice-orb.active::after {
                animation: pulse-ring 1.7s ease-out infinite;
                border: 1px solid rgba(15, 118, 110, 0.28);
                border-radius: 999px;
                content: "";
                inset: -15px;
                position: absolute;
            }

            .voice-orb.active::after {
                animation-delay: 0.55s;
                inset: -28px;
            }

            @keyframes pulse-ring {
                0% { opacity: 0.75; transform: scale(0.92); }
                100% { opacity: 0; transform: scale(1.16); }
            }

            /* Waveform bars */
            .waveform {
                align-items: center;
                display: flex;
                gap: 5px;
                height: 42px;
                justify-content: center;
            }

            .waveform span {
                background: var(--teal);
                border-radius: 999px;
                display: block;
                height: 12px;
                opacity: 0.35;
                width: 6px;
            }

            .waveform.active span {
                animation: voice-wave 1s ease-in-out infinite;
                opacity: 0.86;
            }

            .waveform span:nth-child(2) { animation-delay: 0.08s; height: 22px; }
            .waveform span:nth-child(3) { animation-delay: 0.16s; height: 32px; }
            .waveform span:nth-child(4) { animation-delay: 0.24s; height: 20px; }
            .waveform span:nth-child(5) { animation-delay: 0.32s; height: 34px; }
            .waveform span:nth-child(6) { animation-delay: 0.40s; height: 24px; }
            .waveform span:nth-child(7) { animation-delay: 0.48s; height: 14px; }

            @keyframes voice-wave {
                0%, 100% { transform: scaleY(0.55); }
                50% { transform: scaleY(1.35); }
            }

            /* Copy area */
            .voice-copy h2 {
                font-size: clamp(1.4rem, 2.5vw, 2.2rem);
                line-height: 1.08;
                margin: 0 0 0.55rem;
            }

            .voice-copy p {
                color: var(--muted);
                font-size: 1rem;
                margin: 0;
            }

            /* Signal cards */
            .signal-grid {
                display: grid;
                gap: 0.7rem;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                margin-top: 1rem;
            }

            @media (max-width: 760px) {
                .signal-grid { grid-template-columns: 1fr; }
            }

            .signal-card {
                background: rgba(255, 255, 255, 0.72);
                border: 1px solid var(--line);
                border-radius: 8px;
                padding: 0.7rem;
            }

            .signal-label {
                color: var(--muted);
                font-size: 0.78rem;
                margin-bottom: 0.2rem;
            }

            .signal-value {
                color: var(--ink);
                font-size: 0.95rem;
                font-weight: 750;
            }

            /* Status cards */
            .status-card {
                border: 1px solid var(--line);
                border-radius: 8px;
                background: var(--panel);
                padding: 0.8rem 0.9rem;
                margin-bottom: 0.65rem;
            }

            .status-card-active {
                border-color: rgba(15, 118, 110, 0.45);
                box-shadow: inset 4px 0 0 var(--teal);
            }

            .status-card-complete {
                background: var(--green-soft);
                border-color: rgba(15, 118, 110, 0.28);
            }

            .status-label { font-weight: 700; margin-bottom: 0.15rem; }
            .status-copy { color: var(--muted); font-size: 0.9rem; }

            /* Stage pulse */
            @keyframes stage-pulse {
                0%, 100% { transform: scale(1); opacity: 1; }
                50% { transform: scale(1.3); opacity: 0.7; }
            }

            /* Service rows */
            .service-row {
                align-items: center;
                border-top: 1px solid var(--line);
                display: flex;
                justify-content: space-between;
                gap: 1rem;
                padding: 0.65rem 0;
            }

            .service-row:first-of-type { border-top: 0; }
            .service-name { font-weight: 650; }

            .service-state {
                color: var(--amber);
                font-size: 0.86rem;
                white-space: nowrap;
            }

            div[data-testid="stMetricValue"] { font-size: 1.2rem; }
        </style>
        """
    )


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def render_header() -> None:
    """Render the app header with title and subtitle."""
    st.markdown(
        """
        <div class="app-header">
            <h1>Interruptible Study Assistant</h1>
            <div class="app-subtitle">A voice-first study companion for university students</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Voice session controls
# ---------------------------------------------------------------------------

def render_voice_controls() -> None:
    """Render session and recording controls.

    Flow:
    1. Click "Start session" to enable recording.
    2. Click "🎙 Record" to start → it changes to "⏹ Stop & Submit".
    3. Recording auto-stops on silence, or click "⏹ Stop & Submit" manually.
    4. Click "End session" when done.
    """
    session_active = st.session_state.get("voice_session_active", False)
    recording = st.session_state.get("recording_active", False)

    with st.container(border=True):
        st.subheader("Session controls", icon=":material/tune:")

        with st.container(horizontal=True, horizontal_alignment="distribute"):
            st.button(
                "Start session",
                key="start_session_button",
                icon=":material/play_circle:",
                on_click=_start_session,
                type="primary",
                width="stretch",
                disabled=session_active,
            )
            st.button(
                "⏹ Stop & Submit" if recording else "🎙 Record",
                key="toggle_record_button",
                icon=":material/stop:" if recording else ":material/mic:",
                on_click=_toggle_recording,
                type="primary",
                width="stretch",
                disabled=not session_active,
            )
            st.button(
                "End session",
                key="end_session_button",
                icon=":material/stop_circle:",
                on_click=_end_session,
                width="stretch",
                disabled=not session_active,
            )

        st.button(
            "Clear output",
            key="clear_voice_output_button",
            icon=":material/refresh:",
            on_click=_clear_output,
            width="stretch",
        )

        cols = st.columns(2)
        cols[0].metric("Session", "Active" if session_active else "Idle")
        cols[1].metric("Microphone", st.session_state.microphone_status)


# ---------------------------------------------------------------------------
# Service status
# ---------------------------------------------------------------------------

def render_service_status() -> None:
    """Render the connections panel showing API configuration status."""
    mode = os.environ.get("BACKEND_MODE", "mock").strip().lower()
    services = [
        ("Speech-to-Text (Deepgram)", _api_state(mode, "DEEPGRAM_API_KEY")),
        ("LLM (OpenRouter)", _api_state(mode, "OPENROUTER_API_KEY")),
        ("Rime TTS", _api_state(mode, "RIME_API_KEY")),
    ]

    with st.container(border=True):
        st.subheader("Connections", icon=":material/settings_input_component:")
        st.badge(f"Backend mode: {mode}", color="blue")

        rows_html = "".join(
            f"""
            <div class="service-row">
                <span class="service-name">{name}</span>
                <span class="service-state">{state}</span>
            </div>
            """
            for name, state in services
        )
        st.markdown(rows_html, unsafe_allow_html=True)


def _api_state(mode: str, key_name: str) -> str:
    """Return a human-readable status string for an API key."""
    if mode != "real":
        return "Mock mode"
    return "✓ Configured" if os.environ.get(key_name) else f"⚠ Needs {key_name}"
