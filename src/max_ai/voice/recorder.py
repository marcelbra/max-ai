"""Push-to-talk microphone recorder."""

import io
import sys
import termios
import tty
from collections.abc import Callable
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


_NORMALIZE_TARGET_PEAK = 0.80  # target peak as fraction of full int16 scale
_NORMALIZE_MAX_GAIN = 4.0  # never amplify more than 4× to avoid blowing up silence


def _denoise(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Apply spectral gating noise reduction (two passes). Input/output: int16 (N, 1)."""
    flat = audio.flatten().astype(np.float32) / 32768.0
    denoised = nr.reduce_noise(y=flat, sr=sample_rate)
    denoised = nr.reduce_noise(y=denoised, sr=sample_rate)
    denoised = np.nan_to_num(denoised)
    return (denoised * 32768.0).clip(-32768, 32767).astype(np.int16).reshape(-1, 1)  # type: ignore[no-any-return]


def _normalize(audio: np.ndarray) -> np.ndarray:
    """Boost audio after denoising to restore perceived loudness.

    Scales so the peak reaches _NORMALIZE_TARGET_PEAK of full int16 scale,
    capped at _NORMALIZE_MAX_GAIN× to avoid over-amplifying very quiet segments.
    Input/output: int16 (N, 1).
    """
    flat = audio.flatten().astype(np.float32)
    peak = np.abs(flat).max()
    if peak == 0:
        return audio
    gain = min((_NORMALIZE_TARGET_PEAK * 32767.0) / peak, _NORMALIZE_MAX_GAIN)
    return (flat * gain).clip(-32768, 32767).astype(np.int16).reshape(-1, 1)  # type: ignore[no-any-return]


def record_until_enter(
    sample_rate: int = 16000,
    input_device: int | None = None,
    on_recording_started: Callable[[], None] | None = None,
) -> bytes:
    """Record audio from the microphone until the user presses Enter.

    Applies background noise reduction and normalization before encoding.
    Returns raw WAV bytes suitable for sending to a STT API.

    Pass ``input_device`` to override the system default microphone (sounddevice index).
    This is useful when Bluetooth headphones are in use: opening a mic stream on the headset
    forces them from A2DP (high-quality) into HFP (low-quality) mode, degrading both the
    recording and the audio playback. Routing input to a separate built-in mic avoids this.

    Pass ``on_recording_started`` to receive a callback the instant the stream is open and
    capturing — use this to update UI so the "recording" indicator only appears once audio
    is actually being collected (stream initialization can take ~100–300 ms).
    """
    chunks: list[np.ndarray] = []

    def callback(indata: np.ndarray, frames: int, time: Any, status: sd.CallbackFlags) -> None:
        chunks.append(indata.copy())

    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
        device=input_device,
        latency="low",
        callback=callback,
    ):
        if on_recording_started is not None:
            on_recording_started()
        key = _read_key()
        if key == "x":
            raise VoiceExit()

    audio = np.concatenate(chunks, axis=0) if chunks else np.zeros((0, 1), dtype=np.int16)
    if audio.shape[0] > 0:
        audio = _denoise(audio, sample_rate)
        audio = _normalize(audio)

    wav_buffer = io.BytesIO()
    sf.write(wav_buffer, audio, sample_rate, format="WAV", subtype="PCM_16")
    return wav_buffer.getvalue()
