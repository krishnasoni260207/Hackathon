from __future__ import annotations

import streamlit as st


STAGES = [
    "Input captured",
    "Transcribing speech",
    "Generating answer",
    "Synthesizing speech",
    "Output ready",
]


def render_status_panel(current_status: str) -> None:
    completed_steps = st.session_state.get("last_pipeline_steps", [])
    current_stage = st.session_state.get("current_stage", "Idle")
    progress = _progress_value(completed_steps, current_status)

    with st.container(border=True):
        st.subheader("Live state", icon=":material/query_stats:")
        st.badge(current_status, icon=_status_icon(current_status), color=_status_color(current_status))
        st.metric("Current stage", current_stage)
        st.progress(progress)

        for stage in STAGES:
            status_class = " status-card-complete" if stage in completed_steps else ""
            if stage == current_stage:
                status_class += " status-card-active"
            st.html(
                f"""
                <div class="status-card{status_class}">
                    <div class="status-label">{stage}</div>
                    <div class="status-copy">{_stage_copy(stage)}</div>
                </div>
                """
            )


def _progress_value(completed_steps: list[str], current_status: str) -> float:
    if current_status == "Listening":
        return 0.2
    if not completed_steps:
        return 0.0
    return min(len(completed_steps) / len(STAGES), 1.0)


def _status_icon(status: str) -> str:
    return {
        "Ready to listen": ":material/check_circle:",
        "Session started": ":material/play_circle:",
        "Recording": ":material/mic:",
        "Listening": ":material/mic:",
        "Thinking": ":material/autorenew:",
        "Speaking": ":material/volume_up:",
        "Interrupted": ":material/pause_circle:",
        "Recovering": ":material/history:",
        "Ready for next question": ":material/check_circle:",
    }.get(status, ":material/info:")


def _status_color(status: str) -> str:
    return {
        "Ready to listen": "green",
        "Session started": "green",
        "Recording": "red",
        "Listening": "blue",
        "Thinking": "orange",
        "Speaking": "violet",
        "Interrupted": "red",
        "Recovering": "orange",
        "Ready for next question": "green",
    }.get(status, "gray")


def _stage_copy(stage: str) -> str:
    return {
        "Input captured": "Voice or text entered the pipeline.",
        "Transcribing speech": "Recorded audio is converted to text.",
        "Generating answer": "The LLM prepares the study response.",
        "Synthesizing speech": "Rime TTS prepares assistant audio.",
        "Output ready": "Transcript, text, and audio output are available.",
    }[stage]
