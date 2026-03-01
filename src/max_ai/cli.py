"""Entry point for the max-ai voice CLI."""

import asyncio
from typing import Any

from max_ai.agent import load_agent_prompt
from max_ai.client import create_client
from max_ai.config import settings
from max_ai.db import ConversationService, DocumentService
from max_ai.monitoring.langwatch import setup_langwatch
from max_ai.tools import (
    AlarmTool,
    CalendarTools,
    DocumentTools,
    SpotifyTools,
    TimerTool,
    ToolRegistry,
)
from max_ai.voice.loop import voice_chat_loop


async def main() -> None:
    setup_langwatch()

    async with (
        ConversationService() as conversation_service,
        DocumentService() as document_service,
    ):
        client = create_client()

        event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        use_spotify = settings.spotify_client_id and settings.spotify_client_secret

        tool_registry = ToolRegistry()

        tool_registry.register(DocumentTools(document_service=document_service))
        tool_registry.register(CalendarTools())
        tool_registry.register(TimerTool(event_queue))
        tool_registry.register(AlarmTool())
        if use_spotify:
            tool_registry.register(SpotifyTools())

        system_prompt = load_agent_prompt()
        await voice_chat_loop(
            client=client,
            registry=tool_registry,
            conversation_service=conversation_service,
            event_queue=event_queue,
            system_prompt=system_prompt,
        )


def run_voice_cli() -> None:
    asyncio.run(main())
