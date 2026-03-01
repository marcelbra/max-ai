"""Tests for BaseTool and ToolDefinition."""

from max_ai.tools.base import ToolDefinition


def test_tool_definition_to_api_dict() -> None:
    defn = ToolDefinition(
        name="test",
        description="A test tool",
        input_schema={"type": "object", "properties": {}},
    )
    d = defn.to_api_dict()
    assert d["name"] == "test"
    assert d["description"] == "A test tool"
    assert "input_schema" in d
