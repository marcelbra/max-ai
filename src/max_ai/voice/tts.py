"""ElevenLabs Text-to-Speech with sounddevice playback."""

import asyncio

import numpy as np
import sounddevice as sd
from elevenlabs.client import ElevenLabs

_SAMPLE_RATE = 22050


async def speak(
    text: str,
    api_key: str,
    voice_id: str,
    model_id: str = "eleven_turbo_v2_5",
) -> None:
    """Convert text to speech via ElevenLabs and play it through the speakers.

    Uses pcm_22050 output format for direct sounddevice playback (no ffmpeg needed).
    """
    client = ElevenLabs(api_key=api_key)

    def _generate() -> bytes:
        chunks = client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id=model_id,
            output_format="pcm_22050",
        )
        return b"".join(chunks)

    pcm_bytes = await asyncio.to_thread(_generate)
    audio = np.frombuffer(pcm_bytes, dtype=np.int16)
    sd.play(audio, samplerate=_SAMPLE_RATE)
    await asyncio.to_thread(sd.wait)
