"""Display Protocol and TerminalDisplay implementation.

The Display Protocol is the only coupling between the Orchestrator and the
UI.  All methods are synchronous and must be non-blocking.

Swappable: a WebSocket UI implements the same Protocol and is passed to
Orchestrator as a constructor argument.
"""

from __future__ import annotations

from typing import Protocol

from rich.console import Console

from max_ai.voice.events import AssistantState

_STATE_ICONS: dict[AssistantState, str] = {
    AssistantState.IDLE: "○ idle",
    AssistantState.LISTENING: "● listening…",
    AssistantState.PROCESSING: "⟳ thinking…",
    AssistantState.SPEAKING: "◆ speaking…",
}


class Display(Protocol):
    def on_state_change(self, previous: AssistantState, current: AssistantState) -> None: ...

    def on_agent_text(self, text: str) -> None: ...

    def on_tool_use(self, tool_names: list[str]) -> None: ...


class TerminalDisplay:
    """Single-line status display using Rich."""

    def __init__(self) -> None:
        self._console = Console()

    def on_state_change(self, previous: AssistantState, current: AssistantState) -> None:
        label = _STATE_ICONS.get(current, current.value)
        self._console.print(f"\r[dim]{label}[/]", end="")

    def on_agent_text(self, text: str) -> None:
        self._console.print(text, end="")

    def on_tool_use(self, tool_names: list[str]) -> None:
        label = ", ".join(tool_names)
        self._console.print(f"\r[dim]⚙ {label}…[/]", end="")
