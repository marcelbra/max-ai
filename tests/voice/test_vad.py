"""Tests for SilenceVAD — silence detection logic."""

import struct

from max_ai.voice.vad import SilenceVAD


def _make_frame(amplitude: int, num_samples: int = 512) -> bytes:
    """Return a PCM frame with all samples at the given amplitude."""
    return struct.pack(f"{num_samples}h", *([amplitude] * num_samples))


def test_vad_returns_false_below_threshold() -> None:
    """update() returns False when accumulated silence is below the threshold."""
    vad = SilenceVAD(silence_threshold_ms=1800)
    # One silent frame is ~30 ms — well below 1800 ms
    frame = _make_frame(amplitude=0)
    result = vad.update(frame)
    assert result is False


def test_vad_returns_true_after_threshold_reached() -> None:
    """update() returns True once silence duration reaches the threshold."""
    vad = SilenceVAD(silence_threshold_ms=30)  # exactly one frame
    frame = _make_frame(amplitude=0)
    result = vad.update(frame)
    assert result is True


def test_vad_resets_counter_on_loud_frame() -> None:
    """A loud frame resets the silence counter."""
    vad = SilenceVAD(silence_threshold_ms=30)
    silent_frame = _make_frame(amplitude=0)
    loud_frame = _make_frame(amplitude=10000)

    vad.update(silent_frame)  # would fire after one frame at threshold=30ms
    vad.update(loud_frame)  # should reset counter
    result = vad.update(silent_frame)  # back to one frame of silence
    # counter was reset so we need to accumulate again from zero
    # threshold=30ms, one frame=30ms → should be True
    assert result is True


def test_vad_reset_clears_counter() -> None:
    """reset() clears the silence counter so the next frame starts fresh."""
    vad = SilenceVAD(silence_threshold_ms=30)
    silent_frame = _make_frame(amplitude=0)

    vad.update(silent_frame)  # fires immediately at 30ms threshold
    vad.reset()  # clear counter
    result = vad.update(silent_frame)  # should fire again after one frame
    assert result is True


def test_vad_empty_frame_returns_false() -> None:
    """An empty bytes frame must not raise and must return False."""
    vad = SilenceVAD(silence_threshold_ms=1800)
    result = vad.update(b"")
    assert result is False
