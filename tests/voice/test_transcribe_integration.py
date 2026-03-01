"""Integration tests for the voice loop's STT path (Deepgram vs ElevenLabs)."""

import asyncio
import sys
from collections.abc import Callable
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic

from max_ai.db import ConversationService
from max_ai.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_fake_record(on_chunk_data: bytes = b"\x00\x01\x02\x03") -> Callable[..., bytes]:
    """Return a fake record_until_enter that calls on_chunk once then returns WAV bytes."""

    def fake_record(
        sample_rate: int,
        input_device: int | None,
        on_recording_started: Callable[[], None] | None,
        on_chunk: Callable[[bytes], None] | None = None,
    ) -> bytes:
        if on_recording_started is not None:
            on_recording_started()
        if on_chunk is not None:
            on_chunk(on_chunk_data)
        return b"fake-wav-bytes"

    return fake_record


def _make_mocks() -> (
    tuple[anthropic.AsyncAnthropic, ToolRegistry, ConversationService, "asyncio.Queue[Any]"]
):
    client = cast(anthropic.AsyncAnthropic, MagicMock(spec=anthropic.AsyncAnthropic))
    registry = cast(ToolRegistry, MagicMock(spec=ToolRegistry))
    conversation_service = cast(ConversationService, MagicMock(spec=ConversationService))
    conversation_service.create_conversation = AsyncMock(return_value="conv-1")  # type: ignore[method-assign]
    conversation_service.append_message = AsyncMock()  # type: ignore[method-assign]
    event_queue: asyncio.Queue[Any] = asyncio.Queue()
    return client, registry, conversation_service, event_queue


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_loop_uses_deepgram_when_key_set() -> None:
    """When deepgram_api_key is set, the loop must use DeepgramTranscriber for STT."""
    on_transcript_callback: Callable[[str, bool], None] | None = None
    on_utterance_end_callback: Callable[[], None] | None = None
    send_chunks: list[bytes] = []
    start_called = False
    stop_called = False

    class FakeTranscriber:
        def __init__(self, api_key: str) -> None:
            pass

        async def start(
            self,
            on_transcript: Callable[[str, bool], None],
            on_utterance_end: Callable[[], None],
        ) -> None:
            nonlocal on_transcript_callback, on_utterance_end_callback, start_called
            on_transcript_callback = on_transcript
            on_utterance_end_callback = on_utterance_end
            start_called = True

        async def send(self, audio_bytes: bytes) -> None:
            send_chunks.append(audio_bytes)
            # Simulate Deepgram returning a final transcript for each chunk
            if on_transcript_callback is not None:
                on_transcript_callback("hello world", True)

        async def stop(self) -> None:
            nonlocal stop_called
            stop_called = True
            # Simulate Deepgram firing UtteranceEnd on close
            if on_utterance_end_callback is not None:
                on_utterance_end_callback()

    captured_user_text: list[str] = []

    async def fake_run_agent_turn(agent: Any, user_text: str, conv_id: str) -> str:
        captured_user_text.append(user_text)
        return "agent response"

    client, registry, conversation_service, event_queue = _make_mocks()

    with (
        patch("max_ai.voice.loop.settings") as mock_settings,
        patch.dict(sys.modules, {"deepgram": MagicMock()}),
        patch("max_ai.voice.transcribe.DeepgramTranscriber", FakeTranscriber),
        patch("max_ai.voice.recorder.record_until_enter", side_effect=_make_fake_record()),
        patch("max_ai.voice.loop._wait_for_key", new=AsyncMock(return_value="enter")),
        patch("max_ai.voice.loop._run_agent_turn", new=AsyncMock(side_effect=fake_run_agent_turn)),
        patch(
            "max_ai.voice.loop._speak_and_handle_interrupt",
            new=AsyncMock(return_value=(True, False, b"")),
        ),
    ):
        mock_settings.deepgram_api_key = "fake-deepgram-key"
        mock_settings.elevenlabs_api_key = "fake-elev-key"
        mock_settings.spotify_client_id = ""
        mock_settings.spotify_client_secret = ""
        mock_settings.enable_web_search = False
        mock_settings.debug = False
        mock_settings.voice_input_device = None
        mock_settings.web_search_max_uses = 0

        from max_ai.voice.loop import voice_chat_loop

        await voice_chat_loop(client, registry, conversation_service, event_queue, "system")

    assert start_called, "DeepgramTranscriber.start() was not called"
    assert len(send_chunks) > 0, "DeepgramTranscriber.send() was never called"
    assert stop_called, "DeepgramTranscriber.stop() was not called"
    assert captured_user_text == ["hello world"]


async def test_loop_falls_back_to_elevenlabs_when_no_deepgram_key() -> None:
    """When deepgram_api_key is empty, the loop must call the ElevenLabs transcribe()."""
    elevenlabs_transcribe_called = False

    async def fake_transcribe(
        wav_bytes: bytes, api_key: str, model_id: str, language_code: str
    ) -> str:
        nonlocal elevenlabs_transcribe_called
        elevenlabs_transcribe_called = True
        return "elevenlabs transcript"

    captured_user_text: list[str] = []

    async def fake_run_agent_turn(agent: Any, user_text: str, conv_id: str) -> str:
        captured_user_text.append(user_text)
        return "agent response"

    client, registry, conversation_service, event_queue = _make_mocks()

    with (
        patch("max_ai.voice.loop.settings") as mock_settings,
        patch("max_ai.voice.stt.transcribe", new=fake_transcribe),
        patch("max_ai.voice.recorder.record_until_enter", side_effect=_make_fake_record()),
        patch("max_ai.voice.loop._wait_for_key", new=AsyncMock(return_value="enter")),
        patch("max_ai.voice.loop._run_agent_turn", new=AsyncMock(side_effect=fake_run_agent_turn)),
        patch(
            "max_ai.voice.loop._speak_and_handle_interrupt",
            new=AsyncMock(return_value=(True, False, b"")),
        ),
    ):
        mock_settings.deepgram_api_key = ""
        mock_settings.elevenlabs_api_key = "fake-elev-key"
        mock_settings.elevenlabs_stt_model = "scribe_v1"
        mock_settings.elevenlabs_stt_language = "en"
        mock_settings.spotify_client_id = ""
        mock_settings.spotify_client_secret = ""
        mock_settings.enable_web_search = False
        mock_settings.debug = False
        mock_settings.voice_input_device = None
        mock_settings.web_search_max_uses = 0

        from max_ai.voice.loop import voice_chat_loop

        await voice_chat_loop(client, registry, conversation_service, event_queue, "system")

    assert elevenlabs_transcribe_called, "ElevenLabs transcribe() was not called"
    assert captured_user_text == ["elevenlabs transcript"]
