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

    store = ConversationService()
    await store.init_db()

    doc_store = DocumentService()
    await doc_store.init_db()

    client = create_client()

    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    use_spotify = settings.spotify_client_id and settings.spotify_client_secret

    tool_registry = ToolRegistry()

    tool_registry.register(DocumentTools(doc_store))
    tool_registry.register(CalendarTools())
    tool_registry.register(TimerTool(event_queue))
    tool_registry.register(AlarmTool())
    if use_spotify:
        tool_registry.register(SpotifyTools())

    system_prompt = load_agent_prompt()
    await voice_chat_loop(
        client=client,
        registry=tool_registry,
        store=store,
        event_queue=event_queue,
        system_prompt=system_prompt,
    )

    await store.close()


def run_voice_cli() -> None:
    asyncio.run(main())
