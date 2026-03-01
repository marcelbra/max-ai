"""Tests for the Orchestrator state machine.

All components are mocked.  The bus is driven directly so no real audio,
network, or TTS calls are made.
"""

from collections.abc import AsyncIterator
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import anthropic

from max_ai.agent.agent import Agent
from max_ai.tools.registry import ToolRegistry
from max_ai.voice.audio_capture import AudioCapture
from max_ai.voice.display import Display
from max_ai.voice.events import (
    AgentDone,
    AgentText,
    AssistantState,
    AudioFrame,
    EventBus,
    TaskResult,
    TimerFired,
    UtteranceEnd,
    WakeWordDetected,
)
from max_ai.voice.orchestrator import Orchestrator, OrchestratorConfig
from max_ai.voice.transcribe import StreamingTranscriber
from max_ai.voice.tts import TTSPlayer
from max_ai.voice.wakeword import KeyboardWakeWordDetector

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_display() -> Display:
    return cast(Display, MagicMock(spec=Display))


def _make_mock_audio_capture() -> AudioCapture:
    """AudioCapture whose running() context manager does nothing."""
    import contextlib

    capture = cast(AudioCapture, MagicMock(spec=AudioCapture))

    @contextlib.asynccontextmanager
    async def _running(bus: EventBus) -> AsyncIterator[None]:
        yield

    capture.running = _running  # type: ignore[method-assign]
    return capture


def _make_mock_transcriber() -> StreamingTranscriber:
    transcriber = cast(StreamingTranscriber, MagicMock(spec=StreamingTranscriber))
    transcriber.start = AsyncMock()  # type: ignore[method-assign]
    transcriber.send = AsyncMock()  # type: ignore[method-assign]
    transcriber.stop = AsyncMock()  # type: ignore[method-assign]
    return transcriber


def _make_mock_tts_player() -> TTSPlayer:
    player = cast(TTSPlayer, MagicMock(spec=TTSPlayer))
    player.speak = AsyncMock()  # type: ignore[method-assign]
    return player


def _make_mock_keyboard_detector() -> KeyboardWakeWordDetector:
    detector = cast(KeyboardWakeWordDetector, MagicMock(spec=KeyboardWakeWordDetector))
    detector.run = AsyncMock()  # type: ignore[method-assign]
    return detector


def _make_agent_with_responses(*responses: list[AgentText | AgentDone]) -> Agent:
    """Return an Agent whose run() yields the given event sequences on successive calls."""
    client = cast(anthropic.AsyncAnthropic, MagicMock(spec=anthropic.AsyncAnthropic))
    agent = Agent(client, ToolRegistry(), "system")
    call_count = 0

    async def _fake_run(message: str) -> AsyncIterator[AgentText | AgentDone]:
        nonlocal call_count
        event_list = responses[min(call_count, len(responses) - 1)]
        call_count += 1
        for event in event_list:
            yield event

    agent.run = _fake_run  # type: ignore[assignment]
    return agent


def _make_orchestrator(
    agent: Agent | None = None,
    transcriber: StreamingTranscriber | None = None,
    tts_player: TTSPlayer | None = None,
    display: Display | None = None,
    config: OrchestratorConfig | None = None,
) -> Orchestrator:
    return Orchestrator(
        audio_capture=_make_mock_audio_capture(),
        wake_word_detector=_make_mock_keyboard_detector(),
        transcriber=transcriber or _make_mock_transcriber(),
        agent=agent or _make_agent_with_responses([AgentDone(next_state=None)]),
        tts_player=tts_player or _make_mock_tts_player(),
        display=display or _make_mock_display(),
        config=config or OrchestratorConfig(min_words=1),
    )


# ---------------------------------------------------------------------------
# IDLE state tests
# ---------------------------------------------------------------------------


async def test_idle_wake_word_transitions_to_listening() -> None:
    """WakeWordDetected in IDLE → LISTENING, transcriber.start() called."""
    transcriber = _make_mock_transcriber()
    orchestrator = _make_orchestrator(transcriber=transcriber)

    await orchestrator._dispatch(WakeWordDetected())

    assert orchestrator._state == AssistantState.LISTENING
    cast(AsyncMock, transcriber.start).assert_awaited_once()


async def test_idle_audio_frame_ignored_without_wake_word_detector() -> None:
    """AudioFrame in IDLE does not cause a state change (keyboard detector, no Porcupine)."""
    orchestrator = _make_orchestrator()
    await orchestrator._dispatch(AudioFrame(data=b"\x00" * 1024))
    assert orchestrator._state == AssistantState.IDLE


# ---------------------------------------------------------------------------
# LISTENING state tests
# ---------------------------------------------------------------------------


async def test_listening_audio_frame_forwarded_to_transcriber() -> None:
    """AudioFrame in LISTENING → transcriber.send() called."""
    transcriber = _make_mock_transcriber()
    orchestrator = _make_orchestrator(transcriber=transcriber)
    orchestrator._state = AssistantState.LISTENING

    await orchestrator._dispatch(AudioFrame(data=b"\x01\x02"))

    cast(AsyncMock, transcriber.send).assert_awaited_once_with(b"\x01\x02")


async def test_listening_utterance_end_too_short_returns_to_idle() -> None:
    """UtteranceEnd with fewer than min_words → back to IDLE."""
    transcriber = _make_mock_transcriber()
    orchestrator = _make_orchestrator(
        transcriber=transcriber, config=OrchestratorConfig(min_words=3)
    )
    orchestrator._state = AssistantState.LISTENING

    await orchestrator._dispatch(UtteranceEnd(transcript="hi"))

    assert orchestrator._state == AssistantState.IDLE
    cast(AsyncMock, transcriber.stop).assert_awaited_once()


async def test_listening_utterance_end_enough_words_transitions_to_processing() -> None:
    """UtteranceEnd with enough words → PROCESSING, agent task spawned."""
    transcriber = _make_mock_transcriber()
    agent = _make_agent_with_responses([AgentText(text="response"), AgentDone(next_state=None)])
    orchestrator = _make_orchestrator(
        transcriber=transcriber,
        agent=agent,
        config=OrchestratorConfig(min_words=2),
    )
    orchestrator._state = AssistantState.LISTENING

    await orchestrator._dispatch(UtteranceEnd(transcript="hello world"))

    assert orchestrator._state == AssistantState.PROCESSING
    cast(AsyncMock, transcriber.stop).assert_awaited_once()


# ---------------------------------------------------------------------------
# PROCESSING state tests
# ---------------------------------------------------------------------------


async def test_processing_agent_text_accumulates_in_buffer() -> None:
    """AgentText in PROCESSING → text accumulated in buffer, display called."""
    display = _make_mock_display()
    orchestrator = _make_orchestrator(display=display)
    orchestrator._state = AssistantState.PROCESSING

    await orchestrator._dispatch(AgentText(text="Hello "))
    await orchestrator._dispatch(AgentText(text="World"))

    assert orchestrator._response_buffer == ["Hello ", "World"]
    assert cast(MagicMock, display).on_agent_text.call_count == 2


async def test_processing_agent_done_with_text_transitions_to_speaking() -> None:
    """AgentDone in PROCESSING with buffered text → SPEAKING."""
    tts_player = _make_mock_tts_player()
    orchestrator = _make_orchestrator(tts_player=tts_player)
    orchestrator._state = AssistantState.PROCESSING
    orchestrator._response_buffer = ["Hello World"]

    await orchestrator._dispatch(AgentDone(next_state=None))

    assert orchestrator._state == AssistantState.SPEAKING


async def test_processing_agent_done_without_text_returns_to_idle() -> None:
    """AgentDone in PROCESSING with empty buffer → IDLE."""
    orchestrator = _make_orchestrator()
    orchestrator._state = AssistantState.PROCESSING
    orchestrator._response_buffer = []

    await orchestrator._dispatch(AgentDone(next_state=None))

    assert orchestrator._state == AssistantState.IDLE


# ---------------------------------------------------------------------------
# SPEAKING state tests
# ---------------------------------------------------------------------------


async def test_speaking_utterance_end_is_queued() -> None:
    """UtteranceEnd during SPEAKING is queued for replay after IDLE."""
    orchestrator = _make_orchestrator()
    orchestrator._state = AssistantState.SPEAKING

    await orchestrator._dispatch(UtteranceEnd(transcript="hello world"))

    assert len(orchestrator._queued_events) == 1
    assert isinstance(orchestrator._queued_events[0], UtteranceEnd)


# ---------------------------------------------------------------------------
# Timer / TaskResult injection tests
# ---------------------------------------------------------------------------


async def test_timer_fired_in_idle_transitions_to_processing() -> None:
    """TimerFired in IDLE → PROCESSING, agent task spawned."""
    orchestrator = _make_orchestrator()
    assert orchestrator._state == AssistantState.IDLE

    await orchestrator._dispatch(TimerFired(message="alarm ring"))

    assert orchestrator._state == AssistantState.PROCESSING  # type: ignore[comparison-overlap]


async def test_task_result_in_idle_transitions_to_processing() -> None:
    """TaskResult in IDLE → PROCESSING."""
    orchestrator = _make_orchestrator()
    assert orchestrator._state == AssistantState.IDLE

    await orchestrator._dispatch(TaskResult(task_id="t1", result="done"))

    assert orchestrator._state == AssistantState.PROCESSING  # type: ignore[comparison-overlap]


async def test_timer_fired_during_processing_is_queued() -> None:
    """TimerFired during PROCESSING is queued."""
    orchestrator = _make_orchestrator()
    orchestrator._state = AssistantState.PROCESSING

    await orchestrator._dispatch(TimerFired(message="ping"))

    assert len(orchestrator._queued_events) == 1
    assert isinstance(orchestrator._queued_events[0], TimerFired)


# ---------------------------------------------------------------------------
# StateChanged propagation
# ---------------------------------------------------------------------------


async def test_state_changed_calls_display_on_state_change() -> None:
    """_transition() calls display.on_state_change with correct states."""
    display = _make_mock_display()
    orchestrator = _make_orchestrator(display=display)

    orchestrator._transition(AssistantState.LISTENING)

    cast(MagicMock, display).on_state_change.assert_called_once_with(
        AssistantState.IDLE, AssistantState.LISTENING
    )


async def test_transition_noop_when_same_state() -> None:
    """_transition() does nothing when the state doesn't change."""
    display = _make_mock_display()
    orchestrator = _make_orchestrator(display=display)

    orchestrator._transition(AssistantState.IDLE)

    cast(MagicMock, display).on_state_change.assert_not_called()
