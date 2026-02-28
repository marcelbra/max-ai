"""Push-to-talk microphone recorder."""

import io
from typing import Any

import numpy as np
import sounddevice as sd
import soundfile as sf


def record_until_enter(sample_rate: int = 16000) -> bytes:
    """Record audio from the microphone until the user presses Enter.

    Returns raw WAV bytes suitable for sending to a STT API.
    """
    chunks: list[np.ndarray] = []

    def callback(indata: np.ndarray, frames: int, time: Any, status: sd.CallbackFlags) -> None:
        chunks.append(indata.copy())

    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="int16", callback=callback):
        input()  # blocks until Enter

    audio = np.concatenate(chunks, axis=0) if chunks else np.zeros((0, 1), dtype=np.int16)
    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()
