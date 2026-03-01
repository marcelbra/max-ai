"""Voice activity detection using Silero VAD."""

from typing import Any


class VoiceActivityDetector:
    """Detects speech/silence using Silero VAD and tracks consecutive silence duration."""

    def __init__(self, silence_threshold_ms: int = 1800, sample_rate: int = 16000) -> None:
        self._silence_threshold_ms = silence_threshold_ms
        self._sample_rate = sample_rate
        self._model: Any = None
        self._get_speech_timestamps: Any = None
        self._consecutive_silence_ms: float = 0.0

    def _load_model(self) -> None:
        """Lazy-load Silero VAD from torch hub."""
        import torch  # lazy: optional wake-word extra

        hub: Any = torch.hub
        model, utils = hub.load("snakers4/silero-vad", "silero_vad", trust_repo=True)
        self._model = model
        self._get_speech_timestamps = utils[0]

    def is_speech(self, audio_chunk: bytes) -> bool:
        """Return True if the audio chunk contains speech."""
        import torch  # lazy: optional wake-word extra

        if self._model is None:
            self._load_model()

        assert self._model is not None
        sample_count = len(audio_chunk) // 2
        audio_array = torch.frombuffer(audio_chunk, dtype=torch.int16).float() / 32768.0
        audio_array = audio_array[:sample_count]

        with torch.no_grad():
            confidence = self._model(audio_array, self._sample_rate).item()
        return bool(confidence > 0.5)

    def update(self, audio_chunk: bytes) -> bool:
        """Update silence counter and return True when silence exceeds threshold."""
        chunk_duration_ms = len(audio_chunk) / 2 / self._sample_rate * 1000.0
        if self.is_speech(audio_chunk):
            self._consecutive_silence_ms = 0.0
        else:
            self._consecutive_silence_ms += chunk_duration_ms
        return self._consecutive_silence_ms >= self._silence_threshold_ms

    def reset(self) -> None:
        """Reset the consecutive silence counter and the model's internal state."""
        self._consecutive_silence_ms = 0.0
        if self._model is not None:
            self._model.reset_states()
