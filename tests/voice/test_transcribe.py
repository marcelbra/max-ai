"""Tests for the Deepgram streaming transcriber."""

import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock


def _install_deepgram_stub() -> MagicMock:
    """Install a fake deepgram module in sys.modules."""
    mock_deepgram = MagicMock()

    # LiveTranscriptionEvents stubs
    mock_deepgram.LiveTranscriptionEvents.Transcript = "Transcript"
    mock_deepgram.LiveTranscriptionEvents.UtteranceEnd = "UtteranceEnd"

    sys.modules["deepgram"] = mock_deepgram
    return mock_deepgram


def _force_reimport() -> None:
    for key in list(sys.modules.keys()):
        if "max_ai.voice.transcribe" in key:
            del sys.modules[key]


def test_start_calls_connection_start_with_options() -> None:
    """start() opens a Deepgram WebSocket connection with the expected LiveOptions."""
    mock_deepgram = _install_deepgram_stub()
    _force_reimport()

    mock_connection = MagicMock()
    mock_connection.start = AsyncMock()
    mock_connection.on = MagicMock()

    mock_client = MagicMock()
    mock_client.listen.asyncwebsocket.v.return_value = mock_connection
    mock_deepgram.DeepgramClient.return_value = mock_client

    import asyncio

    from max_ai.voice.transcribe import DeepgramTranscriber

    transcriber = DeepgramTranscriber(api_key="dg-key")
    asyncio.get_event_loop().run_until_complete(
        transcriber.start(on_transcript=lambda t, f: None, on_utterance_end=lambda: None)
    )

    mock_connection.start.assert_called_once()
    # LiveOptions is mocked, so verify it was constructed with expected kwargs
    _, live_options_kwargs = mock_deepgram.LiveOptions.call_args
    assert live_options_kwargs["model"] == "nova-2"
    assert live_options_kwargs["encoding"] == "linear16"
    assert live_options_kwargs["sample_rate"] == 16000


def test_start_registers_transcript_and_utterance_end_handlers() -> None:
    """start() registers handlers for both Transcript and UtteranceEnd events."""
    mock_deepgram = _install_deepgram_stub()
    _force_reimport()

    mock_connection = MagicMock()
    mock_connection.start = AsyncMock()
    registered_events: list[str] = []

    def _on_handler(event: Any, handler: Any) -> None:
        registered_events.append(event)

    mock_connection.on = _on_handler

    mock_client = MagicMock()
    mock_client.listen.asyncwebsocket.v.return_value = mock_connection
    mock_deepgram.DeepgramClient.return_value = mock_client

    import asyncio

    from max_ai.voice.transcribe import DeepgramTranscriber

    transcriber = DeepgramTranscriber(api_key="dg-key")
    asyncio.get_event_loop().run_until_complete(
        transcriber.start(on_transcript=lambda t, f: None, on_utterance_end=lambda: None)
    )

    assert "Transcript" in registered_events
    assert "UtteranceEnd" in registered_events


def test_stop_calls_connection_finish() -> None:
    """stop() calls finish() on the active connection."""
    mock_deepgram = _install_deepgram_stub()
    _force_reimport()

    mock_connection = MagicMock()
    mock_connection.start = AsyncMock()
    mock_connection.finish = AsyncMock()
    mock_connection.on = MagicMock()

    mock_client = MagicMock()
    mock_client.listen.asyncwebsocket.v.return_value = mock_connection
    mock_deepgram.DeepgramClient.return_value = mock_client

    import asyncio

    from max_ai.voice.transcribe import DeepgramTranscriber

    transcriber = DeepgramTranscriber(api_key="dg-key")
    asyncio.get_event_loop().run_until_complete(
        transcriber.start(on_transcript=lambda t, f: None, on_utterance_end=lambda: None)
    )
    asyncio.get_event_loop().run_until_complete(transcriber.stop())

    mock_connection.finish.assert_called_once()


def test_stop_when_not_started_does_nothing() -> None:
    """stop() is a no-op when the connection was never started."""
    _install_deepgram_stub()
    _force_reimport()

    import asyncio

    from max_ai.voice.transcribe import DeepgramTranscriber

    transcriber = DeepgramTranscriber(api_key="dg-key")
    # Should not raise
    asyncio.get_event_loop().run_until_complete(transcriber.stop())


def test_send_when_not_started_does_nothing() -> None:
    """send() is a no-op when the connection is not active."""
    _install_deepgram_stub()
    _force_reimport()

    import asyncio

    from max_ai.voice.transcribe import DeepgramTranscriber

    transcriber = DeepgramTranscriber(api_key="dg-key")
    # Should not raise
    asyncio.get_event_loop().run_until_complete(transcriber.send(b"\x00\x00"))
