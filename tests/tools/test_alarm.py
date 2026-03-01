"""Tests for AlarmTool."""

from unittest.mock import patch

import numpy as np

from max_ai.tools.alarm import AlarmTool, _make_beep


def test_make_beep_returns_int16_array() -> None:
    beep = _make_beep(freq=440.0, duration=0.1, sample_rate=44100)
    assert beep.dtype == np.int16
    assert len(beep) == int(44100 * 0.1)


def test_alarm_definitions() -> None:
    tool = AlarmTool()
    definitions = tool.definitions()
    assert len(definitions) == 1
    assert definitions[0].name == "sound_alarm"


async def test_alarm_execute_returns_confirmation() -> None:
    tool = AlarmTool()
    with patch("max_ai.tools.alarm._play_alarm"):
        result = await tool.execute("sound_alarm", {})
    assert result == "Alarm sounded."


async def test_alarm_execute_calls_play_alarm() -> None:
    tool = AlarmTool()
    with patch("max_ai.tools.alarm._play_alarm") as mock_play:
        await tool.execute("sound_alarm", {})
    mock_play.assert_called_once()
