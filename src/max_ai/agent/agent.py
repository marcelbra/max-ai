"""
Anthropic agentic loop encapsulated in an Agent class.

stop_reason drives the loop:
  tool_use   → execute tools, append results, continue
  end_turn   → yield AgentText chunks then AgentDone, done
  pause_turn → continue (server tools)
  max_tokens → yield truncation notice as AgentText then AgentDone, done

Ref: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Literal, cast

import anthropic
from anthropic import omit
from anthropic.types import ToolResultBlockParam, ToolUnionParam

from max_ai.config import settings
from max_ai.tools.registry import ToolRegistry
from max_ai.tools.search import BaseWebSearchTool
from max_ai.voice.events import AgentDone, AgentText


class Agent:
    """Runs the Anthropic agentic loop and persists conversation history."""

    def __init__(
        self,
        client: anthropic.AsyncAnthropic,
        registry: ToolRegistry,
        system: str,
        max_iterations: int = 10,
        web_search_tool: BaseWebSearchTool | None = None,
    ) -> None:
        self.client = client
        self.registry = registry
        self.system = system
        self.max_iterations = max_iterations
        self.web_search_tool = web_search_tool
        self.messages: list[anthropic.types.MessageParam] = []
        self.next_state: str | None = None

    async def _execute_tool(self, name: str, tool_input: dict[str, Any]) -> str:
        """Route a tool call to the web search tool or the registry."""
        if self.web_search_tool is not None and name == self.web_search_tool.tool_name:
            return await self.web_search_tool.execute(tool_input)
        return await self.registry.execute(name, tool_input)

    async def run(self, user_message: str) -> AsyncIterator[AgentText | AgentDone]:
        """Append user_message to history and run one agent turn.

        Yields AgentText for each text block streamed.
        Yields AgentDone(next_state=self.next_state) at end_turn.
        No awareness of audio, TTS, or display.
        """
        self.next_state = None
        self.messages.append({"role": "user", "content": user_message})

        api_tools = self.registry.get_api_tools()
        if self.web_search_tool:
            api_tools = api_tools + [self.web_search_tool.api_definition()]

        for _ in range(self.max_iterations):
            response = await self.client.messages.create(
                model=settings.model,
                max_tokens=settings.max_tokens,
                system=self.system,
                messages=self.messages,
                tools=cast(list[ToolUnionParam], api_tools) if api_tools else omit,
            )
            self.messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if block.type == "text":
                        yield AgentText(text=block.text)
                yield AgentDone(next_state=self._validated_next_state())
                return

            elif response.stop_reason == "tool_use":
                tool_blocks = [block for block in response.content if block.type == "tool_use"]

                results = await asyncio.gather(
                    *[
                        self._execute_tool(tool_block.name, tool_block.input)
                        for tool_block in tool_blocks
                    ],
                    return_exceptions=True,
                )

                tool_results: list[ToolResultBlockParam] = []
                for tool_block, result in zip(tool_blocks, results, strict=False):
                    content = f"Error: {result}" if isinstance(result, Exception) else str(result)
                    tool_results.append(
                        ToolResultBlockParam(
                            type="tool_result",
                            tool_use_id=tool_block.id,
                            content=content,
                        )
                    )

                self.messages.append({"role": "user", "content": tool_results})

            elif response.stop_reason == "pause_turn":
                continue

            elif response.stop_reason == "max_tokens":
                yield AgentText(text="[Response truncated — max_tokens reached]")
                yield AgentDone(next_state=None)
                return

            else:
                yield AgentText(text=f"[Unexpected stop_reason: {response.stop_reason}]")
                yield AgentDone(next_state=None)
                return

        yield AgentText(text="[Max iterations reached without a final response]")
        yield AgentDone(next_state=None)

    def _validated_next_state(self) -> Literal["idle", "listening"] | None:
        """Return next_state if it is a valid literal, otherwise None."""
        if self.next_state == "idle":
            return "idle"
        if self.next_state == "listening":
            return "listening"
        return None
