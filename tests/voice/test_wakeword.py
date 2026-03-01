"""Tests for wake word detector."""

import struct
import sys
from unittest.mock import MagicMock


def _install_pvporcupine_stub() -> MagicMock:
    """Install a fake pvporcupine module in sys.modules and return the mock."""
    mock_porcupine = MagicMock()
    sys.modules["pvporcupine"] = mock_porcupine
    return mock_porcupine


def _make_handle(frame_length: int = 512, result: int = 0) -> MagicMock:
    handle = MagicMock()
    handle.frame_length = frame_length
    handle.process.return_value = result
    return handle


def test_process_returns_true_when_handle_result_is_zero() -> None:
    """process() returns True when Porcupine returns 0 (keyword index 0)."""
    mock_pv = _install_pvporcupine_stub()
    handle = _make_handle(result=0)
    mock_pv.create.return_value = handle

    # Force re-import to pick up the stub
    if "max_ai.voice.wakeword" in sys.modules:
        del sys.modules["max_ai.voice.wakeword"]
    from max_ai.voice.wakeword import WakeWordDetector

    detector = WakeWordDetector(access_key="key")
    samples = struct.pack(f"{512}h", *([0] * 512))
    assert detector.process(samples) is True


def test_process_returns_true_when_handle_result_is_positive() -> None:
    """process() returns True when Porcupine returns a positive index."""
    mock_pv = _install_pvporcupine_stub()
    handle = _make_handle(result=1)
    mock_pv.create.return_value = handle

    if "max_ai.voice.wakeword" in sys.modules:
        del sys.modules["max_ai.voice.wakeword"]
    from max_ai.voice.wakeword import WakeWordDetector

    detector = WakeWordDetector(access_key="key")
    samples = struct.pack(f"{512}h", *([0] * 512))
    assert detector.process(samples) is True


def test_process_returns_false_when_handle_result_is_negative() -> None:
    """process() returns False when Porcupine returns -1 (no detection)."""
    mock_pv = _install_pvporcupine_stub()
    handle = _make_handle(result=-1)
    mock_pv.create.return_value = handle

    if "max_ai.voice.wakeword" in sys.modules:
        del sys.modules["max_ai.voice.wakeword"]
    from max_ai.voice.wakeword import WakeWordDetector

    detector = WakeWordDetector(access_key="key")
    samples = struct.pack(f"{512}h", *([0] * 512))
    assert detector.process(samples) is False


def test_frame_length_delegates_to_handle() -> None:
    """frame_length property returns the handle's frame_length."""
    mock_pv = _install_pvporcupine_stub()
    handle = _make_handle(frame_length=256)
    mock_pv.create.return_value = handle

    if "max_ai.voice.wakeword" in sys.modules:
        del sys.modules["max_ai.voice.wakeword"]
    from max_ai.voice.wakeword import WakeWordDetector

    detector = WakeWordDetector(access_key="key")
    assert detector.frame_length == 256


def test_close_calls_handle_delete() -> None:
    """close() calls delete() on the Porcupine handle."""
    mock_pv = _install_pvporcupine_stub()
    handle = MagicMock()
    handle.frame_length = 512
    handle.process.return_value = -1
    mock_pv.create.return_value = handle

    if "max_ai.voice.wakeword" in sys.modules:
        del sys.modules["max_ai.voice.wakeword"]
    from max_ai.voice.wakeword import WakeWordDetector

    detector = WakeWordDetector(access_key="key")
    detector.close()
    handle.delete.assert_called_once()


def test_keyword_path_uses_keyword_paths_arg() -> None:
    """When keyword_path is set, create() is called with keyword_paths."""
    mock_pv = _install_pvporcupine_stub()
    handle = _make_handle()
    mock_pv.create.return_value = handle

    if "max_ai.voice.wakeword" in sys.modules:
        del sys.modules["max_ai.voice.wakeword"]
    from max_ai.voice.wakeword import WakeWordDetector

    WakeWordDetector(access_key="key", keyword_path="/path/to/keyword.ppn")
    mock_pv.create.assert_called_once_with(
        access_key="key",
        keyword_paths=["/path/to/keyword.ppn"],
    )


def test_no_keyword_path_uses_keywords_arg() -> None:
    """When keyword_path is empty, create() is called with keywords list."""
    mock_pv = _install_pvporcupine_stub()
    handle = _make_handle()
    mock_pv.create.return_value = handle

    if "max_ai.voice.wakeword" in sys.modules:
        del sys.modules["max_ai.voice.wakeword"]
    from max_ai.voice.wakeword import WakeWordDetector

    WakeWordDetector(access_key="key")
    mock_pv.create.assert_called_once_with(
        access_key="key",
        keywords=["hey google"],
    )
