"""Wake word detection using Porcupine."""


class WakeWordDetector:
    """Detects a wake word in raw int16 PCM audio using Porcupine."""

    def __init__(self, access_key: str, keyword_path: str = "") -> None:
        import pvporcupine  # lazy: optional wake-word extra

        if keyword_path:
            self._handle = pvporcupine.create(
                access_key=access_key,
                keyword_paths=[keyword_path],
            )
        else:
            self._handle = pvporcupine.create(
                access_key=access_key,
                keywords=["hey google"],
            )

    def process(self, audio_chunk: bytes) -> bool:
        """Return True if the wake word was detected in this frame."""
        import struct

        sample_count = len(audio_chunk) // 2
        samples = list(struct.unpack_from(f"{sample_count}h", audio_chunk))
        result = self._handle.process(samples)
        return bool(result >= 0)

    @property
    def frame_length(self) -> int:
        """Number of int16 samples Porcupine expects per frame."""
        return int(self._handle.frame_length)

    @property
    def sample_rate(self) -> int:
        """Sample rate required by Porcupine (always 16000 Hz)."""
        return 16000

    def close(self) -> None:
        """Release Porcupine resources."""
        self._handle.delete()
