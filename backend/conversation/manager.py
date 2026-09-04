from __future__ import annotations

from backend.conversation.state import ConversationMessage, StudySessionState


class ConversationManager:
    """Small in-memory helper for placeholder conversation state."""

    def __init__(self, state: StudySessionState | None = None) -> None:
        self.state = state or StudySessionState()

    def add_student_message(self, text: str) -> ConversationMessage:
        return self.state.add_message("student", text)

    def add_assistant_message(self, text: str) -> ConversationMessage:
        return self.state.add_message("assistant", text)

    def clear(self) -> None:
        self.state.messages.clear()
