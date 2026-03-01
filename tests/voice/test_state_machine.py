"""Tests for the assistant state machine."""

from max_ai.voice.state_machine import AssistantState, StateMachine


def test_initial_state_is_idle() -> None:
    """State machine starts in IDLE state."""
    sm = StateMachine()
    assert sm.state == AssistantState.IDLE


def test_transition_idle_to_listening() -> None:
    """IDLE → LISTENING transition works."""
    sm = StateMachine()
    sm.transition(AssistantState.LISTENING)
    assert sm.state == AssistantState.LISTENING


def test_transition_listening_to_processing() -> None:
    """LISTENING → PROCESSING transition works."""
    sm = StateMachine()
    sm.transition(AssistantState.LISTENING)
    sm.transition(AssistantState.PROCESSING)
    assert sm.state == AssistantState.PROCESSING


def test_transition_processing_to_speaking() -> None:
    """PROCESSING → SPEAKING transition works."""
    sm = StateMachine()
    sm.transition(AssistantState.PROCESSING)
    sm.transition(AssistantState.SPEAKING)
    assert sm.state == AssistantState.SPEAKING


def test_on_tts_complete_returns_to_idle_with_no_pending() -> None:
    """on_tts_complete transitions to IDLE when no pending state is set."""
    sm = StateMachine()
    sm.transition(AssistantState.SPEAKING)
    sm.on_tts_complete()
    assert sm.state == AssistantState.IDLE


def test_on_tts_complete_uses_pending_state() -> None:
    """on_tts_complete transitions to the pending state when set."""
    sm = StateMachine()
    sm.transition(AssistantState.SPEAKING)
    sm.set_post_speak_state(AssistantState.LISTENING)
    sm.on_tts_complete()
    assert sm.state == AssistantState.LISTENING


def test_on_tts_complete_clears_pending_state() -> None:
    """After on_tts_complete, the pending state is cleared."""
    sm = StateMachine()
    sm.set_post_speak_state(AssistantState.LISTENING)
    sm.on_tts_complete()
    # Calling again should now go to IDLE (pending cleared)
    sm.transition(AssistantState.SPEAKING)
    sm.on_tts_complete()
    assert sm.state == AssistantState.IDLE


def test_on_change_callback_fires_on_transition() -> None:
    """Registered on_change callbacks fire on every transition with correct old/new states."""
    sm = StateMachine()
    events: list[tuple[AssistantState, AssistantState]] = []
    sm.on_change(lambda old, new: events.append((old, new)))

    sm.transition(AssistantState.LISTENING)
    sm.transition(AssistantState.PROCESSING)

    assert events == [
        (AssistantState.IDLE, AssistantState.LISTENING),
        (AssistantState.LISTENING, AssistantState.PROCESSING),
    ]


def test_on_change_multiple_callbacks_all_fire() -> None:
    """Multiple on_change callbacks all fire on each transition."""
    sm = StateMachine()
    fired_a: list[AssistantState] = []
    fired_b: list[AssistantState] = []
    sm.on_change(lambda old, new: fired_a.append(new))
    sm.on_change(lambda old, new: fired_b.append(new))

    sm.transition(AssistantState.SPEAKING)

    assert fired_a == [AssistantState.SPEAKING]
    assert fired_b == [AssistantState.SPEAKING]


def test_on_tts_complete_fires_callback() -> None:
    """on_tts_complete fires registered callbacks with correct old/new states."""
    sm = StateMachine()
    events: list[tuple[AssistantState, AssistantState]] = []
    sm.on_change(lambda old, new: events.append((old, new)))

    sm.transition(AssistantState.SPEAKING)
    sm.on_tts_complete()

    assert (AssistantState.SPEAKING, AssistantState.IDLE) in events
