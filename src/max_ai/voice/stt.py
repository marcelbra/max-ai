"""ElevenLabs Speech-to-Text."""

import asyncio
import io

from elevenlabs.client import ElevenLabs


async def transcribe(
    audio_wav: bytes, api_key: str, model_id: str = "scribe_v1", retries: int = 3
) -> str:
    """Convert WAV audio bytes to text using ElevenLabs STT.

    Returns the transcribed text, or an empty string if nothing was detected.
    Retries on transient connection errors (e.g. [Errno 54] Connection reset by peer).
    """
    client = ElevenLabs(api_key=api_key)

    def _call() -> str:
        result = client.speech_to_text.convert(
            file=io.BytesIO(audio_wav),
            model_id=model_id,
        )
        return result.text.strip()

    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return await asyncio.to_thread(_call)
        except Exception as e:
            last_exc = e
            if attempt < retries - 1:
                await asyncio.sleep(1.0)
    raise last_exc  # type: ignore[misc]
