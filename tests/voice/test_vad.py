"""Tests for Voice Activity Detector."""

import struct
import sys
from typing import Any
from unittest.mock import MagicMock


def _install_torch_stub(speech_confidence: float = 0.0) -> MagicMock:
    """Install a fake torch module and configure Silero VAD confidence."""
    mock_torch = MagicMock()

    # Make frombuffer return a mock tensor
    mock_tensor = MagicMock()
    mock_torch.frombuffer.return_value = mock_tensor
    mock_tensor.float.return_value = mock_tensor
    mock_tensor.__truediv__ = lambda self, other: mock_tensor
    mock_tensor.__getitem__ = lambda self, other: mock_tensor

    # Mock no_grad context manager
    mock_torch.no_grad.return_value.__enter__ = lambda s: None
    mock_torch.no_grad.return_value.__exit__ = lambda s, *a: None

    # Mock int16 dtype
    mock_torch.int16 = "int16"

    # Mock the VAD model: calling model(audio, sample_rate).item() returns confidence
    mock_model = MagicMock()
    mock_model_output = MagicMock()
    mock_model_output.item.return_value = speech_confidence
    mock_model.return_value = mock_model_output

    # torch.hub.load returns (model, utils)
    mock_get_speech_timestamps = MagicMock()
    mock_torch.hub.load.return_value = (mock_model, (mock_get_speech_timestamps,))

    sys.modules["torch"] = mock_torch
    return mock_torch


def _silent_chunk(sample_count: int = 160) -> bytes:
    return struct.pack(f"{sample_count}h", *([0] * sample_count))


def _force_reimport() -> Any:
    """Remove cached module so next import picks up mocked torch."""
    for key in list(sys.modules.keys()):
        if "max_ai.voice.vad" in key:
            del sys.modules[key]


def test_update_returns_false_below_silence_threshold() -> None:
    """update() returns False when accumulated silence is below threshold."""
    _install_torch_stub(speech_confidence=0.0)
    _force_reimport()
    from max_ai.voice.vad import VoiceActivityDetector

    vad = VoiceActivityDetector(silence_threshold_ms=1800, sample_rate=16000)
    # One chunk of 160 samples at 16000 Hz = 10ms — far below 1800ms threshold
    chunk = _silent_chunk(160)
    result = vad.update(chunk)
    assert result is False


def test_update_returns_true_after_silence_threshold_exceeded() -> None:
    """update() returns True once accumulated silence exceeds threshold."""
    _install_torch_stub(speech_confidence=0.0)
    _force_reimport()
    from max_ai.voice.vad import VoiceActivityDetector

    # 100ms threshold, chunks of 160 samples = 10ms each → need 10+ chunks
    vad = VoiceActivityDetector(silence_threshold_ms=100, sample_rate=16000)
    chunk = _silent_chunk(160)
    result = False
    for _ in range(12):
        result = vad.update(chunk)
    assert result is True


def test_reset_clears_accumulated_silence() -> None:
    """reset() clears the silence counter so next update returns False."""
    _install_torch_stub(speech_confidence=0.0)
    _force_reimport()
    from max_ai.voice.vad import VoiceActivityDetector

    vad = VoiceActivityDetector(silence_threshold_ms=50, sample_rate=16000)
    chunk = _silent_chunk(160)
    # Accumulate enough silence to exceed 50ms threshold (each chunk = 10ms)
    for _ in range(6):
        vad.update(chunk)

    vad.reset()
    # After reset a single chunk (10ms) should not exceed 50ms threshold
    result = vad.update(chunk)
    assert result is False


def test_reset_calls_model_reset_states() -> None:
    """reset() calls reset_states() on the Silero model to clear LSTM hidden state."""
    _install_torch_stub(speech_confidence=0.0)
    _force_reimport()
    from max_ai.voice.vad import VoiceActivityDetector

    vad = VoiceActivityDetector(silence_threshold_ms=50, sample_rate=16000)
    chunk = _silent_chunk(160)
    vad.update(chunk)  # forces model to load

    assert vad._model is not None
    vad._model.reset_states = MagicMock()
    vad.reset()

    vad._model.reset_states.assert_called_once()


def test_speech_resets_silence_counter() -> None:
    """Detecting speech resets the silence counter."""
    # Start silent, then speech detected, then silent again
    _install_torch_stub(speech_confidence=0.0)
    _force_reimport()
    from max_ai.voice.vad import VoiceActivityDetector

    vad = VoiceActivityDetector(silence_threshold_ms=50, sample_rate=16000)
    chunk = _silent_chunk(160)

    # Accumulate some silence (not enough to trigger)
    for _ in range(3):
        vad.update(chunk)

    # Switch to high speech confidence to reset counter
    vad._model = MagicMock()
    speech_output = MagicMock()
    speech_output.item.return_value = 0.9
    vad._model.return_value = speech_output

    vad.update(chunk)  # detected as speech → resets counter

    # Now silence again — should need full threshold from zero
    silence_output = MagicMock()
    silence_output.item.return_value = 0.0
    vad._model.return_value = silence_output

    # One chunk (10ms) should not exceed 50ms threshold
    result = vad.update(chunk)
    assert result is False
