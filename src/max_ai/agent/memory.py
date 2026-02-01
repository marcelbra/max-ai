"""Session-based conversation memory for the agent."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Message:
    """A single message in the conversation."""

    role: Literal["user", "assistant"]
    content: str


@dataclass
class ConversationMemory:
    """In-memory conversation history for a session."""

    messages: list[Message] = field(default_factory=list)
    max_messages: int = 100

    def add_user_message(self, content: str) -> None:
        """Add a user message to the history."""
        self._add_message(Message(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the history."""
        self._add_message(Message(role="assistant", content=content))

    def _add_message(self, message: Message) -> None:
        """Add a message, trimming if over max."""
        self.messages.append(message)
        if len(self.messages) > self.max_messages:
            # Keep the most recent messages
            self.messages = self.messages[-self.max_messages :]

    def get_messages(self) -> list[dict[str, str]]:
        """Get messages in a format suitable for LLM APIs."""
        return [{"role": msg.role, "content": msg.content} for msg in self.messages]

    def clear(self) -> None:
        """Clear all messages."""
        self.messages = []

    def __len__(self) -> int:
        """Return the number of messages."""
        return len(self.messages)
