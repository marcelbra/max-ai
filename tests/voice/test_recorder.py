"""Tests for voice recorder — input device routing, callbacks, and normalization."""

from typing import Any, cast
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


class _CapturingInputStream:
    """Fake sd.InputStream that records constructor kwargs and emits one silent chunk."""

    captured: dict[str, Any] = {}

    def __init__(self, **kwargs: Any) -> None:
        _CapturingInputStream.captured = kwargs

    def __enter__(self) -> "_CapturingInputStream":
        import sounddevice as sd

        callback = _CapturingInputStream.captured.get("callback")
        if callback is not None:
            chunk = np.zeros((160, 1), dtype=np.int16)
            callback(chunk, len(chunk), None, cast(sd.CallbackFlags, MagicMock()))
        return self

    def __exit__(self, *args: object) -> None:
        pass


@pytest.mark.parametrize("input_device", [None, 3, 0])
def test_record_until_enter_passes_device_to_input_stream(input_device: int | None) -> None:
    """record_until_enter must forward input_device to sd.InputStream."""
    with (
        patch("max_ai.voice.recorder.sd.InputStream", _CapturingInputStream),
        patch("max_ai.voice.recorder._read_key", return_value="enter"),
        patch("max_ai.voice.recorder.nr.reduce_noise", side_effect=lambda y, sr: y),
    ):
        from max_ai.voice.recorder import record_until_enter

        result = record_until_enter(input_device=input_device)

    assert _CapturingInputStream.captured.get("device") == input_device
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_record_until_enter_uses_low_latency() -> None:
    """sd.InputStream must be opened with latency='low' to minimise stream-start delay."""
    with (
        patch("max_ai.voice.recorder.sd.InputStream", _CapturingInputStream),
        patch("max_ai.voice.recorder._read_key", return_value="enter"),
        patch("max_ai.voice.recorder.nr.reduce_noise", side_effect=lambda y, sr: y),
    ):
        from max_ai.voice.recorder import record_until_enter

        record_until_enter()

    assert _CapturingInputStream.captured.get("latency") == "low"


def test_record_until_enter_calls_on_recording_started() -> None:
    """on_recording_started callback must be invoked after the stream opens."""
    called: list[bool] = []

    with (
        patch("max_ai.voice.recorder.sd.InputStream", _CapturingInputStream),
        patch("max_ai.voice.recorder._read_key", return_value="enter"),
        patch("max_ai.voice.recorder.nr.reduce_noise", side_effect=lambda y, sr: y),
    ):
        from max_ai.voice.recorder import record_until_enter

        record_until_enter(on_recording_started=lambda: called.append(True))

    assert called == [True]


def test_record_until_enter_raises_voice_exit_on_x() -> None:
    """Pressing 'x' must raise VoiceExit."""
    from max_ai.voice.recorder import VoiceExit, record_until_enter

    class _NoOpInputStream:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> "_NoOpInputStream":
            return self

        def __exit__(self, *args: object) -> None:
            pass

    with (
        patch("max_ai.voice.recorder.sd.InputStream", _NoOpInputStream),
        patch("max_ai.voice.recorder._read_key", return_value="x"),
    ):
        with pytest.raises(VoiceExit):
            record_until_enter()


def test_record_until_enter_calls_on_chunk() -> None:
    """on_chunk must be called with the raw PCM bytes of each audio block."""
    received: list[bytes] = []

    with (
        patch("max_ai.voice.recorder.sd.InputStream", _CapturingInputStream),
        patch("max_ai.voice.recorder._read_key", return_value="enter"),
        patch("max_ai.voice.recorder.nr.reduce_noise", side_effect=lambda y, sr: y),
    ):
        from max_ai.voice.recorder import record_until_enter

        record_until_enter(on_chunk=lambda audio_bytes: received.append(audio_bytes))

    assert len(received) >= 1
    assert all(isinstance(chunk, bytes) for chunk in received)
    assert len(received[0]) > 0


def test_normalize_boosts_quiet_audio() -> None:
    """_normalize must scale quiet audio up toward the target peak."""
    from max_ai.voice.recorder import _normalize

    quiet = np.full((1000, 1), 1000, dtype=np.int16)  # peak ~3% of full scale
    result = _normalize(quiet)
    peak_after = np.abs(result).max()
    assert peak_after > np.abs(quiet).max()


def test_normalize_caps_gain() -> None:
    """_normalize must not apply more than _NORMALIZE_MAX_GAIN× amplification."""
    from max_ai.voice.recorder import _NORMALIZE_MAX_GAIN, _normalize

    very_quiet = np.full((1000, 1), 10, dtype=np.int16)
    result = _normalize(very_quiet)
    expected_max = min(10 * _NORMALIZE_MAX_GAIN, 32767)
    assert np.abs(result).max() <= expected_max + 1  # +1 for rounding


def test_normalize_silent_audio_unchanged() -> None:
    """_normalize must return zeros unchanged (avoid divide-by-zero)."""
    from max_ai.voice.recorder import _normalize

    silent = np.zeros((500, 1), dtype=np.int16)
    result = _normalize(silent)
    assert np.all(result == 0)
