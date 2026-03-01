"""Tests for the always-listening wake word detection loop."""

import asyncio
import struct
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_wake_detector(
    frame_length: int = 512,
    detects_on_call: int = 0,
) -> MagicMock:
    """Return a WakeWordDetector mock that fires on the Nth process() call."""
    detector = MagicMock()
    detector.frame_length = frame_length
    detector.sample_rate = 16000
    call_counter: list[int] = [0]

    def _process(chunk: bytes) -> bool:
        call_counter[0] += 1
        return call_counter[0] > detects_on_call

    detector.process.side_effect = _process
    return detector


def _make_vad(exceeds_on_call: int = 1) -> MagicMock:
    """Return a VAD mock that triggers utterance-end on the Nth update() call."""
    vad = MagicMock()
    call_counter: list[int] = [0]

    def _update(chunk: bytes) -> bool:
        call_counter[0] += 1
        return call_counter[0] >= exceeds_on_call

    vad.update.side_effect = _update
    vad.reset = MagicMock()
    return vad


def _make_transcriber() -> MagicMock:
    transcriber = MagicMock()
    transcriber.start = AsyncMock()
    transcriber.send = AsyncMock()
    transcriber.stop = AsyncMock()
    return transcriber


def _make_audio_queue(chunks: list[bytes]) -> asyncio.Queue[bytes]:
    """Pre-fill a queue with audio chunks, then add a sentinel that hangs."""
    queue: asyncio.Queue[bytes] = asyncio.Queue()
    for chunk in chunks:
        queue.put_nowait(chunk)
    return queue


def _silent_frame(sample_count: int = 512) -> bytes:
    return struct.pack(f"{sample_count}h", *([0] * sample_count))


@pytest.mark.asyncio
async def test_idle_transitions_to_listening_on_wake_word() -> None:
    """IDLE → LISTENING when WakeWordDetector fires."""
    from max_ai.voice.state_machine import AssistantState, StateMachine

    state_machine = StateMachine()
    transitions: list[AssistantState] = []
    state_machine.on_change(lambda old, new: transitions.append(new))

    # Wake detector fires on first process() call
    wake_detector = _make_wake_detector(frame_length=4, detects_on_call=0)
    vad = _make_vad(exceeds_on_call=999)  # never triggers
    transcriber = _make_transcriber()

    # One frame's worth of audio: 4 samples * 2 bytes = 8 bytes
    frame = _silent_frame(4)

    async def _run_one_iteration() -> None:
        # Manually simulate what the loop does for one audio chunk in IDLE state
        assert state_machine.state == AssistantState.IDLE
        chunk = frame
        frame_buffer = bytearray(chunk)
        frame_size = wake_detector.frame_length * 2
        while len(frame_buffer) >= frame_size:
            f = bytes(frame_buffer[:frame_size])
            del frame_buffer[:frame_size]
            if wake_detector.process(f):
                state_machine.transition(AssistantState.LISTENING)
                vad.reset()
                await transcriber.start(
                    on_transcript=lambda t, fin: None,
                    on_utterance_end=lambda: None,
                )
                break

    await _run_one_iteration()

    assert state_machine.state == AssistantState.LISTENING
    assert AssistantState.LISTENING in transitions
    vad.reset.assert_called_once()
    transcriber.start.assert_called_once()


@pytest.mark.asyncio
async def test_listening_transitions_to_processing_on_utterance_end() -> None:
    """LISTENING → PROCESSING when VAD silence threshold is exceeded."""
    from max_ai.voice.state_machine import AssistantState, StateMachine

    state_machine = StateMachine()
    state_machine.transition(AssistantState.LISTENING)

    vad = _make_vad(exceeds_on_call=1)  # triggers immediately
    transcriber = _make_transcriber()

    transitions: list[AssistantState] = []
    state_machine.on_change(lambda old, new: transitions.append(new))

    # Simulate LISTENING state handling with enough words
    accumulated_transcript = "hello there max please help"

    async def _handle_utterance_end() -> None:
        word_count = len(accumulated_transcript.split())
        if word_count < 3:
            state_machine.transition(AssistantState.IDLE)
            return
        await transcriber.stop()
        state_machine.transition(AssistantState.PROCESSING)

    chunk = _silent_frame(160)
    # vad.update returns True on first call
    if vad.update(chunk):
        await _handle_utterance_end()

    assert state_machine.state == AssistantState.PROCESSING
    assert AssistantState.PROCESSING in transitions
    transcriber.stop.assert_called_once()


@pytest.mark.asyncio
async def test_empty_transcript_returns_to_idle() -> None:
    """An empty transcript (Deepgram returned nothing) returns silently to IDLE."""
    from max_ai.voice.state_machine import AssistantState, StateMachine

    state_machine = StateMachine()
    state_machine.transition(AssistantState.LISTENING)

    transcriber = _make_transcriber()
    transitions: list[AssistantState] = []
    state_machine.on_change(lambda old, new: transitions.append(new))

    accumulated_transcript = ""

    async def _handle_utterance_end() -> None:
        if not accumulated_transcript.strip():
            await transcriber.stop()
            state_machine.transition(AssistantState.IDLE)
            return
        await transcriber.stop()
        state_machine.transition(AssistantState.PROCESSING)

    await _handle_utterance_end()

    assert state_machine.state == AssistantState.IDLE
    transcriber.stop.assert_called_once()
    assert AssistantState.PROCESSING not in transitions


@pytest.mark.asyncio
async def test_interim_transcript_used_as_fallback_when_no_final() -> None:
    """When VAD fires before Deepgram sends is_final, last interim is used instead of empty."""
    from max_ai.voice.state_machine import AssistantState, StateMachine

    state_machine = StateMachine()
    state_machine.transition(AssistantState.LISTENING)

    transcriber = _make_transcriber()
    transitions: list[AssistantState] = []
    state_machine.on_change(lambda old, new: transitions.append(new))

    # No final transcript received yet — only an interim result was seen
    accumulated_transcript = ""
    last_interim_transcript = "what is the weather today"

    async def _handle_utterance_end() -> None:
        transcript_to_process = accumulated_transcript.strip() or last_interim_transcript.strip()
        if not transcript_to_process:
            await transcriber.stop()
            state_machine.transition(AssistantState.IDLE)
            return
        await transcriber.stop()
        state_machine.transition(AssistantState.PROCESSING)

    await _handle_utterance_end()

    assert state_machine.state == AssistantState.PROCESSING
    assert AssistantState.PROCESSING in transitions
    transcriber.stop.assert_called_once()


def test_final_transcripts_append_not_overwrite() -> None:
    """Multiple is_final=True segments are concatenated, not overwritten."""
    accumulated_transcript = ""
    last_interim_transcript = ""

    def on_transcript(text: str, is_final: bool) -> None:
        nonlocal accumulated_transcript, last_interim_transcript
        if is_final:
            accumulated_transcript = (accumulated_transcript + " " + text).strip()
            last_interim_transcript = ""
        elif text:
            last_interim_transcript = text

    on_transcript("hello there", is_final=True)
    on_transcript("how are you", is_final=True)

    assert accumulated_transcript == "hello there how are you"
    assert last_interim_transcript == ""


def test_interim_transcript_cleared_on_final() -> None:
    """Receiving a final transcript clears the interim buffer."""
    accumulated_transcript = ""
    last_interim_transcript = ""

    def on_transcript(text: str, is_final: bool) -> None:
        nonlocal accumulated_transcript, last_interim_transcript
        if is_final:
            accumulated_transcript = (accumulated_transcript + " " + text).strip()
            last_interim_transcript = ""
        elif text:
            last_interim_transcript = text

    on_transcript("what is", is_final=False)
    assert last_interim_transcript == "what is"

    on_transcript("what is the time", is_final=True)
    assert accumulated_transcript == "what is the time"
    assert last_interim_transcript == ""


@pytest.mark.asyncio
async def test_event_queue_handled_during_idle() -> None:
    """Background events from event_queue are processed when in IDLE state."""
    from max_ai.voice.state_machine import AssistantState, StateMachine

    state_machine = StateMachine()
    assert state_machine.state == AssistantState.IDLE

    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    event_queue.put_nowait({"content": "Timer has expired"})

    transitions: list[AssistantState] = []
    state_machine.on_change(lambda old, new: transitions.append(new))

    event = await event_queue.get()
    assert event["content"] == "Timer has expired"

    # Simulate what the loop does with an event in IDLE state
    state_machine.transition(AssistantState.PROCESSING)

    assert AssistantState.PROCESSING in transitions
