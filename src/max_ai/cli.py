"""Entry point for the max-ai voice CLI."""

import asyncio
import logging
from typing import Any

from max_ai.agent import Agent, load_agent_prompt
from max_ai.client import create_client
from max_ai.config import settings
from max_ai.db import ConversationService, DocumentService
from max_ai.monitoring.langwatch import setup_langwatch
from max_ai.tools import (
    AlarmTool,
    CalendarTools,
    DocumentTools,
    SetNextStateTool,
    SpotifyTools,
    TimerTool,
    ToolRegistry,
)
from max_ai.voice.audio_capture import AudioCapture
from max_ai.voice.display import TerminalDisplay
from max_ai.voice.events import TimerFired
from max_ai.voice.orchestrator import Orchestrator, OrchestratorConfig
from max_ai.voice.transcribe import StreamingTranscriber
from max_ai.voice.tts import TTSPlayer


async def main() -> None:
    logging.basicConfig(level=settings.log_level)
    setup_langwatch()

    if not settings.elevenlabs_api_key:
        from rich.console import Console

        Console().print(
            "[red]Error:[/] MAX_AI_ELEVENLABS_API_KEY is not set. Add it to your .env file."
        )
        return

    async with (
        ConversationService(),
        DocumentService() as document_service,
    ):
        client = create_client()
        use_spotify = bool(settings.spotify_client_id and settings.spotify_client_secret)

        tool_registry = ToolRegistry()
        tool_registry.register(DocumentTools(document_service=document_service))
        tool_registry.register(CalendarTools())
        tool_registry.register(AlarmTool())
        if use_spotify:
            tool_registry.register(SpotifyTools())

        system_prompt = load_agent_prompt()
        agent = Agent(client, tool_registry, system_prompt)

        # TimerTool injects messages via an asyncio.Queue; we bridge it to the
        # orchestrator bus via a background forwarding task.
        timer_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        tool_registry.register(TimerTool(timer_queue))
        tool_registry.register(SetNextStateTool(agent))

        # Mode detection: wake-word if Picovoice key + Deepgram key are set,
        # otherwise fall back to push-to-talk (Enter key).
        if settings.picovoice_access_key and settings.deepgram_api_key:
            from max_ai.voice.wakeword import WakeWordDetector

            wake_word_detector: object = WakeWordDetector(
                settings.picovoice_access_key,
                settings.porcupine_keyword_path,
            )
        else:
            from max_ai.voice.wakeword import KeyboardWakeWordDetector

            wake_word_detector = KeyboardWakeWordDetector()

        tts_player = TTSPlayer(
            api_key=settings.elevenlabs_api_key,
            voice_id=settings.elevenlabs_voice_id,
            model_id=settings.elevenlabs_tts_model,
            output_device=settings.tts_output_device,
        )
        transcriber = StreamingTranscriber(settings.deepgram_api_key)
        audio_capture = AudioCapture(input_device=settings.voice_input_device)
        display = TerminalDisplay()

        orchestrator = Orchestrator(
            audio_capture=audio_capture,
            wake_word_detector=wake_word_detector,  # type: ignore[arg-type]
            transcriber=transcriber,
            agent=agent,
            tts_player=tts_player,
            display=display,
            config=OrchestratorConfig(min_words=settings.vad_min_words),
        )

        # Forward timer events onto the orchestrator bus.
        async def _forward_timer_events() -> None:
            while True:
                event = await timer_queue.get()
                orchestrator._bus.put_nowait(TimerFired(message=event["content"]))

        async with asyncio.TaskGroup() as task_group:
            task_group.create_task(orchestrator.run())
            task_group.create_task(_forward_timer_events())


def run_voice_cli() -> None:
    asyncio.run(main())
