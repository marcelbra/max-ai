"""Wake-word detection components.

WakeWordDetector wraps Porcupine (pvporcupine, lazy import).
KeyboardWakeWordDetector is the push-to-talk fallback: Enter key fires
WakeWordDetected, so the orchestrator is unchanged.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable

from max_ai.voice.events import EventBus, WakeWordDetected


def _make_key_press_handler(future: asyncio.Future[str]) -> Callable[[], None]:
    """Return a stdin reader callback bound to a specific future.

    Extracted to module level to satisfy B023 (function in loop must not
    capture loop variables by reference).
    """

    def _on_key_press() -> None:
        character = sys.stdin.read(1)
        if character in ("\n", "\r"):
            if not future.done():
                future.set_result("enter")
        elif character.lower() == "x":
            if not future.done():
                future.set_result("x")

    return _on_key_press


class WakeWordDetector:
    """Porcupine-based wake-word detector.

    Lazy-imports pvporcupine so the module loads even when the package is
    not installed (wake-word extras not present).
    """

    def __init__(self, access_key: str, keyword_path: str = "") -> None:
        import pvporcupine  # lazy: wake-word extra

        if keyword_path:
            self._porcupine = pvporcupine.create(
                access_key=access_key, keyword_paths=[keyword_path]
            )
        else:
            self._porcupine = pvporcupine.create(access_key=access_key, keywords=["porcupine"])

    def process(self, audio_frame: bytes) -> bool:
        """Feed exactly frame_length int16 samples. Returns True on detection."""
        import struct

        samples_count = len(audio_frame) // 2
        samples = list(struct.unpack(f"{samples_count}h", audio_frame))
        result: int = self._porcupine.process(samples)
        return result >= 0

    @property
    def frame_length(self) -> int:
        """Number of int16 samples per frame (typically 512)."""
        return int(self._porcupine.frame_length)

    @property
    def sample_rate(self) -> int:
        """Sample rate required by Porcupine (always 16000)."""
        return int(self._porcupine.sample_rate)

    def close(self) -> None:
        self._porcupine.delete()


class KeyboardWakeWordDetector:
    """Push-to-talk fallback: Enter key triggers WakeWordDetected.

    Runs as a background task while the orchestrator is in IDLE state.
    Pressing Enter puts WakeWordDetected onto the bus.
    Pressing 'x' puts None (signals shutdown) — callers must handle it.
    """

    async def run(self, bus: EventBus) -> None:
        """Listen for Enter/x in a non-blocking way.  Runs until cancelled."""
        import termios
        import tty

        loop = asyncio.get_running_loop()

        while True:
            future: asyncio.Future[str] = loop.create_future()
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            tty.setcbreak(fd)

            loop.add_reader(fd, _make_key_press_handler(future))
            try:
                key = await future
            finally:
                loop.remove_reader(fd)
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

            if key == "enter":
                await bus.put(WakeWordDetected())
            elif key == "x":
                # Signal shutdown by putting a sentinel; orchestrator handles it.
                return
