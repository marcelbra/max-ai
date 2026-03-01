"""Voice chat loop and supporting helpers."""

import asyncio
import queue
import sys
import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any

import anthropic
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner

from max_ai.agent import Agent
from max_ai.config import settings
from max_ai.db import ConversationService
from max_ai.monitoring.langwatch import trace_turn
from max_ai.tools.registry import ToolRegistry
from max_ai.tools.search import AnthropicWebSearch
from max_ai.voice.debug import save_debug_files

console = Console()


# ---------------------------------------------------------------------------
# Spotify volume ducking
# ---------------------------------------------------------------------------


def _get_spotify_volume() -> int | None:
    """Return current Spotify volume (0–100), or None if unavailable."""
    try:
        from max_ai.tools.spotify import _get_spotify

        sp = _get_spotify()
        playback = sp.current_playback()
        if playback and "device" in playback:
            return playback["device"].get("volume_percent")  # type: ignore[no-any-return]
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


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------


async def _wait_for_key() -> str:
    """Wait for Enter or 'x'. Returns 'enter' or 'x'. Cancellation-safe, no orphaned threads."""
    import termios
    import tty

    loop = asyncio.get_event_loop()
    fut: asyncio.Future[str] = loop.create_future()

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)

    def _on_key_press() -> None:
        ch = sys.stdin.read(1)
        if ch in ("\n", "\r"):
            if not fut.done():
                fut.set_result("enter")
        elif ch.lower() == "x":
            if not fut.done():
                fut.set_result("x")

    loop.add_reader(fd, _on_key_press)
    try:
        return await fut
    finally:
        loop.remove_reader(fd)
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


# ---------------------------------------------------------------------------
# Agent and TTS helpers
# ---------------------------------------------------------------------------


async def _run_agent_turn(
    agent: Agent,
    user_text: str,
    conv_id: str,
) -> str | None:
    """Run one agent turn and return the full response text, or None on error."""
    response_chunks: list[str] = []
    try:
        with Live(
            Spinner("dots", text=" [dim]Thinking…[/]"), console=console, transient=True
        ) as live:

            def on_tool_use(names: list[str]) -> None:
                label = ", ".join(names)
                live.update(Spinner("dots", text=f" [dim]⚙ {label}…[/]"))

            async for chunk in trace_turn(
                agent.run(user_text, on_tool_use=on_tool_use),
                user_input=user_text,
                thread_id=conv_id,
                system=agent.system,
            ):
                response_chunks.append(chunk)
    except anthropic.APIError as e:
        console.print(f"[red]API error:[/] {e}")
        return None
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        return None
    return "".join(response_chunks)


async def _speak_and_handle_interrupt(full_response: str) -> tuple[bool, bool, bytes]:
    """Speak a response and handle user interrupts.

    Returns ``(quit, auto_start, pcm_bytes)``.
    """
    from max_ai.voice.tts import speak

    tts_stop = threading.Event()
    console.print("[dim]  ● Speaking — press [bold]Enter[/] to interrupt, [bold]x[/] to quit…[/]")
    speak_task = asyncio.create_task(
        speak(
            full_response,
            api_key=settings.elevenlabs_api_key,
            voice_id=settings.elevenlabs_voice_id,
            model_id=settings.elevenlabs_tts_model,
            stop_event=tts_stop,
            output_device=settings.tts_output_device,
        )
    )
    interrupt_task = asyncio.create_task(_wait_for_key())
    try:
        done, _ = await asyncio.wait(
            {speak_task, interrupt_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        tts_stop.set()
        speak_task.cancel()
        interrupt_task.cancel()
        for t in (speak_task, interrupt_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        raise

    if interrupt_task in done and speak_task not in done:
        key = interrupt_task.result()
        tts_stop.set()
        try:
            await speak_task
        except (asyncio.CancelledError, Exception):
            pass
        if key == "x":
            console.print("[dim]Goodbye.[/]")
            return True, False, b""
        console.print("[dim]Interrupted.[/]")
        return False, True, b""

    interrupt_task.cancel()
    try:
        await interrupt_task
    except asyncio.CancelledError:
        pass
    pcm_bytes = b""
    try:
        pcm_bytes = speak_task.result()
    except Exception as e:
        console.print(f"[yellow]TTS error (response shown above):[/] {e}")
    return False, False, pcm_bytes


# ---------------------------------------------------------------------------
# Deepgram streaming transcription helper
# ---------------------------------------------------------------------------


async def _transcribe_with_deepgram(
    deepgram_api_key: str,
    voice_input_device: int | None,
    on_recording_started: Callable[[], None],
) -> tuple[bytes, str]:
    """Stream audio to Deepgram during push-to-talk recording.

    Returns ``(wav_bytes, transcript)`` where ``wav_bytes`` is the processed WAV
    from the recorder and ``transcript`` is the accumulated final-segment text.

    Raises ``VoiceExit`` if the user presses 'x', or re-raises any recording
    exception so the caller can handle Spotify volume restore and loop control.
    """
    from max_ai.voice.recorder import record_until_enter
    from max_ai.voice.transcribe import DeepgramTranscriber

    final_segments: list[str] = []
    utterance_end_event = asyncio.Event()
    chunk_queue: queue.Queue[bytes | None] = queue.Queue()

    def on_transcript(text: str, is_final: bool) -> None:
        if is_final and text:
            final_segments.append(text)

    def on_utterance_end() -> None:
        utterance_end_event.set()

    transcriber = DeepgramTranscriber(deepgram_api_key)
    await transcriber.start(on_transcript=on_transcript, on_utterance_end=on_utterance_end)

    async def _forward_chunks() -> None:
        while True:
            audio_bytes = await asyncio.to_thread(chunk_queue.get)
            if audio_bytes is None:
                break
            await transcriber.send(audio_bytes)

    forward_task = asyncio.create_task(_forward_chunks())

    def _put_chunk(audio_bytes: bytes) -> None:
        chunk_queue.put(audio_bytes)

    try:
        wav_bytes = await asyncio.to_thread(
            record_until_enter, 16000, voice_input_device, on_recording_started, _put_chunk
        )
    except Exception:
        chunk_queue.put(None)
        await forward_task
        await transcriber.stop()
        raise

    chunk_queue.put(None)
    await forward_task
    await transcriber.stop()

    try:
        await asyncio.wait_for(utterance_end_event.wait(), timeout=1.5)
    except TimeoutError:
        pass

    return wav_bytes, " ".join(segment for segment in final_segments if segment)


# ---------------------------------------------------------------------------
# Voice loop
# ---------------------------------------------------------------------------


async def voice_chat_loop(
    client: anthropic.AsyncAnthropic,
    registry: ToolRegistry,
    conversation_service: ConversationService,
    event_queue: asyncio.Queue[dict[str, Any]],
    system_prompt: str,
) -> None:
    from max_ai.voice.recorder import VoiceExit, record_until_enter
    from max_ai.voice.stt import transcribe

    if not settings.elevenlabs_api_key:
        console.print(
            "[red]Error:[/] MAX_AI_ELEVENLABS_API_KEY is not set. Add it to your .env file."
        )
        return

    if settings.deepgram_api_key:
        try:
            import deepgram as _  # noqa: F401
        except ImportError:
            console.print(
                "[red]Error:[/] deepgram-sdk is not installed. Run: uv sync --extra wake-word"
            )
            return

    conv_id = await conversation_service.create_conversation()
    web_search_tool = (
        AnthropicWebSearch(settings.web_search_max_uses) if settings.enable_web_search else None
    )
    agent = Agent(client, registry, system_prompt, web_search_tool=web_search_tool)

    console.print(
        Panel(
            "[bold cyan]max-ai voice[/] — Personal AI Agent\n"
            "[dim]Press [bold]Enter[/] to start recording, [bold]Enter[/] again to send\n"
            "[bold]x[/] to quit at any time[/]",
            border_style="cyan",
        )
    )

    auto_start = False
    injected_text: str | None = None

    while True:
        wav_bytes = b""

        if injected_text is None and not auto_start:
            try:
                console.print(
                    "\n[dim]Press [bold]Enter[/] to record, [bold]x[/] to quit…[/]", end=""
                )
                key_task = asyncio.create_task(_wait_for_key())
                queue_task: asyncio.Task[dict[str, Any]] = asyncio.create_task(event_queue.get())
                done, _ = await asyncio.wait(
                    {key_task, queue_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if key_task in done:
                    queue_task.cancel()
                    key = key_task.result()
                    if key == "x":
                        console.print("\n[dim]Goodbye.[/]")
                        break
                else:
                    key_task.cancel()
                    event = queue_task.result()
                    console.print("\n[bold yellow]◆ Background event[/]")
                    injected_text = event["content"]
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Goodbye.[/]")
                break
        else:
            auto_start = False

        user_text = ""
        if injected_text is not None:
            user_text = injected_text
            injected_text = None
        else:
            # Duck Spotify volume while recording
            prev_volume: int | None = None
            if settings.spotify_client_id and settings.spotify_client_secret:
                prev_volume = await asyncio.to_thread(_get_spotify_volume)
                if prev_volume is not None:
                    await asyncio.to_thread(_set_spotify_volume, 20)

            console.print("[dim]Preparing microphone…[/]", end="\r")

            def _on_recording_started() -> None:
                console.print(
                    "[bold yellow]● Recording[/] — press [bold]Enter[/] to stop,"
                    " [bold]x[/] to quit…"
                )

            if settings.deepgram_api_key:
                try:
                    wav_bytes, user_text = await _transcribe_with_deepgram(
                        settings.deepgram_api_key,
                        settings.voice_input_device,
                        _on_recording_started,
                    )
                except VoiceExit:
                    if prev_volume is not None:
                        await asyncio.to_thread(_set_spotify_volume, prev_volume)
                    console.print("\n[dim]Goodbye.[/]")
                    break
                except Exception as e:
                    if prev_volume is not None:
                        await asyncio.to_thread(_set_spotify_volume, prev_volume)
                    console.print(f"[red]Recording error:[/] {e}")
                    continue

                if prev_volume is not None:
                    await asyncio.to_thread(_set_spotify_volume, prev_volume)
            else:
                try:
                    wav_bytes = await asyncio.to_thread(
                        record_until_enter,
                        16000,
                        settings.voice_input_device,
                        _on_recording_started,
                    )
                except VoiceExit:
                    if prev_volume is not None:
                        await asyncio.to_thread(_set_spotify_volume, prev_volume)
                    console.print("\n[dim]Goodbye.[/]")
                    break
                except Exception as e:
                    if prev_volume is not None:
                        await asyncio.to_thread(_set_spotify_volume, prev_volume)
                    console.print(f"[red]Recording error:[/] {e}")
                    continue

                if prev_volume is not None:
                    await asyncio.to_thread(_set_spotify_volume, prev_volume)

                with Live(
                    Spinner("dots", text=" [dim]Transcribing…[/]"), console=console, transient=True
                ):
                    try:
                        user_text = await transcribe(
                            wav_bytes,
                            api_key=settings.elevenlabs_api_key,
                            model_id=settings.elevenlabs_stt_model,
                            language_code=settings.elevenlabs_stt_language,
                        )
                    except Exception as e:
                        console.print(f"[red]STT error:[/] {e}")
                        continue

            if not user_text:
                console.print("[dim]No speech detected, try again.[/]")
                continue

        console.print(f"\n[bold green]You[/] {user_text}")
        await conversation_service.append_message(conv_id, "user", user_text)

        full_response = await _run_agent_turn(agent, user_text, conv_id)
        if full_response is None:
            continue

        console.print("\n[bold blue]Max[/]")
        console.print(Markdown(full_response))
        await conversation_service.append_message(conv_id, "assistant", full_response)

        quit, should_auto_start, pcm_bytes = await _speak_and_handle_interrupt(full_response)
        if quit:
            break
        auto_start = should_auto_start

        if settings.debug and pcm_bytes and wav_bytes:
            stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
            await asyncio.to_thread(save_debug_files, wav_bytes, pcm_bytes, stamp)
