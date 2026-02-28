"""Rich-based chat interface for max-ai."""

import asyncio
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich.live import Live

import anthropic

from max_ai.agent import run
from max_ai.config import settings
from max_ai.monitoring.langwatch import setup_langwatch, trace_turn
from max_ai.persistence import ConversationStore
from max_ai.prompts import load_prompt
from max_ai.tools.registry import ToolRegistry

console = Console()

SYSTEM_PROMPT = load_prompt("system")

HELP_TEXT = """\
Commands:
  /new      — Start a new conversation
  /history  — List recent conversations
  /help     — Show this help
  /exit     — Quit
"""


async def chat_loop(
    client: anthropic.AsyncAnthropic,
    registry: ToolRegistry,
    store: ConversationStore,
) -> None:
    conv_id = await store.create_conversation()
    messages: list[dict[str, Any]] = []

    console.print(
        Panel(
            "[bold cyan]max-ai[/] — Personal AI Agent\n"
            "[dim]Type [bold]/help[/] for commands, [bold]Ctrl+C[/] to quit[/]",
            border_style="cyan",
        )
    )

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]You[/]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/]")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            console.print("[dim]Goodbye.[/]")
            break

        # Handle slash commands
        if user_input.startswith("/"):
            cmd = user_input.lower().split()[0]

            if cmd in ("/exit", "/quit"):
                console.print("[dim]Goodbye.[/]")
                break

            elif cmd == "/new":
                conv_id = await store.create_conversation()
                messages = []
                console.print("[dim]New conversation started.[/]")
                continue

            elif cmd == "/history":
                convs = await store.list_conversations()
                if not convs:
                    console.print("[dim]No conversations yet.[/]")
                else:
                    for c in convs:
                        title = c["title"] or "[untitled]"
                        console.print(f"  [dim]{c['created_at'][:19]}[/]  {c['id'][:8]}  {title}")
                continue

            elif cmd == "/help":
                console.print(HELP_TEXT)
                continue

            else:
                console.print(f"[red]Unknown command:[/] {cmd}. Type [bold]/help[/].")
                continue

        # Append user message and persist
        messages.append({"role": "user", "content": user_input})
        await store.append_message(conv_id, "user", user_input)

        # Run agent with spinner
        response_chunks: list[str] = []
        tool_names_used: list[str] = []

        try:
            with Live(Spinner("dots", text=" [dim]Thinking…[/]"), console=console, transient=True) as live:
                def on_tool_use(names: list[str]) -> None:
                    label = ", ".join(names)
                    live.update(Spinner("dots", text=f" [dim]⚙ {label}…[/]"))

                async for chunk in trace_turn(
                    run(client, registry, messages, SYSTEM_PROMPT, on_tool_use=on_tool_use),
                    user_input=user_input,
                    thread_id=conv_id,
                ):
                    response_chunks.append(chunk)

        except anthropic.APIError as e:
            console.print(f"[red]API error:[/] {e}")
            continue
        except Exception as e:
            console.print(f"[red]Error:[/] {e}")
            continue

        full_response = "".join(response_chunks)

        # Print response
        console.print("\n[bold blue]Max[/]")
        console.print(Markdown(full_response))

        # Persist assistant response
        await store.append_message(conv_id, "assistant", full_response)

        # Update messages with the final assistant text for next turn
        # (agent loop already appended intermediate turns to `messages`)
        # The last item in messages is the last tool_result or assistant turn;
        # if the agent ended normally the assistant text is already there.


async def main() -> None:
    from max_ai.client import create_client
    from max_ai.tools.spotify import SpotifyTools

    setup_langwatch()

    store = ConversationStore()
    await store.init_db()

    client = create_client()

    registry = ToolRegistry()
    if settings.spotify_client_id and settings.spotify_client_secret:
        registry.register(SpotifyTools())

    await chat_loop(client, registry, store)
    await store.close()


def run_cli() -> None:
    asyncio.run(main())
