"""Assistant state machine for wake word detection mode."""

from collections.abc import Callable
from enum import Enum


class AssistantState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


class StateMachine:
    """Tracks assistant state and fires callbacks on transitions."""

    def __init__(self) -> None:
        self._state: AssistantState = AssistantState.IDLE
        self._pending_next_state: AssistantState | None = None
        self._listeners: list[Callable[[AssistantState, AssistantState], None]] = []

    @property
    def state(self) -> AssistantState:
        return self._state

    def transition(self, new_state: AssistantState) -> None:
        """Transition to a new state, firing all registered callbacks."""
        old_state = self._state
        self._state = new_state
        for listener in self._listeners:
            listener(old_state, new_state)

    def set_post_speak_state(self, state: AssistantState) -> None:
        """Store the state to transition to after TTS completes."""
        self._pending_next_state = state

    def on_tts_complete(self) -> None:
        """Transition to pending state (or IDLE) after TTS finishes."""
        next_state = (
            self._pending_next_state
            if self._pending_next_state is not None
            else AssistantState.IDLE
        )
        self._pending_next_state = None
        self.transition(next_state)

    def on_change(self, callback: Callable[[AssistantState, AssistantState], None]) -> None:
        """Register a listener that is called on every state transition."""
        self._listeners.append(callback)
