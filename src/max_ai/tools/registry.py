"""Tool registration and dispatch."""

from typing import Any

from max_ai.tools.base import BaseTool, ToolDefinition


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._definitions: dict[str, ToolDefinition] = {}

    def register(self, tool: BaseTool) -> None:
        """Register all tools from a BaseTool instance."""
        for definition in tool.definitions():
            self._tools[definition.name] = tool
            self._definitions[definition.name] = definition

    def get_api_tools(self) -> list[dict[str, Any]]:
        """Return all tool definitions in Anthropic API format."""
        return [definition.to_api_dict() for definition in self._definitions.values()]

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Route a tool call to the appropriate handler."""
        if tool_name not in self._tools:
            return f"Error: unknown tool '{tool_name}'"
        return await self._tools[tool_name].execute(tool_name, tool_input)

    def has_tools(self) -> bool:
        return bool(self._tools)
