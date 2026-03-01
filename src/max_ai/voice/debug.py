"""Debug utilities for voice mode: paths and audio file saving."""

import io
from pathlib import Path

import numpy as np
import soundfile as sf
from rich.console import Console

MAX_AI_HOME = Path.home() / ".max-ai"
DEBUG_AUDIO_DIR = MAX_AI_HOME / "debug"
TTS_SAMPLE_RATE = 22050

console = Console()


def save_debug_files(wav_bytes: bytes, pcm_bytes: bytes, stamp: str) -> None:
    """Save input WAV and output PCM as WAV to the debug directory."""
    DEBUG_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    input_path = DEBUG_AUDIO_DIR / f"{stamp}_input.wav"
    input_path.write_bytes(wav_bytes)

    output_path = DEBUG_AUDIO_DIR / f"{stamp}_output.wav"
    audio = np.frombuffer(pcm_bytes, dtype=np.int16)
    wav_buffer = io.BytesIO()
    sf.write(wav_buffer, audio, TTS_SAMPLE_RATE, format="WAV", subtype="PCM_16")
    output_path.write_bytes(wav_buffer.getvalue())

    console.print(f"[dim]Debug audio saved to {DEBUG_AUDIO_DIR}/{stamp}_{{input,output}}.wav[/]")
