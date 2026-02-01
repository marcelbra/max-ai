"""LangWatch observability wrapper for agent tracing."""

import functools
from typing import Any, Callable, TypeVar

from max_ai.core.config import get_settings

F = TypeVar("F", bound=Callable[..., Any])

# Try to import langwatch, but make it optional
try:
    import langwatch

    LANGWATCH_AVAILABLE = True
except ImportError:
    LANGWATCH_AVAILABLE = False
    langwatch = None


def init_langwatch() -> bool:
    """Initialize LangWatch if API key is configured."""
    if not LANGWATCH_AVAILABLE:
        return False

    settings = get_settings()
    if not settings.langwatch_api_key:
        return False

    langwatch.api_key = settings.langwatch_api_key
    return True


def trace_agent(name: str = "max-agent") -> Callable[[F], F]:
    """
    Decorator to trace agent runs with LangWatch.

    Usage:
        @trace_agent("my-agent")
        async def run_agent(...):
            ...
    """

    def decorator(func: F) -> F:
        if not LANGWATCH_AVAILABLE:
            return func

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            settings = get_settings()
            if not settings.langwatch_api_key:
                return await func(*args, **kwargs)

            with langwatch.trace(name=name):
                return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            settings = get_settings()
            if not settings.langwatch_api_key:
                return func(*args, **kwargs)

            with langwatch.trace(name=name):
                return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


class LangWatchSpan:
    """Context manager for creating LangWatch spans."""

    def __init__(self, name: str, span_type: str = "chain"):
        self.name = name
        self.span_type = span_type
        self._span = None

    def __enter__(self) -> "LangWatchSpan":
        if LANGWATCH_AVAILABLE:
            settings = get_settings()
            if settings.langwatch_api_key:
                self._span = langwatch.span(name=self.name, type=self.span_type)
                self._span.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._span:
            self._span.__exit__(exc_type, exc_val, exc_tb)

    async def __aenter__(self) -> "LangWatchSpan":
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)
