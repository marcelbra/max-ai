"""Wake-word detection via Porcupine (pvporcupine, lazy import)."""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)


class WakeWordDetector:
    """Porcupine-based wake-word detector.

    Lazy-imports pvporcupine so the module loads even when the package is
    not installed (wake-word extras not present).
    """

    def __init__(self, access_key: str, keyword_path: str = "") -> None:
        import pvporcupine  # lazy: wake-word extra

        if keyword_path:
            self._porcupine = pvporcupine.create(
                access_key=access_key, keyword_paths=[keyword_path]
            )
        else:
            self._porcupine = pvporcupine.create(access_key=access_key, keywords=["porcupine"])
        self._buffer: bytes = b""

    def process(self, audio_frame: bytes) -> bool:
        """Buffer incoming bytes and call _porcupine.process once per full frame.

        Audio chunks from sounddevice may be smaller than frame_length, so we
        accumulate samples until we have exactly frame_length int16 values, then
        process all complete frames and return True if any triggered detection.
        """
        import struct

        self._buffer += audio_frame
        required_bytes = self.frame_length * 2
        detected = False
        while len(self._buffer) >= required_bytes:
            chunk = self._buffer[:required_bytes]
            self._buffer = self._buffer[required_bytes:]
            samples = list(struct.unpack(f"{self.frame_length}h", chunk))
            result: int = self._porcupine.process(samples)
            if result >= 0:
                _logger.debug("wake word detected")
                detected = True
        return detected

    @property
    def frame_length(self) -> int:
        """Number of int16 samples per frame (typically 512)."""
        return int(self._porcupine.frame_length)

    @property
    def sample_rate(self) -> int:
        """Sample rate required by Porcupine (always 16000)."""
        return int(self._porcupine.sample_rate)

    def close(self) -> None:
        self._porcupine.delete()
