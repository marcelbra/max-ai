"""Background timer tool — fires an event into the chat loop after N seconds."""

import asyncio
from typing import Any

from max_ai.tools.base import BaseTool, ToolDefinition


class TimerTool(BaseTool):
    def __init__(self, event_queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._queue = event_queue

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="set_timer",
                description=(
                    "Set a background timer. After the given number of seconds you will "
                    "receive a background event and should react (e.g. notify the user, "
                    "sound an alarm, run a follow-up action)."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "seconds": {
                            "type": "integer",
                            "description": "Seconds until the timer fires.",
                        },
                        "label": {
                            "type": "string",
                            "description": "Message included when the timer fires.",
                        },
                    },
                    "required": ["seconds", "label"],
                },
            )
        ]

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        seconds: int = tool_input["seconds"]
        label: str = tool_input["label"]
        asyncio.create_task(self._fire_after(seconds, label))
        return f"Timer set for {seconds}s: '{label}'"

    async def _fire_after(self, seconds: int, label: str) -> None:
        await asyncio.sleep(seconds)
        await self._queue.put(
            {"role": "user", "content": f"[BACKGROUND EVENT] Timer fired: {label}"}
        )
