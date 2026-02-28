"""Voice chat interface — STT → Agent → TTS using ElevenLabs."""

import asyncio
import io
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import anthropic
import numpy as np
import sounddevice as sd
import soundfile as sf
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.live import Live

from max_ai.agent import run
from max_ai.config import settings
from max_ai.monitoring.langwatch import setup_langwatch, trace_turn
from max_ai.persistence import ConversationStore
from max_ai.prompts import load_prompt
from max_ai.tools.registry import ToolRegistry
from max_ai.voice.recorder import record_until_enter
from max_ai.voice.stt import transcribe
from max_ai.voice.tts import speak

console = Console()

_DEBUG_DIR = Path.home() / ".max-ai" / "debug"
_TTS_SAMPLE_RATE = 22050


def _get_spotify_volume() -> int | None:
    """Return current Spotify volume (0–100), or None if unavailable."""
    try:
        from max_ai.tools.spotify import _get_spotify
        sp = _get_spotify()
        playback = sp.current_playback()
        if playback and "device" in playback:
            return playback["device"].get("volume_percent")
    except Exception:
        pass
    return None


def _set_spotify_volume(level: int) -> None:
    """Set Spotify volume, silently ignoring errors."""
    try:
        from max_ai.tools.spotify import _get_spotify
        sp = _get_spotify()
        sp.volume(level)
    except Exception:
        pass


def _save_debug_files(wav_bytes: bytes, pcm_bytes: bytes, stamp: str) -> None:
    """Save input WAV and output PCM as WAV to the debug directory."""
    _DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    input_path = _DEBUG_DIR / f"{stamp}_input.wav"
    input_path.write_bytes(wav_bytes)

    output_path = _DEBUG_DIR / f"{stamp}_output.wav"
    audio = np.frombuffer(pcm_bytes, dtype=np.int16)
    buf = io.BytesIO()
    sf.write(buf, audio, _TTS_SAMPLE_RATE, format="WAV", subtype="PCM_16")
    output_path.write_bytes(buf.getvalue())

    console.print(f"[dim]Debug audio saved to {_DEBUG_DIR}/{stamp}_{{input,output}}.wav[/]")


async def _wait_for_enter() -> None:
    """Wait for Enter using the event-loop reader — cancellable, no orphaned threads."""
    loop = asyncio.get_event_loop()
    fut: asyncio.Future[None] = loop.create_future()

    def _cb() -> None:
        sys.stdin.readline()  # consume the newline
        if not fut.done():
            fut.set_result(None)

    loop.add_reader(sys.stdin.fileno(), _cb)
    try:
        await fut
    finally:
        loop.remove_reader(sys.stdin.fileno())


SYSTEM_PROMPT = load_prompt("system") + "\n\n" + load_prompt("voice")


async def voice_chat_loop(
    client: anthropic.AsyncAnthropic,
    registry: ToolRegistry,
    store: ConversationStore,
) -> None:
    if not settings.elevenlabs_api_key:
        console.print("[red]Error:[/] MAX_AI_ELEVENLABS_API_KEY is not set. Add it to your .env file.")
        return

    conv_id = await store.create_conversation()
    messages: list[dict[str, Any]] = []

    console.print(
        Panel(
            "[bold cyan]max-ai voice[/] — Personal AI Agent\n"
            "[dim]Press [bold]Enter[/] to start recording, [bold]Enter[/] again to send\n"
            "[bold]Ctrl+C[/] to quit[/]",
            border_style="cyan",
        )
    )

    auto_start = False  # set True when user interrupts TTS mid-playback

    while True:
        # Prompt user to start recording (skipped when auto-starting after interrupt)
        if not auto_start:
            try:
                console.print("\n[dim]Press [bold]Enter[/] to record…[/]", end="")
                await asyncio.to_thread(input)
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Goodbye.[/]")
                break
        else:
            auto_start = False

        # Duck Spotify volume while recording
        prev_volume: int | None = None
        if settings.spotify_client_id and settings.spotify_client_secret:
            prev_volume = await asyncio.to_thread(_get_spotify_volume)
            if prev_volume is not None:
                await asyncio.to_thread(_set_spotify_volume, 20)

        # Record audio
        console.print("[bold yellow]● Recording[/] — press [bold]Enter[/] to stop…")
        try:
            wav_bytes = await asyncio.to_thread(record_until_enter)
        except Exception as e:
            if prev_volume is not None:
                await asyncio.to_thread(_set_spotify_volume, prev_volume)
            console.print(f"[red]Recording error:[/] {e}")
            continue

        # Restore Spotify volume after recording
        if prev_volume is not None:
            await asyncio.to_thread(_set_spotify_volume, prev_volume)

        # Transcribe
        with Live(Spinner("dots", text=" [dim]Transcribing…[/]"), console=console, transient=True):
            try:
                user_text = await transcribe(
                    wav_bytes,
                    api_key=settings.elevenlabs_api_key,
                    model_id=settings.elevenlabs_stt_model,
                )
            except Exception as e:
                console.print(f"[red]STT error:[/] {e}")
                continue

        if not user_text:
            console.print("[dim]No speech detected, try again.[/]")
            continue

        console.print(f"\n[bold green]You[/] {user_text}")

        # Persist and append to history
        messages.append({"role": "user", "content": user_text})
        await store.append_message(conv_id, "user", user_text)

        # Run agent
        response_chunks: list[str] = []
        try:
            with Live(Spinner("dots", text=" [dim]Thinking…[/]"), console=console, transient=True) as live:
                def on_tool_use(names: list[str]) -> None:
                    label = ", ".join(names)
                    live.update(Spinner("dots", text=f" [dim]⚙ {label}…[/]"))

                async for chunk in trace_turn(
                    run(client, registry, messages, SYSTEM_PROMPT, on_tool_use=on_tool_use),
                    user_input=user_text,
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

        # Display response
        console.print("\n[bold blue]Max[/]")
        console.print(Markdown(full_response))

        # Persist
        await store.append_message(conv_id, "assistant", full_response)

        # Speak response — Enter interrupts playback and auto-starts next recording
        pcm_bytes = b""
        console.print("[dim]  ● Speaking — press [bold]Enter[/] to interrupt…[/]")
        speak_task = asyncio.create_task(
            speak(
                full_response,
                api_key=settings.elevenlabs_api_key,
                voice_id=settings.elevenlabs_voice_id,
                model_id=settings.elevenlabs_tts_model,
            )
        )
        interrupt_task = asyncio.create_task(_wait_for_enter())
        try:
            done, _ = await asyncio.wait(
                {speak_task, interrupt_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
        except (KeyboardInterrupt, asyncio.CancelledError):
            sd.stop()
            speak_task.cancel()
            interrupt_task.cancel()
            for t in (speak_task, interrupt_task):
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
            raise

        if interrupt_task in done and speak_task not in done:
            # User interrupted mid-playback
            sd.stop()
            speak_task.cancel()
            try:
                await speak_task
            except (asyncio.CancelledError, Exception):
                pass
            auto_start = True
            console.print("[dim]Interrupted.[/]")
        else:
            # TTS completed naturally — cancel the Enter watcher
            interrupt_task.cancel()
            try:
                await interrupt_task
            except asyncio.CancelledError:
                pass
            try:
                pcm_bytes = speak_task.result()
            except Exception as e:
                console.print(f"[yellow]TTS error (response shown above):[/] {e}")

        # Save debug audio if enabled
        if settings.debug and pcm_bytes:
            stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
            await asyncio.to_thread(_save_debug_files, wav_bytes, pcm_bytes, stamp)


async def main() -> None:
    from max_ai.client import create_client
    from max_ai.tools.documents import DocumentTools
    from max_ai.tools.spotify import SpotifyTools

    setup_langwatch()

    store = ConversationStore()
    await store.init_db()

    from max_ai.persistence import DocumentStore
    doc_store = DocumentStore()
    await doc_store.init_db()

    client = create_client()

    registry = ToolRegistry()
    registry.register(DocumentTools(doc_store))
    if settings.spotify_client_id and settings.spotify_client_secret:
        registry.register(SpotifyTools())

    await voice_chat_loop(client, registry, store)
    await store.close()


def run_voice_cli() -> None:
    asyncio.run(main())
