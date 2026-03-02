"""Tests for WakeWordDetector and KeyboardWakeWordDetector."""

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
