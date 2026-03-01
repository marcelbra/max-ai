"""Deepgram streaming transcription client."""

import asyncio
from collections.abc import Callable
from typing import Any


class DeepgramTranscriber:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._connection: Any | None = None
        self._context_manager: Any | None = None
        self._listen_task: asyncio.Task[None] | None = None

    async def start(
        self,
        on_transcript: Callable[[str, bool], None],
        on_utterance_end: Callable[[], None],
    ) -> None:
        """Open Deepgram WebSocket and begin streaming.

        Calls ``on_transcript(text, is_final)`` for each transcript result.
        Calls ``on_utterance_end()`` when Deepgram fires the UtteranceEnd event.

        Connection options:
          model="nova-2", language="en", smart_format=True,
          interim_results=True, utterance_end_ms=1500,
          vad_events=True, encoding="linear16", sample_rate=16000
        """
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

        def _on_message(message: Any) -> None:
            message_type = getattr(message, "type", None)
            if message_type == "Results":
                text: str = message.channel.alternatives[0].transcript
                is_final: bool = bool(message.is_final)
                on_transcript(text, is_final)
            elif message_type == "UtteranceEnd":
                on_utterance_end()

        self._connection.on(EventType.MESSAGE, _on_message)
        self._listen_task = asyncio.create_task(self._connection.start_listening())

    async def send(self, audio_chunk: bytes) -> None:
        """Send raw int16 PCM bytes to the open WebSocket."""
        if self._connection is None:
            raise RuntimeError("DeepgramTranscriber.start() must be called before send()")
        await self._connection.send_media(audio_chunk)

    async def stop(self) -> None:
        """Flush remaining transcripts and close the connection. Safe to call more than once."""
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
