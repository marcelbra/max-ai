"""Push-to-talk microphone recorder."""

import io
from typing import Any

import noisereduce as nr
import numpy as np
import sounddevice as sd
import soundfile as sf


def _denoise(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Apply spectral gating noise reduction. Input/output: int16 (N, 1)."""
    flat = audio.flatten().astype(np.float32) / 32768.0
    denoised = nr.reduce_noise(y=flat, sr=sample_rate)
    return (denoised * 32768.0).clip(-32768, 32767).astype(np.int16).reshape(-1, 1)


def record_until_enter(sample_rate: int = 16000) -> bytes:
    """Record audio from the microphone until the user presses Enter.

    Applies background noise reduction before encoding.
    Returns raw WAV bytes suitable for sending to a STT API.
    """
    chunks: list[np.ndarray] = []

    def callback(indata: np.ndarray, frames: int, time: Any, status: sd.CallbackFlags) -> None:
        chunks.append(indata.copy())

    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="int16", callback=callback):
        input()  # blocks until Enter

    audio = np.concatenate(chunks, axis=0) if chunks else np.zeros((0, 1), dtype=np.int16)
    if audio.shape[0] > 0:
        audio = _denoise(audio, sample_rate)

    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()
