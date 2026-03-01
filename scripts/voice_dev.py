#!/usr/bin/env python3
"""Voice pre-processing development tool.

Workflow per clip:
  1. Press Enter to start recording.
  2. Speak.
  3. Press Enter to stop.
  4. Noise-reduction + normalization pipeline runs; raw, denoised, and
     normalized WAVs are saved.

Output goes to voice_dev/ in the project root. Press q + Enter to quit.
"""

from __future__ import annotations

import datetime
import sys
import termios
import time
import tty
from pathlib import Path
from typing import Any

import noisereduce as nr
import numpy as np
import sounddevice as sd
import soundfile as sf

from max_ai.config import settings

OUTPUT_DIR = Path(__file__).parent.parent / "voice_dev"
SAMPLE_RATE = 16_000


def _getch() -> str:
    """Read one character without echo; returns the character."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _wait_for_enter_or_quit() -> str:
    """Block until Enter or 'q'. Returns 'enter' or 'q'."""
    while True:
        ch = _getch()
        if ch in ("\n", "\r"):
            return "enter"
        if ch.lower() == "q":
            return "q"


def _wait_for_enter() -> None:
    """Block until Enter (ignores other keys)."""
    while True:
        ch = _getch()
        if ch in ("\n", "\r"):
            return


def record() -> tuple[np.ndarray, float]:
    """Record until Enter; returns (audio int16 (N,1), duration_seconds).

    Prints the 'Recording' prompt only after the stream is open so the
    indicator appears the instant audio capture begins.
    """
    chunks: list[np.ndarray] = []

    def callback(indata: np.ndarray, frames: int, _time: Any, _status: sd.CallbackFlags) -> None:
        chunks.append(indata.copy())

    t0 = time.monotonic()
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        device=settings.voice_input_device,
        latency="low",
        callback=callback,
    ):
        print("\n  Recording …  (press Enter to stop)", end=" ", flush=True)
        _wait_for_enter()
    duration = time.monotonic() - t0

    audio = np.concatenate(chunks, axis=0) if chunks else np.zeros((0, 1), dtype=np.int16)
    return audio, duration


def denoise(audio: np.ndarray) -> np.ndarray:
    flat = audio.flatten().astype(np.float32) / 32768.0
    denoised = nr.reduce_noise(y=flat, sr=SAMPLE_RATE)
    denoised = nr.reduce_noise(y=denoised, sr=SAMPLE_RATE)
    denoised = np.nan_to_num(denoised)
    return (denoised * 32768.0).clip(-32768, 32767).astype(np.int16).reshape(-1, 1)


def normalize(audio: np.ndarray, target_peak: float = 0.80, max_gain: float = 4.0) -> np.ndarray:
    """Scale audio so the peak reaches target_peak of full int16 scale (capped at max_gain×)."""
    flat = audio.flatten().astype(np.float32)
    peak = np.abs(flat).max()
    if peak == 0:
        return audio
    gain = min((target_peak * 32767.0) / peak, max_gain)
    return (flat * gain).clip(-32768, 32767).astype(np.int16).reshape(-1, 1)


def rms_db(audio: np.ndarray) -> float:
    """RMS level in dBFS (0 = full scale). Returns -inf for silence."""
    mean_sq = float(np.mean(audio.astype(np.float64) ** 2))
    if mean_sq == 0:
        return float("-inf")
    return 20 * np.log10(np.sqrt(mean_sq) / 32768.0)


def save_wav(audio: np.ndarray, path: Path) -> None:
    with path.open("wb") as f:
        sf.write(f, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    device_label = f"device {settings.voice_input_device}" if settings.voice_input_device is not None else "default device"

    print("\nVoice Pipeline Dev Tool")
    print("=======================")
    print(f"Output dir : {OUTPUT_DIR}")
    print(f"Input      : {device_label}")
    print("Controls   : Enter = start/stop recording  |  q = quit\n")

    clip = 0
    while True:
        clip += 1
        print(
            f"[Clip {clip:02d}] Press Enter to start recording (q to quit) ...",
            end=" ",
            flush=True,
        )

        key = _wait_for_enter_or_quit()
        if key == "q":
            print("\nBye.")
            break

        print("  Preparing microphone …", end="\r", flush=True)
        audio, duration = record()
        print()

        if audio.shape[0] == 0:
            print("  No audio captured.\n")
            continue

        # --- Raw ---
        raw_path = OUTPUT_DIR / f"{ts}_clip{clip:02d}_raw.wav"
        save_wav(audio, raw_path)
        raw_db = rms_db(audio)

        # --- Denoise + normalize ---
        print("  Denoising …", end=" ", flush=True)
        denoised = denoise(audio)
        normalized = normalize(denoised)
        denoised_path = OUTPUT_DIR / f"{ts}_clip{clip:02d}_denoised.wav"
        normalized_path = OUTPUT_DIR / f"{ts}_clip{clip:02d}_normalized.wav"
        save_wav(denoised, denoised_path)
        save_wav(normalized, normalized_path)
        print("done.\n")

        denoised_db = rms_db(denoised)
        normalized_db = rms_db(normalized)

        print(f"  Duration   : {duration:.2f} s")
        print(f"  Level raw  : {raw_db:+.1f} dBFS")
        print(f"  Level post : {denoised_db:+.1f} dBFS  (Δ {denoised_db - raw_db:+.1f} dB vs raw)")
        print(f"  Level norm : {normalized_db:+.1f} dBFS  (Δ {normalized_db - raw_db:+.1f} dB vs raw)")
        print(f"  Raw        → {raw_path.name}")
        print(f"  Denoised   → {denoised_path.name}")
        print(f"  Normalized → {normalized_path.name}")
        print()


if __name__ == "__main__":
    main()
