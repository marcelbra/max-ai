"""Tests for DeepgramTranscriber — callbacks, connection lifecycle, and error handling."""

import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fake Deepgram SDK
# ---------------------------------------------------------------------------

TRANSCRIPT_EVENT = "Transcript"
UTTERANCE_END_EVENT = "UtteranceEnd"


class _FakeConnection:
    """Fake Deepgram asynclive connection that records event handlers."""

    def __init__(self) -> None:
        self.handlers: dict[str, Any] = {}
        self.finish: AsyncMock = AsyncMock()
        self.send: AsyncMock = AsyncMock()

    def on(self, event: str, handler: Any) -> None:
        self.handlers[event] = handler

    async def start(self, options: Any) -> bool:
        return True


class _FakeLiveOptions:
    def __init__(self, **kwargs: Any) -> None:
        pass


class _FakeLiveTranscriptionEvents:
    Transcript = TRANSCRIPT_EVENT
    UtteranceEnd = UTTERANCE_END_EVENT


def _make_fake_deepgram_module(connection: _FakeConnection) -> MagicMock:
    """Return a MagicMock deepgram module wired to the given fake connection."""
    fake_client_instance = MagicMock()
    fake_client_instance.listen.asynclive.v.return_value = connection

    fake_deepgram = MagicMock()
    fake_deepgram.DeepgramClient.return_value = fake_client_instance
    fake_deepgram.LiveOptions = _FakeLiveOptions
    fake_deepgram.LiveTranscriptionEvents = _FakeLiveTranscriptionEvents
    return fake_deepgram


def _make_transcript_result(text: str, is_final: bool) -> MagicMock:
    result = MagicMock()
    result.channel.alternatives[0].transcript = text
    result.is_final = is_final
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_transcript_fires_for_interim_result() -> None:
    """on_transcript must be called with (text, False) for interim transcripts."""
    connection = _FakeConnection()
    fake_deepgram = _make_fake_deepgram_module(connection)

    received: list[tuple[str, bool]] = []

    with patch.dict(sys.modules, {"deepgram": fake_deepgram}):
        from max_ai.voice.transcribe import DeepgramTranscriber

        transcriber = DeepgramTranscriber(api_key="test-key")
        await transcriber.start(
            on_transcript=lambda text, is_final: received.append((text, is_final)),
            on_utterance_end=lambda: None,
        )

    handler = connection.handlers[TRANSCRIPT_EVENT]
    await handler(connection, _make_transcript_result("hello", False))

    assert received == [("hello", False)]


@pytest.mark.asyncio
async def test_on_transcript_fires_for_final_result() -> None:
    """on_transcript must be called with (text, True) for final transcripts."""
    connection = _FakeConnection()
    fake_deepgram = _make_fake_deepgram_module(connection)

    received: list[tuple[str, bool]] = []

    with patch.dict(sys.modules, {"deepgram": fake_deepgram}):
        from max_ai.voice.transcribe import DeepgramTranscriber

        transcriber = DeepgramTranscriber(api_key="test-key")
        await transcriber.start(
            on_transcript=lambda text, is_final: received.append((text, is_final)),
            on_utterance_end=lambda: None,
        )

    handler = connection.handlers[TRANSCRIPT_EVENT]
    await handler(connection, _make_transcript_result("world", True))

    assert received == [("world", True)]


@pytest.mark.asyncio
async def test_on_utterance_end_fires() -> None:
    """on_utterance_end must be called when Deepgram fires the UtteranceEnd event."""
    connection = _FakeConnection()
    fake_deepgram = _make_fake_deepgram_module(connection)

    calls: list[bool] = []

    with patch.dict(sys.modules, {"deepgram": fake_deepgram}):
        from max_ai.voice.transcribe import DeepgramTranscriber

        transcriber = DeepgramTranscriber(api_key="test-key")
        await transcriber.start(
            on_transcript=lambda text, is_final: None,
            on_utterance_end=lambda: calls.append(True),
        )

    handler = connection.handlers[UTTERANCE_END_EVENT]
    await handler(connection, MagicMock())

    assert calls == [True]


@pytest.mark.asyncio
async def test_stop_closes_connection() -> None:
    """stop() must call finish() on the underlying Deepgram connection."""
    connection = _FakeConnection()
    fake_deepgram = _make_fake_deepgram_module(connection)

    with patch.dict(sys.modules, {"deepgram": fake_deepgram}):
        from max_ai.voice.transcribe import DeepgramTranscriber

        transcriber = DeepgramTranscriber(api_key="test-key")
        await transcriber.start(on_transcript=lambda t, f: None, on_utterance_end=lambda: None)
        await transcriber.stop()

    connection.finish.assert_awaited_once()


@pytest.mark.asyncio
async def test_stop_is_idempotent() -> None:
    """stop() must not raise when called a second time after the connection is already closed."""
    connection = _FakeConnection()
    fake_deepgram = _make_fake_deepgram_module(connection)

    with patch.dict(sys.modules, {"deepgram": fake_deepgram}):
        from max_ai.voice.transcribe import DeepgramTranscriber

        transcriber = DeepgramTranscriber(api_key="test-key")
        await transcriber.start(on_transcript=lambda t, f: None, on_utterance_end=lambda: None)
        await transcriber.stop()
        await transcriber.stop()  # must not raise

    assert connection.finish.await_count == 1


@pytest.mark.asyncio
async def test_send_before_start_raises() -> None:
    """send() must raise RuntimeError if called before start()."""
    from max_ai.voice.transcribe import DeepgramTranscriber

    transcriber = DeepgramTranscriber(api_key="test-key")

    with pytest.raises(RuntimeError, match="start()"):
        await transcriber.send(b"\x00\x01")
