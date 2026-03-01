"""Voice test fixtures — stubs out hardware deps unavailable in CI."""

import sys
from unittest.mock import MagicMock

# sounddevice requires PortAudio, a system library absent in CI.  Inject a
# MagicMock stub so that recorder.py's module-level ``import sounddevice as sd``
# succeeds without raising OSError.  Individual tests then patch specific
# attributes (e.g. ``max_ai.voice.recorder.sd.InputStream``) as usual.
if "sounddevice" not in sys.modules:
    sys.modules["sounddevice"] = MagicMock()
