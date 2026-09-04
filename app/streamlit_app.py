from __future__ import annotations

import streamlit as st

from app.ui.components import (
    apply_base_styles,
    render_header,
    render_service_status,
    render_voice_controls,
)
from app.ui.conversation_view import render_conversation_panel
from app.ui.status_view import render_status_panel


def initialize_session_state() -> None:
    st.session_state.setdefault("voice_status", "Ready to listen")
    st.session_state.setdefault("microphone_status", "Disconnected (placeholder)")


def main() -> None:
    st.set_page_config(
        page_title="Interruptible Study Assistant",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    initialize_session_state()
    apply_base_styles()

    render_header()

    left_column, right_column = st.columns([1.8, 1], gap="large")

    with left_column:
        render_conversation_panel()

    with right_column:
        render_status_panel(st.session_state.voice_status)
        render_voice_controls()
        render_service_status()


if __name__ == "__main__":
    main()
