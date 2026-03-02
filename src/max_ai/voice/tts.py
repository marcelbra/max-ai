"""ElevenLabs Text-to-Speech with sounddevice playback."""

import asyncio
import logging
import threading
import time

import numpy as np
import sounddevice as sd
from elevenlabs.client import ElevenLabs

_logger = logging.getLogger(__name__)

_SAMPLE_RATE = 22050
_MAX_RETRIES = 3
_RETRY_DELAY = 1.0
_PITCH_SEMITONES = 1.5  # slight upward pitch for clarity


def _pitch_shift(audio: np.ndarray, semitones: float = _PITCH_SEMITONES) -> np.ndarray:
    """Pitch-shift audio up by semitones via linear resampling. Input/output: int16 (N,)."""
    ratio = 2.0 ** (semitones / 12.0)
    n = len(audio)
    n_short = max(1, int(round(n / ratio)))
    flat = audio.astype(np.float32)
    compressed = np.interp(np.linspace(0, n - 1, n_short), np.arange(n), flat)
    stretched = np.interp(np.linspace(0, n_short - 1, n), np.arange(n_short), compressed)
    return stretched.clip(-32768, 32767).astype(np.int16)


async def speak(
    text: str,
    api_key: str,
    voice_id: str,
    model_id: str = "eleven_turbo_v2_5",
    stop_event: threading.Event | None = None,
    output_device: int | None = None,
) -> bytes:
    """Convert text to speech via ElevenLabs and play it through the speakers.

    Uses pcm_22050 output format for direct sounddevice playback (no ffmpeg needed).
    Returns the raw PCM bytes (int16, 22050 Hz) for optional downstream use (e.g. debug saving).
    Pass a threading.Event as stop_event to interrupt playback cleanly without PortAudio errors.
    """
    client = ElevenLabs(api_key=api_key)

    def _generate() -> bytes:
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                chunks = client.text_to_speech.convert(
                    voice_id=voice_id,
                    text=text,
                    model_id=model_id,
                    output_format="pcm_22050",
                )
                return b"".join(chunks)
            except Exception as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_DELAY * (attempt + 1))
        raise last_exc  # type: ignore[misc]

    pcm_bytes = await asyncio.to_thread(_generate)
    audio = _pitch_shift(np.frombuffer(pcm_bytes, dtype=np.int16))

    def _play(thread_stop_event: threading.Event | None) -> None:
        position = 0
        done = threading.Event()

        def callback(
            outdata: np.ndarray, frames: int, _time: object, _status: sd.CallbackFlags
        ) -> None:
            nonlocal position
            if thread_stop_event is not None and thread_stop_event.is_set():
                outdata[:] = 0
                raise sd.CallbackStop
            remaining = len(audio) - position
            if remaining <= 0:
                outdata[:] = 0
                raise sd.CallbackStop
            frames_to_write = min(frames, remaining)
            outdata[:frames_to_write, 0] = audio[position : position + frames_to_write]
            if frames_to_write < frames:
                outdata[frames_to_write:] = 0
            position += frames_to_write

        with sd.OutputStream(
            samplerate=_SAMPLE_RATE,
            channels=1,
            dtype="int16",
            device=output_device,
            callback=callback,
            finished_callback=done.set,
        ):
            done.wait()

    await asyncio.to_thread(_play, stop_event)
    return pcm_bytes


class TTSPlayer:
    """Orchestrator-facing TTS component.

    speak() accepts an asyncio.Event for interruption, bridging to the
    threading.Event that the sounddevice callback checks.
    """

    def __init__(
        self,
        api_key: str,
        voice_id: str,
        model_id: str = "eleven_turbo_v2_5",
        output_device: int | None = None,
    ) -> None:
        self._api_key = api_key
        self._voice_id = voice_id
        self._model_id = model_id
        self._output_device = output_device

    async def speak(self, text: str, stop_event: asyncio.Event) -> None:
        """Play TTS audio. Returns when done or stop_event is set."""
        _logger.debug("tts speak start: %d chars", len(text))
        thread_stop_event = threading.Event()

        async def _watch_stop() -> None:
            await stop_event.wait()
            thread_stop_event.set()

        watch_task = asyncio.create_task(_watch_stop())
        try:
            await speak(
                text=text,
                api_key=self._api_key,
                voice_id=self._voice_id,
                model_id=self._model_id,
                stop_event=thread_stop_event,
                output_device=self._output_device,
            )
        finally:
            watch_task.cancel()
            try:
                await watch_task
            except asyncio.CancelledError:
                pass
        _logger.debug("tts speak end")
