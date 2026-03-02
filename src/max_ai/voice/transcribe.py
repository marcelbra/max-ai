"""Deepgram streaming transcription client.

StreamingTranscriber opens a Deepgram WebSocket and puts TranscriptPartial
and UtteranceEnd events onto the EventBus.

Lazy-imports deepgram-sdk inside start() so the module loads when the SDK
is not installed.
"""

import asyncio
import logging
from typing import Any

from max_ai.voice.events import EventBus, TranscriptPartial, UtteranceEnd

_logger = logging.getLogger(__name__)


class StreamingTranscriber:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._connection: Any | None = None
        self._context_manager: Any | None = None
        self._listen_task: asyncio.Task[None] | None = None

    async def start(self, bus: EventBus) -> None:
        """Open Deepgram WebSocket. Puts TranscriptPartial and UtteranceEnd onto bus.

        Connection options:
          model="nova-2", language="en", smart_format=True,
          interim_results=True, utterance_end_ms=1500,
          vad_events=True, encoding="linear16", sample_rate=16000
        """
        _logger.debug("transcriber start")
        from deepgram import AsyncDeepgramClient  # lazy: optional dependency
        from deepgram.core.events import EventType  # lazy: optional dependency

        client = AsyncDeepgramClient(api_key=self._api_key)
        self._context_manager = client.listen.v1.connect(
            model="nova-2",
            language="en",
            smart_format="true",
            interim_results="true",
            utterance_end_ms="1500",
            vad_events="true",
            encoding="linear16",
            sample_rate="16000",
        )
        self._connection = await self._context_manager.__aenter__()

        accumulated_transcript: list[str] = []

        def _on_message(message: Any) -> None:
            message_type = getattr(message, "type", None)
            if message_type == "Results":
                text: str = message.channel.alternatives[0].transcript
                is_final: bool = bool(message.is_final)
                if text:
                    bus.put_nowait(TranscriptPartial(text=text))
                    if is_final:
                        accumulated_transcript.append(text)
            elif message_type == "UtteranceEnd":
                full_transcript = " ".join(part for part in accumulated_transcript if part)
                accumulated_transcript.clear()
                bus.put_nowait(UtteranceEnd(transcript=full_transcript))

        self._connection.on(EventType.MESSAGE, _on_message)
        self._listen_task = asyncio.create_task(self._connection.start_listening())

    async def send(self, audio_chunk: bytes) -> None:
        """Send raw int16 PCM bytes to the open WebSocket."""
        _logger.debug("transcriber send %d bytes", len(audio_chunk))
        if self._connection is None:
            raise RuntimeError("StreamingTranscriber.start() must be called before send()")
        await self._connection.send_media(audio_chunk)

    async def stop(self) -> None:
        """Flush remaining transcripts and close the connection. Safe to call more than once."""
        _logger.debug("transcriber stop")
        if self._connection is None:
            return
        connection = self._connection
        context_manager = self._context_manager
        listen_task = self._listen_task
        self._connection = None
        self._context_manager = None
        self._listen_task = None

        try:
            await connection.send_close_stream()
        except Exception:
            pass

        if listen_task is not None:
            # Wait up to 2 s for Deepgram to drain final messages (including UtteranceEnd).
            try:
                await asyncio.wait_for(asyncio.shield(listen_task), timeout=2.0)
            except Exception:
                pass
            if not listen_task.done():
                listen_task.cancel()
                try:
                    await listen_task
                except (asyncio.CancelledError, Exception):
                    pass

        if context_manager is not None:
            try:
                await context_manager.__aexit__(None, None, None)
            except Exception:
                pass
