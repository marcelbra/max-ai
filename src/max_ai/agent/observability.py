"""LangWatch observability wrapper for agent tracing."""

import logging
import warnings
from typing import Any

from max_ai.core.config import get_settings

# Suppress verbose LangWatch logging
logging.getLogger("langwatch").setLevel(logging.ERROR)
logging.getLogger("langwatch.utils.initialization").setLevel(logging.ERROR)
logging.getLogger("langwatch.client").setLevel(logging.ERROR)

# Suppress LangWatch warnings
warnings.filterwarnings("ignore", module="langwatch")

# Try to import langwatch, but make it optional
try:
    import langwatch

    LANGWATCH_AVAILABLE = True
except ImportError:
    LANGWATCH_AVAILABLE = False
    langwatch = None

_initialized = False


def init_langwatch() -> bool:
    """Initialize LangWatch if API key is configured."""
    global _initialized

    if _initialized:
        return True

    if not LANGWATCH_AVAILABLE:
        return False

    settings = get_settings()
    if not settings.langwatch_api_key:
        return False

    # Properly initialize LangWatch with setup()
    langwatch.setup(
        api_key=settings.langwatch_api_key,
        debug=False,
    )
    _initialized = True
    return True


class LangWatchTrace:
    """Context manager for creating LangWatch traces."""

    def __init__(self, name: str = "max-agent-chat"):
        self.name = name
        self._trace = None
        self._enabled = False

    def __enter__(self) -> "LangWatchTrace":
        if LANGWATCH_AVAILABLE:
            settings = get_settings()
            if settings.langwatch_api_key:
                init_langwatch()
                self._trace = langwatch.trace(name=self.name)
                self._trace.__enter__()
                self._enabled = True
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._trace and self._enabled:
            self._trace.__exit__(exc_type, exc_val, exc_tb)

    async def __aenter__(self) -> "LangWatchTrace":
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)
