"""LangWatch tracing integration."""

import logging
from collections.abc import AsyncIterator

from max_ai.config import settings

logger = logging.getLogger(__name__)

_langwatch_enabled = False


def setup_langwatch() -> None:
    """Initialize LangWatch if an API key is configured."""
    global _langwatch_enabled
    if not settings.langwatch_api_key:
        return
    try:
        import langwatch

        langwatch.setup(api_key=settings.langwatch_api_key)
        _langwatch_enabled = True
        logger.debug("LangWatch tracing enabled.")
    except ImportError:
        logger.warning("langwatch package not installed — tracing disabled.")
    except Exception as e:
        logger.warning(f"LangWatch setup failed: {e}")


async def trace_turn(
    gen: AsyncIterator[str],
    user_input: str = "",
    thread_id: str | None = None,
    system: str = "",
) -> AsyncIterator[str]:
    """
    Wrap an agent turn with LangWatch tracing if enabled.
    Falls back to a passthrough when LangWatch is not configured.
    """
    if not _langwatch_enabled:
        async for chunk in gen:
            yield chunk
        return

    try:
        import langwatch

        with langwatch.trace() as trace:
            metadata: dict[str, str] = {}
            if thread_id:
                metadata["thread_id"] = thread_id
            if system:
                metadata["system"] = system
            trace.update(input=user_input, metadata=metadata or None)
            chunks: list[str] = []
            async for chunk in gen:
                chunks.append(chunk)
                yield chunk
            trace.update(output="".join(chunks))
    except Exception as e:
        logger.warning(f"LangWatch trace error: {e}")
        async for chunk in gen:
            yield chunk
