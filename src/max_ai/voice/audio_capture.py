"""sounddevice → EventBus bridge.

AudioCapture opens a continuous InputStream and forwards each audio block
as an AudioFrame onto the event bus using call_soon_threadsafe, which is
safe to call from the sounddevice C callback thread.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any

import sounddevice as sd

from max_ai.voice.events import AudioFrame, EventBus

_SAMPLE_RATE = 16000
_CHANNELS = 1
_DTYPE = "int16"


class AudioCapture:
    """Continuously captures microphone audio and puts AudioFrame events on the bus."""

    def __init__(
        self,
        sample_rate: int = _SAMPLE_RATE,
        input_device: int | None = None,
    ) -> None:
        self._sample_rate = sample_rate
        self._input_device = input_device

    @contextlib.asynccontextmanager
    async def running(self, bus: EventBus) -> AsyncIterator[None]:
        """Start the sounddevice InputStream, yield, then stop on exit."""
        loop = asyncio.get_running_loop()

        def _sd_callback(
            indata: Any,
            frames: int,
            time: Any,
            status: Any,
        ) -> None:
            # Called from a C thread — never await here.
            loop.call_soon_threadsafe(bus.put_nowait, AudioFrame(data=indata.tobytes()))

        stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=_CHANNELS,
            dtype=_DTYPE,
            device=self._input_device,
            latency="low",
            callback=_sd_callback,
        )
        stream.start()
        try:
            yield
        finally:
            stream.stop()
            stream.close()
