"""SetNextStateTool — lets the agent control what state the assistant enters after speaking."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from max_ai.tools.base import BaseTool, ToolDefinition

if TYPE_CHECKING:
    from max_ai.agent.agent import Agent


class SetNextStateTool(BaseTool):
    """Tool that sets Agent.next_state for the orchestrator to read after AgentDone."""

    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="set_next_state",
                description=(
                    "Set the assistant state after speaking. "
                    "Use 'listening' to immediately start listening again after the response. "
                    "Use 'idle' (default) to return to waiting for a wake word."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "enum": ["idle", "listening"],
                            "description": (
                                "The state to enter after the assistant finishes speaking."
                            ),
                        }
                    },
                    "required": ["state"],
                },
            )
        ]

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        state = str(tool_input.get("state", "idle"))
        self._agent.next_state = state
        return f"Next state set to '{state}'."
