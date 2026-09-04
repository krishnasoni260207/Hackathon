from __future__ import annotations

import streamlit as st


def _set_voice_placeholder(status: str, microphone_status: str) -> None:
    st.session_state.voice_status = status
    st.session_state.microphone_status = microphone_status


def apply_base_styles() -> None:
    st.markdown(
        """
        <style>
            :root {
                --surface: #f7f8fb;
                --panel: #ffffff;
                --ink: #1d2733;
                --muted: #647084;
                --line: #dce2ea;
                --teal: #0f766e;
                --amber: #b45309;
                --rose: #be123c;
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

            h1, h2, h3 {
                letter-spacing: 0;
            }

            .app-header {
                border-bottom: 1px solid var(--line);
                padding-bottom: 1.15rem;
                margin-bottom: 1.25rem;
            }

            .app-subtitle {
                color: var(--muted);
                font-size: 1.05rem;
                margin-top: -0.25rem;
            }

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

            .status-label {
                font-weight: 700;
                margin-bottom: 0.15rem;
            }

            .status-copy {
                color: var(--muted);
                font-size: 0.9rem;
            }

            .service-row {
                align-items: center;
                border-top: 1px solid var(--line);
                display: flex;
                justify-content: space-between;
                gap: 1rem;
                padding: 0.65rem 0;
            }

            .service-row:first-of-type {
                border-top: 0;
            }

            .service-name {
                font-weight: 650;
            }

            .service-state {
                color: var(--amber);
                font-size: 0.86rem;
                white-space: nowrap;
            }

            div[data-testid="stMetricValue"] {
                font-size: 1.2rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        """
        <div class="app-header">
            <h1>Interruptible Study Assistant</h1>
            <div class="app-subtitle">A voice-first study companion for university students</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_voice_controls() -> None:
    with st.container(border=True):
        st.subheader("Voice Controls")
        st.caption("Phase 1 placeholder controls. No microphone stream is opened.")

        start_col, stop_col = st.columns(2)
        with start_col:
            st.button(
                "Start Listening",
                on_click=_set_voice_placeholder,
                args=("Listening", "UI placeholder active"),
                use_container_width=True,
            )

        with stop_col:
            st.button(
                "Stop Listening",
                on_click=_set_voice_placeholder,
                args=("Ready to listen", "Disconnected (placeholder)"),
                use_container_width=True,
            )

        st.metric("Microphone status", st.session_state.microphone_status)


def render_service_status() -> None:
    services = [
        ("Speech-to-Text", "Not connected"),
        ("LLM", "Not connected"),
        ("Rime TTS", "Not connected"),
        ("LiveKit", "Not connected"),
    ]

    with st.container(border=True):
        st.subheader("Future Services")
        st.caption("Configured later with API keys and backend integrations.")

        rows = "".join(
            f"""
            <div class="service-row">
                <span class="service-name">{name}</span>
                <span class="service-state">{state}</span>
            </div>
            """
            for name, state in services
        )
        st.markdown(rows, unsafe_allow_html=True)
