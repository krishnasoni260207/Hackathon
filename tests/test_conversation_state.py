from backend.conversation.manager import ConversationManager
from backend.conversation.state import StudySessionState


def test_new_study_session_starts_ready() -> None:
    state = StudySessionState()

    assert state.status == "ready"
    assert state.messages == []


def test_conversation_manager_adds_messages_in_order() -> None:
    manager = ConversationManager()

    student_message = manager.add_student_message("What is photosynthesis?")
    assistant_message = manager.add_assistant_message("It is how plants make food.")

    assert manager.state.messages == [student_message, assistant_message]
    assert student_message.speaker == "student"
    assert assistant_message.speaker == "assistant"
