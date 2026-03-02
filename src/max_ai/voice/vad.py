"""Voice Activity Detection — silence-based utterance-end fallback.

Tracks consecutive silent frames and fires when the configured silence
duration threshold is reached.  Used as a fallback when Deepgram's
UtteranceEnd does not arrive in time.

Lazy-imports torch so the module loads even when the wake-word extra is
not installed.
"""

from __future__ import annotations

_FRAME_DURATION_MS = 30  # ms per audio frame at 16 kHz / 512 samples


class SilenceVAD:
    """Frame-level silence detector.

    Call ``update(audio_frame)`` for each incoming AudioFrame.
    ``update`` returns True when accumulated silence exceeds the threshold.
    Call ``reset()`` after an utterance to clear the counter.
    """

    def __init__(self, silence_threshold_ms: int = 1800) -> None:
        self._silence_threshold_ms = silence_threshold_ms
        self._silent_frame_count = 0

    def update(self, audio_frame: bytes) -> bool:
        """Return True when silence duration has exceeded the threshold."""
        import struct

        import numpy as np

        samples_count = len(audio_frame) // 2
        if samples_count == 0:
            return False
        samples = struct.unpack(f"{samples_count}h", audio_frame)
        rms = float(np.sqrt(np.mean(np.array(samples, dtype=np.float32) ** 2)))
        is_silent = rms < 200.0  # rough energy threshold for 16-bit audio

        if is_silent:
            self._silent_frame_count += 1
        else:
            self._silent_frame_count = 0

        silent_ms = self._silent_frame_count * _FRAME_DURATION_MS
        return silent_ms >= self._silence_threshold_ms

    def reset(self) -> None:
        """Clear the silence counter (call at utterance start)."""
        self._silent_frame_count = 0
