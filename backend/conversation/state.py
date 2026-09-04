from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


Speaker = Literal["student", "assistant"]
VoiceStatus = Literal["ready", "listening", "thinking", "speaking"]


@dataclass(frozen=True)
class ConversationMessage:
    speaker: Speaker
    text: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class StudySessionState:
    status: VoiceStatus = "ready"
    messages: list[ConversationMessage] = field(default_factory=list)

    def add_message(self, speaker: Speaker, text: str) -> ConversationMessage:
        message = ConversationMessage(speaker=speaker, text=text)
        self.messages.append(message)
        return message
