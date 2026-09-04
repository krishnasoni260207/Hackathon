from __future__ import annotations

import streamlit as st


STATUS_DETAILS = {
    "Ready to listen": "The UI is idle and waiting for a future voice session.",
    "Listening": "Placeholder state for when microphone capture is added later.",
    "Thinking": "Placeholder state for when an LLM request is added later.",
    "Speaking": "Placeholder state for when Rime TTS playback is added later.",
}


def render_status_panel(current_status: str) -> None:
    with st.container(border=True):
        st.subheader("Assistant Status")
        st.markdown(f"**{current_status}**")

        for status, description in STATUS_DETAILS.items():
            active_class = " status-card-active" if status == current_status else ""
            st.markdown(
                f"""
                <div class="status-card{active_class}">
                    <div class="status-label">{status}</div>
                    <div class="status-copy">{description}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
