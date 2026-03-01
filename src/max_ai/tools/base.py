"""Abstract tool interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolDefinition:
    """Represents a single tool in Anthropic API format."""

    name: str
    description: str
    input_schema: dict[str, Any]

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class BaseTool(ABC):
    @abstractmethod
    def definitions(self) -> list[ToolDefinition]:
        """Return tool definitions for the API call."""
        ...

    @abstractmethod
    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool call and return the result as a string."""
        ...
