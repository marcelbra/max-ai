"""ElevenLabs Text-to-Speech with sounddevice playback."""

import asyncio
import threading
import time

import numpy as np
import sounddevice as sd
from elevenlabs.client import ElevenLabs

_SAMPLE_RATE = 22050
_MAX_RETRIES = 3
_RETRY_DELAY = 1.0


async def speak(
    text: str,
    api_key: str,
    voice_id: str,
    model_id: str = "eleven_turbo_v2_5",
    stop_event: threading.Event | None = None,
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
    audio = np.frombuffer(pcm_bytes, dtype=np.int16)

    def _play() -> None:
        idx = 0
        done = threading.Event()

        def callback(outdata: np.ndarray, frames: int, _time: object, _status: sd.CallbackFlags) -> None:
            nonlocal idx
            if stop_event is not None and stop_event.is_set():
                outdata[:] = 0
                raise sd.CallbackStop
            remaining = len(audio) - idx
            if remaining <= 0:
                outdata[:] = 0
                raise sd.CallbackStop
            n = min(frames, remaining)
            outdata[:n, 0] = audio[idx : idx + n]
            if n < frames:
                outdata[n:] = 0
            idx += n

        with sd.OutputStream(
            samplerate=_SAMPLE_RATE,
            channels=1,
            dtype="int16",
            callback=callback,
            finished_callback=done.set,
        ):
            done.wait()

    await asyncio.to_thread(_play)
    return pcm_bytes
