"""Tests for TimerTool."""

import asyncio

from max_ai.tools.timer import TimerTool


async def test_timer_execute_returns_confirmation():
    queue: asyncio.Queue[dict] = asyncio.Queue()
    tool = TimerTool(event_queue=queue)
    result = await tool.execute("set_timer", {"seconds": 60, "label": "lunch"})
    assert "60" in result
    assert "lunch" in result


async def test_timer_fires_event_into_queue():
    queue: asyncio.Queue[dict] = asyncio.Queue()
    tool = TimerTool(event_queue=queue)
    await tool.execute("set_timer", {"seconds": 0, "label": "ping"})
    await asyncio.sleep(0.05)  # let the background task fire
    assert not queue.empty()
    event = await queue.get()
    assert event["role"] == "user"
    assert "ping" in event["content"]
