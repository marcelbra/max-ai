"""Tests for the agent loop."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from max_ai.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_agent_end_turn(mock_anthropic_client: MagicMock, empty_registry: ToolRegistry) -> None:
    """Agent yields text when stop_reason is end_turn."""
    from max_ai.agent import run

    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [MagicMock(type="text", text="Hello!")]
    mock_anthropic_client.messages.create = AsyncMock(return_value=response)

    messages: list = []
    chunks = []
    async for chunk in run(mock_anthropic_client, empty_registry, messages, "system"):
        chunks.append(chunk)

    assert chunks == ["Hello!"]
    assert len(messages) == 1
    assert messages[0]["role"] == "assistant"


@pytest.mark.asyncio
async def test_agent_max_tokens(mock_anthropic_client: MagicMock, empty_registry: ToolRegistry) -> None:
    """Agent yields truncation notice on max_tokens."""
    from max_ai.agent import run

    response = MagicMock()
    response.stop_reason = "max_tokens"
    response.content = []
    mock_anthropic_client.messages.create = AsyncMock(return_value=response)

    messages: list = []
    chunks = []
    async for chunk in run(mock_anthropic_client, empty_registry, messages, "system"):
        chunks.append(chunk)

    assert any("max_tokens" in c for c in chunks)


@pytest.mark.asyncio
async def test_agent_tool_use_then_end_turn(
    mock_anthropic_client: MagicMock,
) -> None:
    """Agent executes tools then yields final response."""
    from max_ai.agent import run
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

        async def execute(self, tool_name: str, tool_input: dict) -> str:
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

    mock_anthropic_client.messages.create = AsyncMock(
        side_effect=[tool_response, final_response]
    )

    messages: list = []
    chunks = []
    async for chunk in run(mock_anthropic_client, registry, messages, "system"):
        chunks.append(chunk)

    assert chunks == ["Done!"]
    # messages should have: assistant (tool_use), user (tool_result), assistant (end_turn)
    assert len(messages) == 3
