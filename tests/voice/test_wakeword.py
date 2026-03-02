"""Tests for WakeWordDetector."""

import struct
import sys
from typing import Any
from unittest.mock import MagicMock, patch


def _make_fake_porcupine(detect_result: int = 0) -> MagicMock:
    """Return a fake pvporcupine.create() return value."""
    porcupine = MagicMock()
    porcupine.frame_length = 512
    porcupine.sample_rate = 16000
    porcupine.process.return_value = detect_result
    return porcupine


def _make_silent_frame(num_samples: int = 512) -> bytes:
    """Return a frame of num_samples zero int16 samples."""
    return struct.pack(f"{num_samples}h", *([0] * num_samples))


def test_wake_word_detector_process_returns_true_on_detection() -> None:
    """process() returns True when Porcupine returns a non-negative index."""
    fake_porcupine = _make_fake_porcupine(detect_result=0)
    fake_pvporcupine = MagicMock()
    fake_pvporcupine.create.return_value = fake_porcupine

    with patch.dict(sys.modules, {"pvporcupine": fake_pvporcupine}):
        from max_ai.voice.wakeword import WakeWordDetector

        detector = WakeWordDetector(access_key="key")
        result = detector.process(_make_silent_frame())

    assert result is True


def test_wake_word_detector_process_returns_false_on_no_detection() -> None:
    """process() returns False when Porcupine returns -1 (no detection)."""
    fake_porcupine = _make_fake_porcupine(detect_result=-1)
    fake_pvporcupine = MagicMock()
    fake_pvporcupine.create.return_value = fake_porcupine

    with patch.dict(sys.modules, {"pvporcupine": fake_pvporcupine}):
        from max_ai.voice.wakeword import WakeWordDetector

        detector = WakeWordDetector(access_key="key")
        result = detector.process(_make_silent_frame())

    assert result is False


def test_wake_word_detector_frame_length_property() -> None:
    fake_porcupine = _make_fake_porcupine()
    fake_pvporcupine = MagicMock()
    fake_pvporcupine.create.return_value = fake_porcupine

    with patch.dict(sys.modules, {"pvporcupine": fake_pvporcupine}):
        from max_ai.voice.wakeword import WakeWordDetector

        detector = WakeWordDetector(access_key="key")
        assert detector.frame_length == 512


def test_wake_word_detector_sample_rate_property() -> None:
    fake_porcupine = _make_fake_porcupine()
    fake_pvporcupine = MagicMock()
    fake_pvporcupine.create.return_value = fake_porcupine

    with patch.dict(sys.modules, {"pvporcupine": fake_pvporcupine}):
        from max_ai.voice.wakeword import WakeWordDetector

        detector = WakeWordDetector(access_key="key")
        assert detector.sample_rate == 16000


def test_wake_word_detector_uses_keyword_path_when_provided() -> None:
    fake_porcupine = _make_fake_porcupine()
    fake_pvporcupine = MagicMock()
    fake_pvporcupine.create.return_value = fake_porcupine

    with patch.dict(sys.modules, {"pvporcupine": fake_pvporcupine}):
        from max_ai.voice.wakeword import WakeWordDetector

        WakeWordDetector(access_key="key", keyword_path="/path/to/keyword.ppn")

    call_kwargs: dict[str, Any] = fake_pvporcupine.create.call_args.kwargs
    assert call_kwargs.get("keyword_paths") == ["/path/to/keyword.ppn"]
    assert "keywords" not in call_kwargs


def test_wake_word_detector_uses_built_in_keyword_when_no_path() -> None:
    fake_porcupine = _make_fake_porcupine()
    fake_pvporcupine = MagicMock()
    fake_pvporcupine.create.return_value = fake_porcupine

    with patch.dict(sys.modules, {"pvporcupine": fake_pvporcupine}):
        from max_ai.voice.wakeword import WakeWordDetector

        WakeWordDetector(access_key="key")

    call_kwargs = fake_pvporcupine.create.call_args.kwargs
    assert "keywords" in call_kwargs
    assert "keyword_paths" not in call_kwargs


def test_wake_word_detector_close_calls_delete() -> None:
    fake_porcupine = _make_fake_porcupine()
    fake_pvporcupine = MagicMock()
    fake_pvporcupine.create.return_value = fake_porcupine

    with patch.dict(sys.modules, {"pvporcupine": fake_pvporcupine}):
        from max_ai.voice.wakeword import WakeWordDetector

        detector = WakeWordDetector(access_key="key")
        detector.close()

    fake_porcupine.delete.assert_called_once()


def test_wake_word_detector_buffers_small_chunks_until_full_frame() -> None:
    """process() buffers sub-frame chunks and only calls porcupine with full frames.

    Regression: sounddevice with latency="low" delivers chunks as small as 15
    samples, but Porcupine requires exactly frame_length (512) samples.
    """
    fake_porcupine = _make_fake_porcupine(detect_result=-1)
    fake_pvporcupine = MagicMock()
    fake_pvporcupine.create.return_value = fake_porcupine

    chunk_size = 15
    chunk = _make_silent_frame(chunk_size)
    full_frame_size = 512

    with patch.dict(sys.modules, {"pvporcupine": fake_pvporcupine}):
        from max_ai.voice.wakeword import WakeWordDetector

        detector = WakeWordDetector(access_key="key")

        # Feed chunks until just before a full frame is complete.
        chunks_per_frame = full_frame_size // chunk_size  # 34 chunks = 510 samples
        for _ in range(chunks_per_frame):
            result = detector.process(chunk)
            assert result is False

        # Porcupine must not have been called yet (only 510 of 512 samples buffered).
        fake_porcupine.process.assert_not_called()

        # Feed the remaining 2 samples to complete the first frame.
        remaining = _make_silent_frame(full_frame_size - chunk_size * chunks_per_frame)
        result = detector.process(remaining)

    assert result is False
    fake_porcupine.process.assert_called_once()
    called_samples = fake_porcupine.process.call_args[0][0]
    assert len(called_samples) == full_frame_size


def test_wake_word_detector_detects_across_small_chunks() -> None:
    """process() returns True when detection occurs after buffering sub-frame chunks."""
    fake_porcupine = _make_fake_porcupine(detect_result=0)  # detection on every call
    fake_pvporcupine = MagicMock()
    fake_pvporcupine.create.return_value = fake_porcupine

    full_frame = _make_silent_frame(512)

    with patch.dict(sys.modules, {"pvporcupine": fake_pvporcupine}):
        from max_ai.voice.wakeword import WakeWordDetector

        detector = WakeWordDetector(access_key="key")
        # Feed 256 samples twice to form one complete frame.
        result_first_half = detector.process(_make_silent_frame(256))
        result_second_half = detector.process(_make_silent_frame(256))

    assert result_first_half is False  # frame not complete yet
    assert result_second_half is True  # frame complete, detection triggered
    del full_frame
