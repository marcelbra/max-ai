"""Push-to-talk microphone recorder."""

import io
import sys
import termios
import tty
from typing import Any

import noisereduce as nr
import numpy as np
import sounddevice as sd
import soundfile as sf


class VoiceExit(Exception):
    """Raised when the user presses 'x' to exit voice mode."""


def _read_key() -> str:
    """Read a single keypress in cbreak mode. Returns 'enter' or 'x'."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch in ("\n", "\r"):
                return "enter"
            if ch.lower() == "x":
                return "x"
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _denoise(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Apply spectral gating noise reduction (two passes). Input/output: int16 (N, 1)."""
    flat = audio.flatten().astype(np.float32) / 32768.0
    denoised = nr.reduce_noise(y=flat, sr=sample_rate)
    denoised = nr.reduce_noise(y=denoised, sr=sample_rate)  # second pass removes residual noise
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
        key = _read_key()
        if key == "x":
            raise VoiceExit()

    audio = np.concatenate(chunks, axis=0) if chunks else np.zeros((0, 1), dtype=np.int16)
    if audio.shape[0] > 0:
        audio = _denoise(audio, sample_rate)

    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()
