"""Tests for DeepgramTranscriber — callbacks, connection lifecycle, and error handling."""

import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
        # Store by the string value so tests can look up by plain string.
        self.handlers[str(event)] = handler

    async def start_listening(self) -> None:
        # Returns immediately — simulates the connection being closed right away.
        pass


class _FakeContextManager:
    """Async context manager that yields the provided fake connection."""

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
    """Return ``(fake_deepgram, fake_events)`` wired to the given fake connection."""
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
    """Build a fake ListenV1Results-style message."""
    message = MagicMock()
    message.type = "Results"
    message.channel.alternatives[0].transcript = text
    message.is_final = is_final
    return message


def _make_utterance_end_message() -> MagicMock:
    """Build a fake ListenV1UtteranceEnd-style message."""
    message = MagicMock()
    message.type = "UtteranceEnd"
    return message


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_on_transcript_fires_for_interim_result() -> None:
    """on_transcript must be called with (text, False) for interim transcripts."""
    connection = _FakeConnection()
    fake_deepgram, fake_events = _make_fake_deepgram_module(connection)

    received: list[tuple[str, bool]] = []

    with patch.dict(sys.modules, _sys_modules_patch(fake_deepgram, fake_events)):
        from max_ai.voice.transcribe import DeepgramTranscriber

        transcriber = DeepgramTranscriber(api_key="test-key")
        await transcriber.start(
            on_transcript=lambda text, is_final: received.append((text, is_final)),
            on_utterance_end=lambda: None,
        )

    handler = connection.handlers[_EVENT_MESSAGE]
    handler(_make_results_message("hello", False))

    assert received == [("hello", False)]


async def test_on_transcript_fires_for_final_result() -> None:
    """on_transcript must be called with (text, True) for final transcripts."""
    connection = _FakeConnection()
    fake_deepgram, fake_events = _make_fake_deepgram_module(connection)

    received: list[tuple[str, bool]] = []

    with patch.dict(sys.modules, _sys_modules_patch(fake_deepgram, fake_events)):
        from max_ai.voice.transcribe import DeepgramTranscriber

        transcriber = DeepgramTranscriber(api_key="test-key")
        await transcriber.start(
            on_transcript=lambda text, is_final: received.append((text, is_final)),
            on_utterance_end=lambda: None,
        )

    handler = connection.handlers[_EVENT_MESSAGE]
    handler(_make_results_message("world", True))

    assert received == [("world", True)]


async def test_on_utterance_end_fires() -> None:
    """on_utterance_end must be called when Deepgram fires the UtteranceEnd event."""
    connection = _FakeConnection()
    fake_deepgram, fake_events = _make_fake_deepgram_module(connection)

    calls: list[bool] = []

    with patch.dict(sys.modules, _sys_modules_patch(fake_deepgram, fake_events)):
        from max_ai.voice.transcribe import DeepgramTranscriber

        transcriber = DeepgramTranscriber(api_key="test-key")
        await transcriber.start(
            on_transcript=lambda text, is_final: None,
            on_utterance_end=lambda: calls.append(True),
        )

    handler = connection.handlers[_EVENT_MESSAGE]
    handler(_make_utterance_end_message())

    assert calls == [True]


async def test_stop_closes_connection() -> None:
    """stop() must call send_close_stream() on the underlying Deepgram connection."""
    connection = _FakeConnection()
    fake_deepgram, fake_events = _make_fake_deepgram_module(connection)

    with patch.dict(sys.modules, _sys_modules_patch(fake_deepgram, fake_events)):
        from max_ai.voice.transcribe import DeepgramTranscriber

        transcriber = DeepgramTranscriber(api_key="test-key")
        await transcriber.start(on_transcript=lambda t, f: None, on_utterance_end=lambda: None)
        await transcriber.stop()

    connection.send_close_stream.assert_awaited_once()


async def test_stop_is_idempotent() -> None:
    """stop() must not raise when called a second time after the connection is already closed."""
    connection = _FakeConnection()
    fake_deepgram, fake_events = _make_fake_deepgram_module(connection)

    with patch.dict(sys.modules, _sys_modules_patch(fake_deepgram, fake_events)):
        from max_ai.voice.transcribe import DeepgramTranscriber

        transcriber = DeepgramTranscriber(api_key="test-key")
        await transcriber.start(on_transcript=lambda t, f: None, on_utterance_end=lambda: None)
        await transcriber.stop()
        await transcriber.stop()  # must not raise

    assert connection.send_close_stream.await_count == 1


async def test_send_before_start_raises() -> None:
    """send() must raise RuntimeError if called before start()."""
    from max_ai.voice.transcribe import DeepgramTranscriber

    transcriber = DeepgramTranscriber(api_key="test-key")

    with pytest.raises(RuntimeError, match="start()"):
        await transcriber.send(b"\x00\x01")
