"""Tests for SetNextStateTool."""

from typing import cast
from unittest.mock import MagicMock

import anthropic

from max_ai.agent.agent import Agent
from max_ai.tools.registry import ToolRegistry
from max_ai.tools.state import SetNextStateTool


def _make_agent() -> Agent:
    client = cast(anthropic.AsyncAnthropic, MagicMock(spec=anthropic.AsyncAnthropic))
    return Agent(client, ToolRegistry(), "system")


async def test_set_next_state_sets_listening() -> None:
    agent = _make_agent()
    tool = SetNextStateTool(agent)
    result = await tool.execute("set_next_state", {"state": "listening"})
    assert agent.next_state == "listening"
    assert "listening" in result


async def test_set_next_state_sets_idle() -> None:
    agent = _make_agent()
    tool = SetNextStateTool(agent)
    result = await tool.execute("set_next_state", {"state": "idle"})
    assert agent.next_state == "idle"
    assert "idle" in result


async def test_set_next_state_tool_definitions_include_enum() -> None:
    agent = _make_agent()
    tool = SetNextStateTool(agent)
    definitions = tool.definitions()
    assert len(definitions) == 1
    schema = definitions[0].input_schema
    state_enum = schema["properties"]["state"]["enum"]
    assert "idle" in state_enum
    assert "listening" in state_enum


async def test_set_next_state_tool_name() -> None:
    agent = _make_agent()
    tool = SetNextStateTool(agent)
    assert tool.definitions()[0].name == "set_next_state"
