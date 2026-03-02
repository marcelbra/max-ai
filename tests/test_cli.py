"""Tests for CLI entry point."""

from __future__ import annotations

import asyncio
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

from max_ai.voice.orchestrator import Orchestrator
from max_ai.voice.wakeword import WakeWordDetector


def _make_async_context_manager() -> MagicMock:
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    return mock


class _NoOpTaskGroup:
    """Replaces asyncio.TaskGroup so main() exits without running tasks."""

    async def __aenter__(self) -> _NoOpTaskGroup:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    def create_task(self, coroutine: object) -> None:
        if asyncio.iscoroutine(coroutine):
            coroutine.close()


async def test_main_uses_wake_word_detector() -> None:
    """main() always instantiates WakeWordDetector (wake-word is a project requirement)."""
    captured_wake_word_detector: list[object] = []

    mock_orchestrator = cast(Orchestrator, MagicMock(spec=Orchestrator))
    mock_orchestrator.run = AsyncMock()  # type: ignore[method-assign]

    def _capturing_orchestrator(**kwargs: object) -> Orchestrator:
        captured_wake_word_detector.append(kwargs.get("wake_word_detector"))
        return mock_orchestrator

    fake_porcupine = MagicMock()
    fake_porcupine.frame_length = 512
    fake_porcupine.sample_rate = 16000
    fake_pvporcupine = MagicMock()
    fake_pvporcupine.create.return_value = fake_porcupine

    with (
        patch("max_ai.cli.settings") as mock_settings,
        patch("max_ai.cli.setup_langwatch"),
        patch("max_ai.cli.ConversationService", return_value=_make_async_context_manager()),
        patch("max_ai.cli.DocumentService", return_value=_make_async_context_manager()),
        patch("max_ai.cli.create_client", return_value=MagicMock()),
        patch("max_ai.cli.ToolRegistry", return_value=MagicMock()),
        patch("max_ai.cli.DocumentTools", return_value=MagicMock()),
        patch("max_ai.cli.CalendarTools", return_value=MagicMock()),
        patch("max_ai.cli.AlarmTool", return_value=MagicMock()),
        patch("max_ai.cli.TimerTool", return_value=MagicMock()),
        patch("max_ai.cli.SetNextStateTool", return_value=MagicMock()),
        patch("max_ai.cli.load_agent_prompt", return_value=""),
        patch("max_ai.cli.Agent", return_value=MagicMock()),
        patch("max_ai.cli.TTSPlayer", return_value=MagicMock()),
        patch("max_ai.cli.StreamingTranscriber", return_value=MagicMock()),
        patch("max_ai.cli.AudioCapture", return_value=MagicMock()),
        patch("max_ai.cli.TerminalDisplay", return_value=MagicMock()),
        patch("max_ai.cli.Orchestrator", side_effect=_capturing_orchestrator),
        patch("sys.modules", {**__import__("sys").modules, "pvporcupine": fake_pvporcupine}),
        patch("asyncio.TaskGroup", _NoOpTaskGroup),
    ):
        mock_settings.log_level = "WARNING"
        mock_settings.elevenlabs_api_key = "test-elevenlabs-key"
        mock_settings.picovoice_access_key = "test-picovoice-key"
        mock_settings.porcupine_keyword_path = ""
        mock_settings.spotify_client_id = ""
        mock_settings.spotify_client_secret = ""
        mock_settings.vad_min_words = 3
        mock_settings.elevenlabs_voice_id = "test-voice"
        mock_settings.elevenlabs_tts_model = "test-model"
        mock_settings.tts_output_device = None
        mock_settings.voice_input_device = None

        from max_ai.cli import main

        await main()

    assert len(captured_wake_word_detector) == 1
    assert isinstance(captured_wake_word_detector[0], WakeWordDetector)
