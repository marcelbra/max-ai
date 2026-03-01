"""Tests for ToolRegistry."""

import pytest

from max_ai.tools.base import BaseTool, ToolDefinition
from max_ai.tools.registry import ToolRegistry


class SimpleTool(BaseTool):
    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="greet",
                description="Say hello",
                input_schema={
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            )
        ]

    async def execute(self, tool_name: str, tool_input: dict) -> str:
        return f"Hello, {tool_input['name']}!"


def test_registry_register_and_list() -> None:
    registry = ToolRegistry()
    registry.register(SimpleTool())
    api_tools = registry.get_api_tools()
    assert len(api_tools) == 1
    assert api_tools[0]["name"] == "greet"


def test_registry_has_tools() -> None:
    registry = ToolRegistry()
    assert not registry.has_tools()
    registry.register(SimpleTool())
    assert registry.has_tools()


@pytest.mark.asyncio
async def test_registry_execute() -> None:
    registry = ToolRegistry()
    registry.register(SimpleTool())
    result = await registry.execute("greet", {"name": "World"})
    assert result == "Hello, World!"


@pytest.mark.asyncio
async def test_registry_execute_unknown_tool() -> None:
    registry = ToolRegistry()
    result = await registry.execute("nonexistent", {})
    assert "unknown tool" in result
