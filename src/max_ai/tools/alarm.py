"""Alarm tool — plays a beep tone via sounddevice."""

import asyncio
from typing import Any

import numpy as np

from max_ai.tools.base import BaseTool, ToolDefinition

_SAMPLE_RATE = 44100
_BEEP_HZ = 880
_BEEP_DURATION = 0.3  # seconds per beep
_BEEP_PAUSE = 0.15  # silence between beeps
_BEEPS = 3


def _make_beep(freq: float, duration: float, sample_rate: int) -> np.ndarray:
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    wave = np.sin(2 * np.pi * freq * t)
    # Fade in/out to avoid clicks
    fade = int(sample_rate * 0.01)
    wave[:fade] *= np.linspace(0, 1, fade)
    wave[-fade:] *= np.linspace(1, 0, fade)
    return (wave * 32767).astype(np.int16)


def _play_alarm() -> None:
    import sounddevice as sd  # noqa: PLC0415 — optional platform dep, lazy import

    beep = _make_beep(_BEEP_HZ, _BEEP_DURATION, _SAMPLE_RATE)
    silence = np.zeros(int(_SAMPLE_RATE * _BEEP_PAUSE), dtype=np.int16)
    pattern = np.concatenate([np.concatenate([beep, silence]) for _ in range(_BEEPS)])
    sd.play(pattern, samplerate=_SAMPLE_RATE)
    sd.wait()


class AlarmTool(BaseTool):
    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="sound_alarm",
                description=(
                    "Play an audible beep alarm to the user. "
                    "Call this when a timer fires or when you need to alert the user "
                    "with an urgent notification."
                ),
                input_schema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            )
        ]

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        await asyncio.to_thread(_play_alarm)
        return "Alarm sounded."
