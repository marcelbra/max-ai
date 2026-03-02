"""Tests that the orchestrator emits structured DEBUG log messages."""

import logging

import pytest

from max_ai.voice.events import AgentDone, AssistantState, WakeWordDetected
from max_ai.voice.orchestrator import Orchestrator, OrchestratorConfig
from tests.voice.test_orchestrator import (
    _make_agent_with_responses,
    _make_mock_audio_capture,
    _make_mock_display,
    _make_mock_keyboard_detector,
    _make_mock_transcriber,
    _make_mock_tts_player,
)


def _make_orchestrator() -> Orchestrator:
    return Orchestrator(
        audio_capture=_make_mock_audio_capture(),
        wake_word_detector=_make_mock_keyboard_detector(),
        transcriber=_make_mock_transcriber(),
        agent=_make_agent_with_responses([AgentDone(next_state=None)]),
        tts_player=_make_mock_tts_player(),
        display=_make_mock_display(),
        config=OrchestratorConfig(min_words=1),
    )


async def test_transition_emits_debug_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Dispatching WakeWordDetected logs 'state IDLE → LISTENING' at DEBUG."""
    orchestrator = _make_orchestrator()

    with caplog.at_level(logging.DEBUG, logger="max_ai.voice.orchestrator"):
        await orchestrator._dispatch(WakeWordDetected())

    assert orchestrator._state == AssistantState.LISTENING
    assert any(
        "state IDLE → LISTENING" in record.message
        for record in caplog.records
        if record.levelno == logging.DEBUG
    )
