"""Voice assistant orchestrator — state machine + event routing.

One event bus.  One orchestrator that transitions state.  Everything else
is a component.

The main loop never awaits long operations.  Anything that takes time
(agent turn, TTS playback) is fired as a background task that puts a result
event onto the bus when done.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from max_ai.voice.events import (
    AgentDone,
    AgentText,
    AssistantState,
    AudioFrame,
    EventBus,
    StateChanged,
    TaskResult,
    TimerFired,
    TTSDone,
    UtteranceEnd,
    WakeWordDetected,
)

if TYPE_CHECKING:
    from max_ai.agent.agent import Agent
    from max_ai.voice.audio_capture import AudioCapture
    from max_ai.voice.display import Display
    from max_ai.voice.transcribe import StreamingTranscriber
    from max_ai.voice.tts import TTSPlayer
    from max_ai.voice.wakeword import WakeWordDetector

_logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    min_words: int = 3


class Orchestrator:
    """Routes events through the assistant state machine."""

    def __init__(
        self,
        audio_capture: AudioCapture,
        wake_word_detector: WakeWordDetector,
        transcriber: StreamingTranscriber,
        agent: Agent,
        tts_player: TTSPlayer,
        display: Display,
        config: OrchestratorConfig | None = None,
    ) -> None:
        self._audio_capture = audio_capture
        self._wake_word_detector = wake_word_detector
        self._transcriber = transcriber
        self._agent = agent
        self._tts_player = tts_player
        self._display = display
        self._config = config or OrchestratorConfig()

        self._bus: EventBus = asyncio.Queue()
        self._state: AssistantState = AssistantState.IDLE
        self._response_buffer: list[str] = []
        self._tts_stop_event = asyncio.Event()
        self._queued_events: list[UtteranceEnd | TimerFired | TaskResult] = []

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Start the orchestrator loop."""
        self._display.on_state_change(self._state, self._state)

        async with self._audio_capture.running(self._bus):
            while True:
                event = await self._bus.get()
                should_stop = await self._dispatch(event)
                if should_stop:
                    break

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _transition(self, new_state: AssistantState) -> None:
        if new_state == self._state:
            return
        previous = self._state
        self._state = new_state
        _logger.debug("state %s → %s", previous.name, new_state.name)
        changed = StateChanged(previous=previous, current=new_state)
        self._display.on_state_change(previous, new_state)
        self._bus.put_nowait(changed)

    # ------------------------------------------------------------------
    # Event dispatch (never awaits agent or TTS directly)
    # ------------------------------------------------------------------

    async def _dispatch(self, event: object) -> bool:
        """Route one event.  Returns True if the loop should stop."""
        _logger.debug("event %r in state %s", event, self._state.name)
        match event:
            case AudioFrame(data=data):
                await self._handle_audio_frame(data)

            case WakeWordDetected():
                if self._state == AssistantState.IDLE:
                    self._response_buffer.clear()
                    await self._transcriber.start(self._bus)
                    self._transition(AssistantState.LISTENING)

            case UtteranceEnd(transcript=transcript):
                await self._handle_utterance_end(transcript)

            case AgentText(text=text):
                if self._state == AssistantState.PROCESSING:
                    self._response_buffer.append(text)
                    self._display.on_agent_text(text)

            case AgentDone(next_state=next_state_value):
                if self._state == AssistantState.PROCESSING:
                    full_text = "".join(self._response_buffer)
                    self._response_buffer.clear()
                    if full_text:
                        self._tts_stop_event.clear()
                        self._transition(AssistantState.SPEAKING)
                        asyncio.create_task(self._tts_task(full_text, next_state_value))
                    else:
                        self._transition(AssistantState.IDLE)
                        await self._replay_queued_events()

            case TTSDone():
                if self._state == AssistantState.SPEAKING:
                    # _tts_task carries the next_state; it is stored on event
                    pass  # handled inside _tts_task via the queued sentinel below

            case TimerFired(message=message):
                await self._handle_injectable(TimerFired(message=message))

            case TaskResult() as task_result:
                await self._handle_injectable(task_result)

            case StateChanged():
                pass  # display already notified in _transition

        return False

    # ------------------------------------------------------------------
    # Background tasks
    # ------------------------------------------------------------------

    async def _agent_task(self, transcript: str) -> None:
        _logger.debug("agent_task start: %r", transcript)
        try:
            async for agent_event in self._agent.run(transcript):
                await self._bus.put(agent_event)
        except Exception:
            _logger.exception("Agent task failed")
            self._transition(AssistantState.IDLE)
            await self._replay_queued_events()
            return
        _logger.debug("agent_task end")

    async def _tts_task(self, text: str, next_state_after_speaking: str | None) -> None:
        _logger.debug("tts_task start: %d chars", len(text))
        try:
            await self._tts_player.speak(text, self._tts_stop_event)
        except Exception:
            _logger.exception("TTS task failed")
            self._transition(AssistantState.IDLE)
            await self._replay_queued_events()
            return
        _logger.debug("tts_task end")
        # Transition based on the next_state set by the agent (or default to IDLE).
        if next_state_after_speaking == "listening":
            await self._transcriber.start(self._bus)
            self._transition(AssistantState.LISTENING)
        else:
            self._transition(AssistantState.IDLE)
            await self._replay_queued_events()
        await self._bus.put(TTSDone())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _handle_audio_frame(self, data: bytes) -> None:
        if self._state == AssistantState.IDLE:
            if self._wake_word_detector.process(data):
                await self._bus.put(WakeWordDetected())
        elif self._state == AssistantState.LISTENING:
            await self._transcriber.send(data)

    async def _handle_utterance_end(self, transcript: str) -> None:
        if self._state == AssistantState.LISTENING:
            word_count = len(transcript.split())
            if word_count < self._config.min_words:
                await self._transcriber.stop()
                self._transition(AssistantState.IDLE)
                return
            await self._transcriber.stop()
            self._display.on_user_input(transcript)
            self._transition(AssistantState.PROCESSING)
            asyncio.create_task(self._agent_task(transcript))
        elif self._state in (AssistantState.PROCESSING, AssistantState.SPEAKING):
            self._queued_events.append(UtteranceEnd(transcript=transcript))

    async def _handle_injectable(self, event: TimerFired | TaskResult) -> None:
        """Inject a background event as an agent turn, or queue it."""
        if self._state == AssistantState.IDLE:
            message = event.message if isinstance(event, TimerFired) else event.result
            self._transition(AssistantState.PROCESSING)
            asyncio.create_task(self._agent_task(message))
        else:
            self._queued_events.append(event)

    async def _replay_queued_events(self) -> None:
        """Replay queued events in order now that we are back in IDLE."""
        queued = list(self._queued_events)
        self._queued_events.clear()
        _logger.debug("replaying %d queued events", len(queued))
        for event in queued:
            await self._dispatch(event)
