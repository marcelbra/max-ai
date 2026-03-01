"""Streaming transcription via Deepgram WebSocket API."""

from collections.abc import Callable
from typing import Any


class DeepgramTranscriber:
    """Streams audio to Deepgram and delivers transcript/utterance-end events."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._connection: Any = None

    async def start(
        self,
        on_transcript: Callable[[str, bool], None],
        on_utterance_end: Callable[[], None],
    ) -> None:
        """Open a Deepgram WebSocket connection and register event handlers."""
        from deepgram import (  # lazy: optional wake-word extra
            DeepgramClient,
            LiveOptions,
            LiveTranscriptionEvents,
        )

        client = DeepgramClient(self._api_key)
        connection = client.listen.asyncwebsocket.v("1")

        async def _on_transcript(self_: Any, result: Any, **kwargs: Any) -> None:
            sentence = result.channel.alternatives[0].transcript
            is_final = result.is_final
            if sentence:
                on_transcript(sentence, is_final)

        async def _on_utterance_end(self_: Any, utterance_end: Any, **kwargs: Any) -> None:
            on_utterance_end()

        connection.on(LiveTranscriptionEvents.Transcript, _on_transcript)
        connection.on(LiveTranscriptionEvents.UtteranceEnd, _on_utterance_end)

        options = LiveOptions(
            model="nova-2",
            language="en",
            smart_format=True,
            interim_results=True,
            utterance_end_ms="1500",
            vad_events=True,
            encoding="linear16",
            sample_rate=16000,
        )
        await connection.start(options)
        self._connection = connection

    async def send(self, audio_chunk: bytes) -> None:
        """Send a raw PCM audio chunk to Deepgram."""
        if self._connection is not None:
            await self._connection.send(audio_chunk)

    async def stop(self) -> None:
        """Close the Deepgram WebSocket connection."""
        if self._connection is not None:
            await self._connection.finish()
            self._connection = None
