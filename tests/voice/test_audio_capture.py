"""Tests for AudioCapture — verifies AudioFrame is put on the bus from the callback."""

import asyncio
from typing import Any, cast
from unittest.mock import MagicMock, patch

import numpy as np

from max_ai.voice.events import AudioFrame, EventBus


class _FakeInputStream:
    """Fake sd.InputStream that fires the callback once on start()."""

    def __init__(self, **kwargs: Any) -> None:
        self._callback = kwargs.get("callback")

    def start(self) -> None:
        if self._callback is not None:
            chunk = np.zeros((512, 1), dtype=np.int16)
            self._callback(chunk, 512, None, cast(Any, MagicMock()))

    def stop(self) -> None:
        pass

    def close(self) -> None:
        pass


async def test_audio_capture_puts_audio_frame_on_bus() -> None:
    """AudioCapture must put at least one AudioFrame on the bus when audio arrives."""
    bus: EventBus = asyncio.Queue()

    with patch("max_ai.voice.audio_capture.sd.InputStream", _FakeInputStream):
        from max_ai.voice.audio_capture import AudioCapture

        capture = AudioCapture(sample_rate=16000, input_device=None)
        async with capture.running(bus):
            pass
        # call_soon_threadsafe schedules on the next event loop tick — flush it.
        await asyncio.sleep(0)

    assert not bus.empty()
    frame = bus.get_nowait()
    assert isinstance(frame, AudioFrame)
    assert isinstance(frame.data, bytes)
    assert len(frame.data) > 0


async def test_audio_capture_forwards_device_to_input_stream() -> None:
    """AudioCapture must pass input_device to sd.InputStream."""
    bus: EventBus = asyncio.Queue()
    captured_kwargs: dict[str, Any] = {}

    class _RecordingInputStream(_FakeInputStream):
        def __init__(self, **kwargs: Any) -> None:
            captured_kwargs.update(kwargs)
            super().__init__(**kwargs)

    with patch("max_ai.voice.audio_capture.sd.InputStream", _RecordingInputStream):
        from max_ai.voice.audio_capture import AudioCapture

        capture = AudioCapture(sample_rate=16000, input_device=3)
        async with capture.running(bus):
            pass

    assert captured_kwargs.get("device") == 3


async def test_audio_capture_uses_low_latency() -> None:
    """AudioCapture must open the stream with latency='low'."""
    bus: EventBus = asyncio.Queue()
    captured_kwargs: dict[str, Any] = {}

    class _RecordingInputStream(_FakeInputStream):
        def __init__(self, **kwargs: Any) -> None:
            captured_kwargs.update(kwargs)
            super().__init__(**kwargs)

    with patch("max_ai.voice.audio_capture.sd.InputStream", _RecordingInputStream):
        from max_ai.voice.audio_capture import AudioCapture

        capture = AudioCapture()
        async with capture.running(bus):
            pass

    assert captured_kwargs.get("latency") == "low"
