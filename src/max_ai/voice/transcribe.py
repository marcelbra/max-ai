"""Deepgram streaming transcription client."""

from collections.abc import Callable
from typing import Any


class DeepgramTranscriber:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._connection: Any | None = None  # deepgram LiveClient

    async def start(
        self,
        on_transcript: Callable[[str, bool], None],
        on_utterance_end: Callable[[], None],
    ) -> None:
        """Open Deepgram WebSocket.

        Calls on_transcript(text, is_final) for each transcript result.
        Calls on_utterance_end() when Deepgram fires the UtteranceEnd event.

        Options:
          model="nova-2", language="en", smart_format=True,
          interim_results=True, utterance_end_ms=1500,
          vad_events=True, encoding="linear16", sample_rate=16000
        """
        from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents  # lazy

        client = DeepgramClient(self._api_key)
        connection = client.listen.asynclive.v("1")

        async def _on_transcript(self_: Any, result: Any, **kwargs: Any) -> None:
            text: str = result.channel.alternatives[0].transcript
            is_final: bool = result.is_final
            on_transcript(text, is_final)

        async def _on_utterance_end(self_: Any, utterance_end: Any, **kwargs: Any) -> None:
            on_utterance_end()

        connection.on(LiveTranscriptionEvents.Transcript, _on_transcript)
        connection.on(LiveTranscriptionEvents.UtteranceEnd, _on_utterance_end)

        options = LiveOptions(
            model="nova-2",
            language="en",
            smart_format=True,
            interim_results=True,
            utterance_end_ms=1500,
            vad_events=True,
            encoding="linear16",
            sample_rate=16000,
        )

        await connection.start(options)
        self._connection = connection

    async def send(self, audio_chunk: bytes) -> None:
        """Send raw int16 PCM bytes to the open WebSocket."""
        if self._connection is None:
            raise RuntimeError("DeepgramTranscriber.start() must be called before send()")
        await self._connection.send(audio_chunk)

    async def stop(self) -> None:
        """Close the WebSocket connection. Safe to call more than once."""
        if self._connection is None:
            return
        await self._connection.finish()
        self._connection = None
