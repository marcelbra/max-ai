"""Tests for StreamingTranscriber — events on the bus, connection lifecycle, error handling."""

import asyncio
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from max_ai.voice.events import EventBus, TranscriptPartial, UtteranceEnd

# ---------------------------------------------------------------------------
# Fake Deepgram SDK (v6 API)
# ---------------------------------------------------------------------------

# EventType.MESSAGE is the string "message" in the real SDK.
_EVENT_MESSAGE = "message"


class _FakeEventType:
    MESSAGE = _EVENT_MESSAGE


class _FakeConnection:
    """Fake AsyncV1SocketClient that records event handlers and exposes async mocks."""

    def __init__(self) -> None:
        self.handlers: dict[str, Any] = {}
        self.send_media: AsyncMock = AsyncMock()
        self.send_close_stream: AsyncMock = AsyncMock()

    def on(self, event: Any, handler: Any) -> None:
        self.handlers[str(event)] = handler

    async def start_listening(self) -> None:
        pass


class _FakeContextManager:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> _FakeConnection:
        return self._connection

    async def __aexit__(self, *args: object) -> None:
        pass


def _sys_modules_patch(fake_deepgram: MagicMock, fake_events: MagicMock) -> dict[str, Any]:
    return {
        "deepgram": fake_deepgram,
        "deepgram.core": MagicMock(),
        "deepgram.core.events": fake_events,
    }


def _make_fake_deepgram_module(connection: _FakeConnection) -> tuple[MagicMock, MagicMock]:
    fake_events = MagicMock()
    fake_events.EventType = _FakeEventType

    fake_listen_v1 = MagicMock()
    fake_listen_v1.connect.return_value = _FakeContextManager(connection)

    fake_listen = MagicMock()
    fake_listen.v1 = fake_listen_v1

    fake_client_instance = MagicMock()
    fake_client_instance.listen = fake_listen

    fake_deepgram = MagicMock()
    fake_deepgram.AsyncDeepgramClient.return_value = fake_client_instance

    return fake_deepgram, fake_events


def _make_results_message(text: str, is_final: bool) -> MagicMock:
    message = MagicMock()
    message.type = "Results"
    message.channel.alternatives[0].transcript = text
    message.is_final = is_final
    return message


def _make_utterance_end_message() -> MagicMock:
    message = MagicMock()
    message.type = "UtteranceEnd"
    return message


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_transcript_partial_event_put_on_bus_for_interim() -> None:
    """TranscriptPartial must be put on the bus for interim transcripts."""
    connection = _FakeConnection()
    fake_deepgram, fake_events = _make_fake_deepgram_module(connection)
    bus: EventBus = asyncio.Queue()

    with patch.dict(sys.modules, _sys_modules_patch(fake_deepgram, fake_events)):
        from max_ai.voice.transcribe import StreamingTranscriber

        transcriber = StreamingTranscriber(api_key="test-key")
        await transcriber.start(bus)

    handler = connection.handlers[_EVENT_MESSAGE]
    handler(_make_results_message("hello", False))

    assert not bus.empty()
    event = bus.get_nowait()
    assert isinstance(event, TranscriptPartial)
    assert event.text == "hello"


async def test_transcript_partial_event_put_on_bus_for_final() -> None:
    """TranscriptPartial must also be put on the bus for final transcripts (text preview)."""
    connection = _FakeConnection()
    fake_deepgram, fake_events = _make_fake_deepgram_module(connection)
    bus: EventBus = asyncio.Queue()

    with patch.dict(sys.modules, _sys_modules_patch(fake_deepgram, fake_events)):
        from max_ai.voice.transcribe import StreamingTranscriber

        transcriber = StreamingTranscriber(api_key="test-key")
        await transcriber.start(bus)

    handler = connection.handlers[_EVENT_MESSAGE]
    handler(_make_results_message("world", True))

    event = bus.get_nowait()
    assert isinstance(event, TranscriptPartial)
    assert event.text == "world"


async def test_utterance_end_event_put_on_bus() -> None:
    """UtteranceEnd must be put on the bus when Deepgram fires the UtteranceEnd event."""
    connection = _FakeConnection()
    fake_deepgram, fake_events = _make_fake_deepgram_module(connection)
    bus: EventBus = asyncio.Queue()

    with patch.dict(sys.modules, _sys_modules_patch(fake_deepgram, fake_events)):
        from max_ai.voice.transcribe import StreamingTranscriber

        transcriber = StreamingTranscriber(api_key="test-key")
        await transcriber.start(bus)

    handler = connection.handlers[_EVENT_MESSAGE]
    # Accumulate a final transcript segment first
    handler(_make_results_message("hello world", True))
    # Drain the TranscriptPartial
    _ = bus.get_nowait()
    # Now fire UtteranceEnd
    handler(_make_utterance_end_message())

    event = bus.get_nowait()
    assert isinstance(event, UtteranceEnd)
    assert event.transcript == "hello world"


async def test_utterance_end_transcript_accumulates_final_segments() -> None:
    """UtteranceEnd.transcript must join all final segments received since the last reset."""
    connection = _FakeConnection()
    fake_deepgram, fake_events = _make_fake_deepgram_module(connection)
    bus: EventBus = asyncio.Queue()

    with patch.dict(sys.modules, _sys_modules_patch(fake_deepgram, fake_events)):
        from max_ai.voice.transcribe import StreamingTranscriber

        transcriber = StreamingTranscriber(api_key="test-key")
        await transcriber.start(bus)

    handler = connection.handlers[_EVENT_MESSAGE]
    handler(_make_results_message("hello", True))
    handler(_make_results_message("world", True))
    handler(_make_utterance_end_message())

    # Drain TranscriptPartial events
    events = []
    while not bus.empty():
        events.append(bus.get_nowait())

    utterance_events = [e for e in events if isinstance(e, UtteranceEnd)]
    assert len(utterance_events) == 1
    assert utterance_events[0].transcript == "hello world"


async def test_stop_closes_connection() -> None:
    """stop() must call send_close_stream() on the underlying Deepgram connection."""
    connection = _FakeConnection()
    fake_deepgram, fake_events = _make_fake_deepgram_module(connection)
    bus: EventBus = asyncio.Queue()

    with patch.dict(sys.modules, _sys_modules_patch(fake_deepgram, fake_events)):
        from max_ai.voice.transcribe import StreamingTranscriber

        transcriber = StreamingTranscriber(api_key="test-key")
        await transcriber.start(bus)
        await transcriber.stop()

    connection.send_close_stream.assert_awaited_once()


async def test_stop_is_idempotent() -> None:
    """stop() must not raise when called a second time."""
    connection = _FakeConnection()
    fake_deepgram, fake_events = _make_fake_deepgram_module(connection)
    bus: EventBus = asyncio.Queue()

    with patch.dict(sys.modules, _sys_modules_patch(fake_deepgram, fake_events)):
        from max_ai.voice.transcribe import StreamingTranscriber

        transcriber = StreamingTranscriber(api_key="test-key")
        await transcriber.start(bus)
        await transcriber.stop()
        await transcriber.stop()

    assert connection.send_close_stream.await_count == 1


async def test_send_before_start_raises() -> None:
    """send() must raise RuntimeError if called before start()."""
    from max_ai.voice.transcribe import StreamingTranscriber

    transcriber = StreamingTranscriber(api_key="test-key")

    with pytest.raises(RuntimeError, match="start()"):
        await transcriber.send(b"\x00\x01")
