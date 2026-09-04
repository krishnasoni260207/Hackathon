from __future__ import annotations

import streamlit as st


EXAMPLE_MESSAGES = [
    {
        "speaker": "Student",
        "role": "user",
        "text": "Can you explain the difference between mitosis and meiosis?",
    },
    {
        "speaker": "AI Assistant",
        "role": "assistant",
        "text": (
            "Mitosis creates two identical body cells. Meiosis creates four genetically "
            "different sex cells, which helps explain variation in offspring."
        ),
    },
    {
        "speaker": "Student",
        "role": "user",
        "text": "Make that simpler, like I am reviewing before an exam.",
    },
    {
        "speaker": "AI Assistant",
        "role": "assistant",
        "text": (
            "Quick version: mitosis is for growth and repair. Meiosis is for reproduction."
        ),
    },
]


def render_conversation_panel() -> None:
    with st.container(border=True):
        st.subheader("Study Conversation")
        st.caption("Example messages only. No LLM is connected in Phase 1.")

        for message in EXAMPLE_MESSAGES:
            with st.chat_message(message["role"]):
                st.markdown(f"**{message['speaker']}**")
                st.write(message["text"])

        st.text_input(
            "Study question",
            placeholder="Conversation input will be connected in a later phase",
            disabled=True,
            label_visibility="collapsed",
        )
