"""Tests for the voice event catalog and AssistantState enum."""

from max_ai.voice.events import (
    AgentDone,
    AgentText,
    AssistantState,
    AudioFrame,
    EventBus,
    StateChanged,
    TaskResult,
    TimerFired,
    TranscriptFinal,
    TranscriptPartial,
    TTSDone,
    UtteranceEnd,
    WakeWordDetected,
)


def test_assistant_state_values() -> None:
    """AssistantState has the four expected string values."""
    assert AssistantState.IDLE.value == "idle"
    assert AssistantState.LISTENING.value == "listening"
    assert AssistantState.PROCESSING.value == "processing"
    assert AssistantState.SPEAKING.value == "speaking"


def test_assistant_state_enum_members() -> None:
    members = {s.value for s in AssistantState}
    assert members == {"idle", "listening", "processing", "speaking"}


def test_audio_frame_is_frozen() -> None:
    frame = AudioFrame(data=b"\x00\x01")
    import pytest

    with pytest.raises((AttributeError, TypeError)):
        frame.data = b"\x02"  # type: ignore[misc]


def test_agent_done_next_state_none() -> None:
    event = AgentDone(next_state=None)
    assert event.next_state is None


def test_agent_done_next_state_listening() -> None:
    event = AgentDone(next_state="listening")
    assert event.next_state == "listening"


def test_state_changed_holds_both_states() -> None:
    event = StateChanged(previous=AssistantState.IDLE, current=AssistantState.LISTENING)
    assert event.previous == AssistantState.IDLE
    assert event.current == AssistantState.LISTENING


def test_utterance_end_carries_transcript() -> None:
    event = UtteranceEnd(transcript="hello world")
    assert event.transcript == "hello world"


def test_timer_fired_carries_message() -> None:
    event = TimerFired(message="timer done")
    assert event.message == "timer done"


def test_task_result_fields() -> None:
    event = TaskResult(task_id="t1", result="done")
    assert event.task_id == "t1"
    assert event.result == "done"


def test_event_bus_is_asyncio_queue() -> None:
    import asyncio

    bus: EventBus = asyncio.Queue()
    assert isinstance(bus, asyncio.Queue)


def test_all_event_types_are_importable() -> None:
    """Smoke test: all event types can be instantiated without error."""
    AudioFrame(data=b"")
    WakeWordDetected()
    TranscriptPartial(text="hi")
    TranscriptFinal(text="hi")
    UtteranceEnd(transcript="hi")
    AgentText(text="hi")
    AgentDone(next_state=None)
    TTSDone()
    TimerFired(message="ping")
    TaskResult(task_id="x", result="y")
    StateChanged(previous=AssistantState.IDLE, current=AssistantState.LISTENING)
