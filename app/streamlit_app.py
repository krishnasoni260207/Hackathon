"""Streamlit entry point for the Interruptible Study Assistant.

Run with:  streamlit run app/streamlit_app.py
"""
from __future__ import annotations

from pathlib import Path
import sys

from dotenv import load_dotenv
import streamlit as st

# ---------------------------------------------------------------------------
# Path setup — ensure project root and app dir are importable
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = Path(__file__).resolve().parent

for _path in (PROJECT_ROOT, APP_DIR):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

# ---------------------------------------------------------------------------
# Local imports (after path setup)
# ---------------------------------------------------------------------------
from app.ui.components import (
    apply_base_styles,
    render_header,
    render_service_status,
    render_voice_controls,
)
from app.ui.conversation_view import render_conversation_panel
from app.ui.pipeline_view import (
    handle_voice_submission,
    render_latest_output,
    render_voice_console,
    render_voice_input,
)
from app.ui.status_view import render_status_panel
from app.ui.voice_recorder import render_voice_recorder


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def _init_session_state() -> None:
    """Initialize all session state keys with sensible defaults."""
    defaults = {
        "voice_status": "Ready to listen",
        "microphone_status": "Disconnected",
        "voice_session_active": False,
        "recording_active": False,
        "voice_session_id": "",
        "recording_stop_requested": False,
        "messages": [],
        "current_stage": "Idle",
        "last_pipeline_steps": [],
        "latest_input_type": "",
        "latest_user_audio_bytes": b"",
        "latest_user_audio_name": "",
        "latest_transcript": "",
        "latest_response_text": "",
        "latest_audio_bytes": b"",
        "latest_play_audio_base64": "",
        "cancel_playback": False,
        "latest_request_id": "",
        "latest_error": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    st.set_page_config(
        page_title="Interruptible Study Assistant",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    _init_session_state()
    apply_base_styles()
    render_header()
    render_voice_controls()

    # ---- Voice recorder (active when session is active or recording) ----
    if st.session_state.get("voice_session_active") or st.session_state.get("recording_active"):
        recorded_event = render_voice_recorder(
            active=True,
            session_id=st.session_state.voice_session_id,
            play_audio_base64=st.session_state.get("latest_play_audio_base64", ""),
            play_request_id=st.session_state.get("latest_request_id", ""),
            cancel_playback=st.session_state.get("cancel_playback", False),
        )
        if recorded_event:
            handle_voice_submission(recorded_event)

    # ---- Typed input alternative ----
    with st.expander("Type a question instead", expanded=False):
        text_submission = render_voice_input()
        if text_submission:
            handle_voice_submission(text_submission)

    # ---- Two-column layout: voice console + output ----
    voice_col, output_col = st.columns([1.15, 0.85], gap="large")

    with voice_col:
        render_voice_console()
        render_conversation_panel(st.session_state.messages)

    with output_col:
        render_latest_output()
        render_status_panel(st.session_state.voice_status)
        render_service_status()


if __name__ == "__main__":
    main()
