"""Tests for the Agent class."""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import anthropic
import pytest
from anthropic.types import Message, TextBlock, ToolResultBlockParam, ToolUseBlock

from max_ai.agent import Agent
from max_ai.tools.registry import ToolRegistry
from max_ai.tools.search import BaseWebSearchTool


@pytest.mark.asyncio
async def test_agent_end_turn(
    mock_anthropic_client: anthropic.AsyncAnthropic, empty_registry: ToolRegistry
) -> None:
    """Agent yields text when stop_reason is end_turn."""
    response = cast(Message, MagicMock(spec=Message))
    response.stop_reason = "end_turn"
    response.content = [cast(TextBlock, MagicMock(spec=TextBlock, type="text", text="Hello!"))]
    mock_anthropic_client.messages.create = AsyncMock(return_value=response)  # type: ignore[method-assign]

    agent = Agent(mock_anthropic_client, empty_registry, "system")
    chunks = []
    async for chunk in agent.run("hi"):
        chunks.append(chunk)

    assert chunks == ["Hello!"]
    assert len(agent.messages) == 2
    assert agent.messages[0]["role"] == "user"
    assert agent.messages[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_agent_max_tokens(
    mock_anthropic_client: anthropic.AsyncAnthropic, empty_registry: ToolRegistry
) -> None:
    """Agent yields truncation notice on max_tokens."""
    response = cast(Message, MagicMock(spec=Message))
    response.stop_reason = "max_tokens"
    response.content = []
    mock_anthropic_client.messages.create = AsyncMock(return_value=response)  # type: ignore[method-assign]

    agent = Agent(mock_anthropic_client, empty_registry, "system")
    chunks = []
    async for chunk in agent.run("hi"):
        chunks.append(chunk)

    assert any("max_tokens" in c for c in chunks)


@pytest.mark.asyncio
async def test_agent_tool_use_then_end_turn(
    mock_anthropic_client: anthropic.AsyncAnthropic,
) -> None:
    """Agent executes tools then yields final response."""
    from max_ai.tools.base import BaseTool, ToolDefinition

    class EchoTool(BaseTool):
        def definitions(self) -> list[ToolDefinition]:
            return [
                ToolDefinition(
                    name="echo",
                    description="Echo input",
                    input_schema={
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                    },
                )
            ]

        async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
            return f"echoed: {tool_input['text']}"

    registry = ToolRegistry()
    registry.register(EchoTool())

    tool_block = cast(ToolUseBlock, MagicMock(spec=ToolUseBlock))
    tool_block.type = "tool_use"
    tool_block.name = "echo"
    tool_block.input = {"text": "hello"}
    tool_block.id = "tool_1"

    text_block = cast(TextBlock, MagicMock(spec=TextBlock))
    text_block.type = "text"
    text_block.text = "Done!"

    tool_response = cast(Message, MagicMock(spec=Message))
    tool_response.stop_reason = "tool_use"
    tool_response.content = [tool_block]

    final_response = cast(Message, MagicMock(spec=Message))
    final_response.stop_reason = "end_turn"
    final_response.content = [text_block]

    mock_anthropic_client.messages.create = AsyncMock(side_effect=[tool_response, final_response])  # type: ignore[method-assign]

    agent = Agent(mock_anthropic_client, registry, "system")
    chunks = []
    async for chunk in agent.run("hi"):
        chunks.append(chunk)

    assert chunks == ["Done!"]
    # messages: user, assistant (tool_use), user (tool_result), assistant (end_turn)
    assert len(agent.messages) == 4


@pytest.mark.asyncio
async def test_agent_on_tool_use_callback(mock_anthropic_client: anthropic.AsyncAnthropic) -> None:
    """on_tool_use callback is called with the names of executed tools."""
    from max_ai.tools.base import BaseTool, ToolDefinition

    class NoopTool(BaseTool):
        def definitions(self) -> list[ToolDefinition]:
            return [
                ToolDefinition(
                    name="noop",
                    description="Does nothing",
                    input_schema={"type": "object", "properties": {}},
                )
            ]

        async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
            return "ok"

    registry = ToolRegistry()
    registry.register(NoopTool())

    tool_block = cast(ToolUseBlock, MagicMock(spec=ToolUseBlock))
    tool_block.type = "tool_use"
    tool_block.name = "noop"
    tool_block.input = {}
    tool_block.id = "t1"

    text_block = cast(TextBlock, MagicMock(spec=TextBlock))
    text_block.type = "text"
    text_block.text = "Done"

    tool_response = cast(Message, MagicMock(spec=Message))
    tool_response.stop_reason = "tool_use"
    tool_response.content = [tool_block]

    final_response = cast(Message, MagicMock(spec=Message))
    final_response.stop_reason = "end_turn"
    final_response.content = [text_block]

    mock_anthropic_client.messages.create = AsyncMock(side_effect=[tool_response, final_response])  # type: ignore[method-assign]

    called_with: list[str] = []
    agent = Agent(mock_anthropic_client, registry, "system")
    async for _ in agent.run("hi", on_tool_use=lambda names: called_with.extend(names)):
        pass

    assert called_with == ["noop"]


@pytest.mark.asyncio
async def test_agent_tool_exception_is_handled(
    mock_anthropic_client: anthropic.AsyncAnthropic,
) -> None:
    """When a tool raises, the exception is caught and passed back as an error string."""
    from max_ai.tools.base import BaseTool, ToolDefinition

    class BrokenTool(BaseTool):
        def definitions(self) -> list[ToolDefinition]:
            return [
                ToolDefinition(
                    name="broken",
                    description="Always fails",
                    input_schema={"type": "object", "properties": {}},
                )
            ]

        async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
            raise RuntimeError("tool exploded")

    registry = ToolRegistry()
    registry.register(BrokenTool())

    tool_block = cast(ToolUseBlock, MagicMock(spec=ToolUseBlock))
    tool_block.type = "tool_use"
    tool_block.name = "broken"
    tool_block.input = {}
    tool_block.id = "t1"

    text_block = cast(TextBlock, MagicMock(spec=TextBlock))
    text_block.type = "text"
    text_block.text = "Handled"

    tool_response = cast(Message, MagicMock(spec=Message))
    tool_response.stop_reason = "tool_use"
    tool_response.content = [tool_block]

    final_response = cast(Message, MagicMock(spec=Message))
    final_response.stop_reason = "end_turn"
    final_response.content = [text_block]

    mock_anthropic_client.messages.create = AsyncMock(side_effect=[tool_response, final_response])  # type: ignore[method-assign]

    agent = Agent(mock_anthropic_client, registry, "system")
    chunks = []
    async for chunk in agent.run("hi"):
        chunks.append(chunk)

    assert chunks == ["Handled"]
    # messages[2] = user (tool_result), after user (0) and assistant tool_use (1)
    tool_result_content = cast(list[ToolResultBlockParam], agent.messages[2]["content"])[0][
        "content"
    ]
    assert "Error" in tool_result_content


@pytest.mark.asyncio
async def test_agent_unexpected_stop_reason(
    mock_anthropic_client: anthropic.AsyncAnthropic, empty_registry: ToolRegistry
) -> None:
    """An unrecognised stop_reason yields a message and exits."""
    response = cast(Message, MagicMock(spec=Message))
    response.stop_reason = "some_future_reason"  # type: ignore[assignment]
    response.content = []
    mock_anthropic_client.messages.create = AsyncMock(return_value=response)  # type: ignore[method-assign]

    agent = Agent(mock_anthropic_client, empty_registry, "system")
    chunks = []
    async for chunk in agent.run("hi"):
        chunks.append(chunk)

    assert len(chunks) == 1
    assert "some_future_reason" in chunks[0]


@pytest.mark.asyncio
async def test_agent_max_iterations(
    mock_anthropic_client: anthropic.AsyncAnthropic, empty_registry: ToolRegistry
) -> None:
    """Agent yields a message when max_iterations is exhausted without end_turn."""
    response = cast(Message, MagicMock(spec=Message))
    response.stop_reason = "pause_turn"
    response.content = []
    mock_anthropic_client.messages.create = AsyncMock(return_value=response)  # type: ignore[method-assign]

    agent = Agent(mock_anthropic_client, empty_registry, "system", max_iterations=2)
    chunks = []
    async for chunk in agent.run("hi"):
        chunks.append(chunk)

    assert len(chunks) == 1
    assert "Max iterations" in chunks[0]


@pytest.mark.asyncio
async def test_agent_includes_web_search_tool(
    mock_anthropic_client: anthropic.AsyncAnthropic, empty_registry: ToolRegistry
) -> None:
    """When a web_search_tool is provided, its api_definition is passed to the API call."""
    from max_ai.tools.search import AnthropicWebSearch

    response = cast(Message, MagicMock(spec=Message))
    response.stop_reason = "end_turn"
    response.content = [cast(TextBlock, MagicMock(spec=TextBlock, type="text", text="ok"))]
    mock_anthropic_client.messages.create = AsyncMock(return_value=response)  # type: ignore[method-assign]

    web_search_tool = AnthropicWebSearch(max_uses=3)
    agent = Agent(mock_anthropic_client, empty_registry, "system", web_search_tool=web_search_tool)
    async for _ in agent.run("hi"):
        pass

    call_kwargs = mock_anthropic_client.messages.create.call_args.kwargs
    tools_passed = call_kwargs["tools"]
    assert web_search_tool.api_definition() in tools_passed


@pytest.mark.asyncio
async def test_agent_local_web_search_tool_is_executed(
    mock_anthropic_client: anthropic.AsyncAnthropic, empty_registry: ToolRegistry
) -> None:
    """When stop_reason is tool_use for a local web search tool, execute() is called."""
    from typing import Any

    class LocalSearch(BaseWebSearchTool):
        executed: bool = False

        @property
        def tool_name(self) -> str:
            return "local_search"

        @property
        def is_server_tool(self) -> bool:
            return False

        def api_definition(self) -> dict[str, Any]:
            return {"name": self.tool_name, "input_schema": {}}

        async def execute(self, tool_input: dict[str, Any]) -> str:
            LocalSearch.executed = True
            return "search results"

    tool_block = cast(ToolUseBlock, MagicMock(spec=ToolUseBlock))
    tool_block.type = "tool_use"
    tool_block.name = "local_search"
    tool_block.input = {"query": "test"}
    tool_block.id = "ws_1"

    text_block = cast(TextBlock, MagicMock(spec=TextBlock))
    text_block.type = "text"
    text_block.text = "Done"

    tool_response = cast(Message, MagicMock(spec=Message))
    tool_response.stop_reason = "tool_use"
    tool_response.content = [tool_block]

    final_response = cast(Message, MagicMock(spec=Message))
    final_response.stop_reason = "end_turn"
    final_response.content = [text_block]

    mock_anthropic_client.messages.create = AsyncMock(side_effect=[tool_response, final_response])  # type: ignore[method-assign]

    local_search = LocalSearch()
    agent = Agent(mock_anthropic_client, empty_registry, "system", web_search_tool=local_search)
    async for _ in agent.run("hi"):
        pass

    assert LocalSearch.executed is True
