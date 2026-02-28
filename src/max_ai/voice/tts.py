"""ElevenLabs Text-to-Speech with sounddevice playback."""

import asyncio
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
) -> bytes:
    """Convert text to speech via ElevenLabs and play it through the speakers.

    Uses pcm_22050 output format for direct sounddevice playback (no ffmpeg needed).
    Returns the raw PCM bytes (int16, 22050 Hz) for optional downstream use (e.g. debug saving).
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
    sd.play(audio, samplerate=_SAMPLE_RATE)
    await asyncio.to_thread(sd.wait)
    return pcm_bytes
