"""
Anthropic agentic loop encapsulated in an Agent class.

stop_reason drives the loop:
  tool_use   → execute tools, append results, continue
  end_turn   → yield final text, done
  pause_turn → continue (server tools)
  max_tokens → yield truncation notice, done

Ref: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use
"""

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

import anthropic

from max_ai.agent.tools.registry import ToolRegistry
from max_ai.config import settings


class Agent:
    """Runs the Anthropic agentic loop and persists conversation history."""

    def __init__(
        self,
        client: anthropic.AsyncAnthropic,
        registry: ToolRegistry,
        system: str,
        max_iterations: int = 10,
    ) -> None:
        self.client = client
        self.registry = registry
        self.system = system
        self.max_iterations = max_iterations
        self.messages: list[dict[str, Any]] = []

    async def run(
        self,
        user_message: str,
        on_tool_use: Callable[[list[str]], None] | None = None,
    ) -> AsyncIterator[str]:
        """Append user_message to history and run one agent turn, yielding text chunks."""
        self.messages.append({"role": "user", "content": user_message})

        api_tools = self.registry.get_api_tools()
        if settings.enable_web_search:
            api_tools = api_tools + [
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": settings.web_search_max_uses,
                }
            ]

        for _ in range(self.max_iterations):
            kwargs: dict[str, Any] = dict(
                model=settings.model,
                max_tokens=settings.max_tokens,
                system=self.system,
                messages=self.messages,
            )
            if api_tools:
                kwargs["tools"] = api_tools

            response = await self.client.messages.create(**kwargs)
            self.messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if block.type == "text":
                        yield block.text
                return

            elif response.stop_reason == "tool_use":
                tool_blocks = [b for b in response.content if b.type == "tool_use"]

                if on_tool_use:
                    on_tool_use([tb.name for tb in tool_blocks])

                results = await asyncio.gather(
                    *[self.registry.execute(tb.name, tb.input) for tb in tool_blocks],
                    return_exceptions=True,
                )

                tool_results = []
                for tb, result in zip(tool_blocks, results, strict=False):
                    content = f"Error: {result}" if isinstance(result, Exception) else str(result)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tb.id,
                            "content": content,
                        }
                    )

                self.messages.append({"role": "user", "content": tool_results})

            elif response.stop_reason == "pause_turn":
                continue

            elif response.stop_reason == "max_tokens":
                yield "[Response truncated — max_tokens reached]"
                return

            else:
                yield f"[Unexpected stop_reason: {response.stop_reason}]"
                return

        yield "[Max iterations reached without a final response]"
