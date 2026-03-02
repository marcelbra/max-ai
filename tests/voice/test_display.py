"""Tests for TerminalDisplay — verifies correct Rich output per state."""

from typing import cast
from unittest.mock import MagicMock

from rich.console import Console

from max_ai.voice.display import TerminalDisplay
from max_ai.voice.events import AssistantState


def _make_display_with_mock_console() -> tuple[TerminalDisplay, MagicMock]:
    display = TerminalDisplay()
    mock_console = cast(Console, MagicMock(spec=Console))
    display._console = mock_console
    return display, cast(MagicMock, mock_console)


def test_on_state_change_prints_idle_label() -> None:
    display, mock_console = _make_display_with_mock_console()
    display.on_state_change(AssistantState.LISTENING, AssistantState.IDLE)
    mock_console.print.assert_called_once()
    printed = cast(MagicMock, mock_console.print).call_args[0][0]
    assert "idle" in printed


def test_on_state_change_prints_listening_label() -> None:
    display, mock_console = _make_display_with_mock_console()
    display.on_state_change(AssistantState.IDLE, AssistantState.LISTENING)
    printed = cast(MagicMock, mock_console.print).call_args[0][0]
    assert "listening" in printed


def test_on_state_change_prints_thinking_label() -> None:
    display, mock_console = _make_display_with_mock_console()
    display.on_state_change(AssistantState.LISTENING, AssistantState.PROCESSING)
    printed = cast(MagicMock, mock_console.print).call_args[0][0]
    assert "thinking" in printed


def test_on_state_change_prints_speaking_label() -> None:
    display, mock_console = _make_display_with_mock_console()
    display.on_state_change(AssistantState.PROCESSING, AssistantState.SPEAKING)
    printed = cast(MagicMock, mock_console.print).call_args[0][0]
    assert "speaking" in printed


def test_on_agent_text_prints_text() -> None:
    display, mock_console = _make_display_with_mock_console()
    display.on_agent_text("Hello, world!")
    mock_console.print.assert_called_once_with("Hello, world!", end="")


def test_on_tool_use_prints_tool_names() -> None:
    display, mock_console = _make_display_with_mock_console()
    display.on_tool_use(["spotify", "calendar"])
    printed = cast(MagicMock, mock_console.print).call_args[0][0]
    assert "spotify" in printed
    assert "calendar" in printed
