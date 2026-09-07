"""Conversation panel — displays the chat history.

Shows example messages only when the user hasn't started a real conversation.
Once there are real messages, only real messages are shown.
"""
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
]


def render_conversation_panel(messages: list[dict] | None = None) -> None:
    """Render the conversation history panel.

    Shows example messages when the conversation is empty,
    otherwise shows only real messages.
    """
    real_messages = messages or []
    show_messages = real_messages if real_messages else EXAMPLE_MESSAGES

    with st.container(border=True):
        st.subheader("Conversation", icon=":material/forum:")

        if not real_messages:
            st.caption("Example conversation — start a session and ask a question!")

        for msg in show_messages:
            avatar = (
                ":material/person:"
                if msg["role"] == "user"
                else ":material/smart_toy:"
            )
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(f"**{msg['speaker']}**")
                st.write(msg["text"])
