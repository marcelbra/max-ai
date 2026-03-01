"""Tests for CalendarTools and helpers."""

from unittest.mock import patch

import pytest

from max_ai.agent.tools.calendar import CalendarTools, _dispatch, _esc


def test_esc_backslash() -> None:
    assert _esc("a\\b") == "a\\\\b"


def test_esc_double_quote() -> None:
    assert _esc('say "hi"') == 'say \\"hi\\"'


def test_esc_clean_string() -> None:
    assert _esc("hello") == "hello"


def test_definitions_returns_all_tool_names() -> None:
    tool = CalendarTools()
    names = {d.name for d in tool.definitions()}
    assert names == {
        "calendar_list_calendars",
        "calendar_list_events",
        "calendar_create_event",
        "calendar_update_event",
        "calendar_delete_event",
    }


def test_dispatch_unknown_tool() -> None:
    result = _dispatch("nonexistent", {})
    assert "Unknown" in result


@pytest.mark.asyncio
async def test_execute_wraps_exceptions_as_error_string() -> None:
    tool = CalendarTools()
    with patch(
        "max_ai.agent.tools.calendar._run_jxa", side_effect=RuntimeError("osascript error")
    ):
        result = await tool.execute("calendar_list_calendars", {})
    assert "Calendar error" in result


@pytest.mark.asyncio
async def test_list_calendars_returns_jxa_output() -> None:
    tool = CalendarTools()
    with patch("max_ai.agent.tools.calendar._run_jxa", return_value="Work\nPersonal"):
        result = await tool.execute("calendar_list_calendars", {})
    assert "Work" in result
    assert "Personal" in result


@pytest.mark.asyncio
async def test_list_calendars_empty_returns_message() -> None:
    tool = CalendarTools()
    with patch("max_ai.agent.tools.calendar._run_jxa", return_value=""):
        result = await tool.execute("calendar_list_calendars", {})
    assert "No calendars" in result
