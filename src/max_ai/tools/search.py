"""Web search tool abstraction.

Two provider types are supported:

- Server tools (e.g. Anthropic built-in): the API executes the search on its
  servers; ``stop_reason`` is ``pause_turn`` and ``execute()`` is never called.
- Local tools (e.g. Tavily, DuckDuckGo): the agent calls ``execute()`` locally;
  ``stop_reason`` is ``tool_use``.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseWebSearchTool(ABC):
    """Abstract base for web search providers."""

    @property
    @abstractmethod
    def tool_name(self) -> str:
        """The name the Anthropic API will use when invoking this tool."""
        ...

    @abstractmethod
    def api_definition(self) -> dict[str, Any]:
        """Return the dict to include in the ``tools`` list of the API call."""
        ...

    async def execute(self, tool_input: dict[str, Any]) -> str:
        """Execute a local search.  Override for non-server providers."""
        raise NotImplementedError(
            f"{type(self).__name__} is a server-side tool and cannot be executed locally."
        )


class AnthropicWebSearch(BaseWebSearchTool):
    """Anthropic's built-in server-side web search tool."""

    def __init__(self, max_uses: int = 5) -> None:
        self._max_uses = max_uses

    @property
    def tool_name(self) -> str:
        return "web_search"

    def api_definition(self) -> dict[str, Any]:
        return {
            "type": "web_search_20250305",
            "name": self.tool_name,
            "max_uses": self._max_uses,
        }
