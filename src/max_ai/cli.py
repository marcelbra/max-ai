"""Entry point for the max-ai voice CLI."""

import asyncio
from typing import Any

from max_ai.agent import load_agent_prompt
from max_ai.agent.tools.registry import ToolRegistry
from max_ai.monitoring.langwatch import setup_langwatch
from max_ai.persistence import ConversationStore
from max_ai.voice.loop import voice_chat_loop


async def main() -> None:
    from max_ai.agent.tools.documents import DocumentTools
    from max_ai.agent.tools.spotify import SpotifyTools
    from max_ai.agent.tools.timer import TimerTool
    from max_ai.client import create_client
    from max_ai.config import settings

    setup_langwatch()

    store = ConversationStore()
    await store.init_db()

    from max_ai.persistence import DocumentStore

    doc_store = DocumentStore()
    await doc_store.init_db()

    client = create_client()

    from max_ai.agent.tools.calendar import CalendarTools

    registry = ToolRegistry()
    registry.register(DocumentTools(doc_store))
    registry.register(CalendarTools())

    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    registry.register(TimerTool(event_queue))

    if settings.spotify_client_id and settings.spotify_client_secret:
        registry.register(SpotifyTools())

    system_prompt = load_agent_prompt()
    await voice_chat_loop(client, registry, store, event_queue, system_prompt)

    await store.close()


def run_voice_cli() -> None:
    asyncio.run(main())
