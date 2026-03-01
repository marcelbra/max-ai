"""Tests for the Agent class."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from max_ai.agent import Agent
from max_ai.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_agent_end_turn(
    mock_anthropic_client: MagicMock, empty_registry: ToolRegistry
) -> None:
    """Agent yields text when stop_reason is end_turn."""
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [MagicMock(type="text", text="Hello!")]
    mock_anthropic_client.messages.create = AsyncMock(return_value=response)

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
    mock_anthropic_client: MagicMock, empty_registry: ToolRegistry
) -> None:
    """Agent yields truncation notice on max_tokens."""
    response = MagicMock()
    response.stop_reason = "max_tokens"
    response.content = []
    mock_anthropic_client.messages.create = AsyncMock(return_value=response)

    agent = Agent(mock_anthropic_client, empty_registry, "system")
    chunks = []
    async for chunk in agent.run("hi"):
        chunks.append(chunk)

    assert any("max_tokens" in c for c in chunks)


@pytest.mark.asyncio
async def test_agent_tool_use_then_end_turn(
    mock_anthropic_client: MagicMock,
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

    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "echo"
    tool_block.input = {"text": "hello"}
    tool_block.id = "tool_1"

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Done!"

    tool_response = MagicMock()
    tool_response.stop_reason = "tool_use"
    tool_response.content = [tool_block]

    final_response = MagicMock()
    final_response.stop_reason = "end_turn"
    final_response.content = [text_block]

    mock_anthropic_client.messages.create = AsyncMock(side_effect=[tool_response, final_response])

    agent = Agent(mock_anthropic_client, registry, "system")
    chunks = []
    async for chunk in agent.run("hi"):
        chunks.append(chunk)

    assert chunks == ["Done!"]
    # messages: user, assistant (tool_use), user (tool_result), assistant (end_turn)
    assert len(agent.messages) == 4


@pytest.mark.asyncio
async def test_agent_on_tool_use_callback(mock_anthropic_client: MagicMock) -> None:
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

    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "noop"
    tool_block.input = {}
    tool_block.id = "t1"

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Done"

    tool_response = MagicMock()
    tool_response.stop_reason = "tool_use"
    tool_response.content = [tool_block]

    final_response = MagicMock()
    final_response.stop_reason = "end_turn"
    final_response.content = [text_block]

    mock_anthropic_client.messages.create = AsyncMock(side_effect=[tool_response, final_response])

    called_with: list[str] = []
    agent = Agent(mock_anthropic_client, registry, "system")
    async for _ in agent.run("hi", on_tool_use=lambda names: called_with.extend(names)):
        pass

    assert called_with == ["noop"]


@pytest.mark.asyncio
async def test_agent_tool_exception_is_handled(mock_anthropic_client: MagicMock) -> None:
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

    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "broken"
    tool_block.input = {}
    tool_block.id = "t1"

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Handled"

    tool_response = MagicMock()
    tool_response.stop_reason = "tool_use"
    tool_response.content = [tool_block]

    final_response = MagicMock()
    final_response.stop_reason = "end_turn"
    final_response.content = [text_block]

    mock_anthropic_client.messages.create = AsyncMock(side_effect=[tool_response, final_response])

    agent = Agent(mock_anthropic_client, registry, "system")
    chunks = []
    async for chunk in agent.run("hi"):
        chunks.append(chunk)

    assert chunks == ["Handled"]
    # messages[2] = user (tool_result), after user (0) and assistant tool_use (1)
    tool_result_content = agent.messages[2]["content"][0]["content"]
    assert "Error" in tool_result_content


@pytest.mark.asyncio
async def test_agent_unexpected_stop_reason(
    mock_anthropic_client: MagicMock, empty_registry: ToolRegistry
) -> None:
    """An unrecognised stop_reason yields a message and exits."""
    response = MagicMock()
    response.stop_reason = "some_future_reason"
    response.content = []
    mock_anthropic_client.messages.create = AsyncMock(return_value=response)

    agent = Agent(mock_anthropic_client, empty_registry, "system")
    chunks = []
    async for chunk in agent.run("hi"):
        chunks.append(chunk)

    assert len(chunks) == 1
    assert "some_future_reason" in chunks[0]


@pytest.mark.asyncio
async def test_agent_max_iterations(
    mock_anthropic_client: MagicMock, empty_registry: ToolRegistry
) -> None:
    """Agent yields a message when max_iterations is exhausted without end_turn."""
    response = MagicMock()
    response.stop_reason = "pause_turn"
    response.content = []
    mock_anthropic_client.messages.create = AsyncMock(return_value=response)

    agent = Agent(mock_anthropic_client, empty_registry, "system", max_iterations=2)
    chunks = []
    async for chunk in agent.run("hi"):
        chunks.append(chunk)

    assert len(chunks) == 1
    assert "Max iterations" in chunks[0]
