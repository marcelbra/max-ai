"""Tests for the Agent class."""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import anthropic
from anthropic.types import Message, TextBlock, ToolResultBlockParam, ToolUseBlock

from max_ai.agent import Agent
from max_ai.tools.registry import ToolRegistry
from max_ai.tools.search import BaseWebSearchTool
from max_ai.voice.events import AgentDone, AgentText


async def test_agent_end_turn(
    mock_anthropic_client: anthropic.AsyncAnthropic, empty_registry: ToolRegistry
) -> None:
    """Agent yields AgentText then AgentDone when stop_reason is end_turn."""
    response = cast(Message, MagicMock(spec=Message))
    response.stop_reason = "end_turn"
    response.content = [cast(TextBlock, MagicMock(spec=TextBlock, type="text", text="Hello!"))]
    mock_anthropic_client.messages.create = AsyncMock(return_value=response)  # type: ignore[method-assign]

    agent = Agent(mock_anthropic_client, empty_registry, "system")
    events = []
    async for event in agent.run("hi"):
        events.append(event)

    assert events[0] == AgentText(text="Hello!")
    assert isinstance(events[-1], AgentDone)
    assert len(agent.messages) == 2
    assert agent.messages[0]["role"] == "user"
    assert agent.messages[1]["role"] == "assistant"


async def test_agent_max_tokens(
    mock_anthropic_client: anthropic.AsyncAnthropic, empty_registry: ToolRegistry
) -> None:
    """Agent yields AgentText truncation notice then AgentDone on max_tokens."""
    response = cast(Message, MagicMock(spec=Message))
    response.stop_reason = "max_tokens"
    response.content = []
    mock_anthropic_client.messages.create = AsyncMock(return_value=response)  # type: ignore[method-assign]

    agent = Agent(mock_anthropic_client, empty_registry, "system")
    events = []
    async for event in agent.run("hi"):
        events.append(event)

    text_events = [e for e in events if isinstance(e, AgentText)]
    assert any("max_tokens" in e.text for e in text_events)
    assert isinstance(events[-1], AgentDone)


async def test_agent_tool_use_then_end_turn(
    mock_anthropic_client: anthropic.AsyncAnthropic,
) -> None:
    """Agent executes tools then yields final AgentText + AgentDone."""
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
    events = []
    async for event in agent.run("hi"):
        events.append(event)

    text_events = [e for e in events if isinstance(e, AgentText)]
    assert text_events == [AgentText(text="Done!")]
    assert isinstance(events[-1], AgentDone)
    # messages: user, assistant (tool_use), user (tool_result), assistant (end_turn)
    assert len(agent.messages) == 4


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
    events = []
    async for event in agent.run("hi"):
        events.append(event)

    text_events = [e for e in events if isinstance(e, AgentText)]
    assert text_events == [AgentText(text="Handled")]
    # messages[2] = user (tool_result)
    tool_result_content = cast(list[ToolResultBlockParam], agent.messages[2]["content"])[0][
        "content"
    ]
    assert "Error" in tool_result_content


async def test_agent_unexpected_stop_reason(
    mock_anthropic_client: anthropic.AsyncAnthropic, empty_registry: ToolRegistry
) -> None:
    """An unrecognised stop_reason yields an AgentText message and AgentDone."""
    response = cast(Message, MagicMock(spec=Message))
    response.stop_reason = "some_future_reason"  # type: ignore[assignment]
    response.content = []
    mock_anthropic_client.messages.create = AsyncMock(return_value=response)  # type: ignore[method-assign]

    agent = Agent(mock_anthropic_client, empty_registry, "system")
    events = []
    async for event in agent.run("hi"):
        events.append(event)

    text_events = [e for e in events if isinstance(e, AgentText)]
    assert len(text_events) == 1
    assert "some_future_reason" in text_events[0].text
    assert isinstance(events[-1], AgentDone)


async def test_agent_max_iterations(
    mock_anthropic_client: anthropic.AsyncAnthropic, empty_registry: ToolRegistry
) -> None:
    """Agent yields AgentText + AgentDone when max_iterations is exhausted."""
    response = cast(Message, MagicMock(spec=Message))
    response.stop_reason = "pause_turn"
    response.content = []
    mock_anthropic_client.messages.create = AsyncMock(return_value=response)  # type: ignore[method-assign]

    agent = Agent(mock_anthropic_client, empty_registry, "system", max_iterations=2)
    events = []
    async for event in agent.run("hi"):
        events.append(event)

    text_events = [e for e in events if isinstance(e, AgentText)]
    assert len(text_events) == 1
    assert "Max iterations" in text_events[0].text
    assert isinstance(events[-1], AgentDone)


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


async def test_agent_local_web_search_tool_is_executed(
    mock_anthropic_client: anthropic.AsyncAnthropic, empty_registry: ToolRegistry
) -> None:
    """When stop_reason is tool_use for a local web search tool, execute() is called."""

    class LocalSearch(BaseWebSearchTool):
        executed: bool = False

        @property
        def tool_name(self) -> str:
            return "local_search"

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


async def test_agent_next_state_resets_per_turn(
    mock_anthropic_client: anthropic.AsyncAnthropic, empty_registry: ToolRegistry
) -> None:
    """next_state is reset to None at the start of every run() call."""
    response = cast(Message, MagicMock(spec=Message))
    response.stop_reason = "end_turn"
    response.content = [cast(TextBlock, MagicMock(spec=TextBlock, type="text", text="ok"))]
    mock_anthropic_client.messages.create = AsyncMock(return_value=response)  # type: ignore[method-assign]

    agent = Agent(mock_anthropic_client, empty_registry, "system")
    agent.next_state = "listening"  # set from a previous turn

    async for _ in agent.run("hi"):
        pass

    # next_state should have been reset at turn start, then stayed None
    # (no SetNextStateTool was called in this turn)
    events = []
    mock_anthropic_client.messages.create = AsyncMock(return_value=response)  # type: ignore[method-assign]
    async for event in agent.run("hi2"):
        events.append(event)

    done_events = [e for e in events if isinstance(e, AgentDone)]
    assert done_events[-1].next_state is None


async def test_agent_done_carries_next_state(
    mock_anthropic_client: anthropic.AsyncAnthropic, empty_registry: ToolRegistry
) -> None:
    """AgentDone carries next_state value set via agent.next_state during the turn."""
    response = cast(Message, MagicMock(spec=Message))
    response.stop_reason = "end_turn"
    response.content = [cast(TextBlock, MagicMock(spec=TextBlock, type="text", text="ok"))]
    mock_anthropic_client.messages.create = AsyncMock(return_value=response)  # type: ignore[method-assign]

    agent = Agent(mock_anthropic_client, empty_registry, "system")

    events = []
    # Simulate a tool setting next_state mid-run by patching _validated_next_state.
    original = agent._validated_next_state
    agent._validated_next_state = lambda: "listening"  # type: ignore[method-assign, assignment]

    async for event in agent.run("hi"):
        events.append(event)

    agent._validated_next_state = original  # type: ignore[method-assign]

    done_events = [e for e in events if isinstance(e, AgentDone)]
    assert done_events[-1].next_state == "listening"
