"""Tests for BaseWebSearchTool and AnthropicWebSearch."""

import pytest

from max_ai.tools.search import AnthropicWebSearch, BaseWebSearchTool


def test_anthropic_web_search_tool_name() -> None:
    tool = AnthropicWebSearch()
    assert tool.tool_name == "web_search"


def test_anthropic_web_search_is_server_tool() -> None:
    tool = AnthropicWebSearch()
    assert tool.is_server_tool is True


def test_anthropic_web_search_default_max_uses() -> None:
    tool = AnthropicWebSearch()
    definition = tool.api_definition()
    assert definition["max_uses"] == 5


def test_anthropic_web_search_api_definition() -> None:
    tool = AnthropicWebSearch(max_uses=3)
    definition = tool.api_definition()
    assert definition == {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 3,
    }


@pytest.mark.asyncio
async def test_anthropic_web_search_execute_raises() -> None:
    tool = AnthropicWebSearch()
    with pytest.raises(NotImplementedError):
        await tool.execute({})


def test_base_web_search_tool_is_abstract() -> None:
    with pytest.raises(TypeError):
        BaseWebSearchTool()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_local_web_search_tool_can_be_implemented() -> None:
    """A concrete local (non-server) subclass can override execute()."""

    class LocalSearch(BaseWebSearchTool):
        @property
        def tool_name(self) -> str:
            return "local_search"

        @property
        def is_server_tool(self) -> bool:
            return False

        def api_definition(self) -> dict:  # type: ignore[type-arg]
            return {"name": self.tool_name, "input_schema": {}}

        async def execute(self, tool_input: dict) -> str:  # type: ignore[type-arg]
            return f"results for: {tool_input.get('query', '')}"

    tool = LocalSearch()
    result = await tool.execute({"query": "hello"})
    assert result == "results for: hello"
    assert not tool.is_server_tool
    assert tool.tool_name == "local_search"
