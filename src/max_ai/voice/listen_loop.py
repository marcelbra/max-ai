"""Always-listening voice loop with wake word detection."""

import asyncio
from typing import Any

import anthropic
from rich.console import Console
from rich.panel import Panel

from max_ai.agent import Agent
from max_ai.config import settings
from max_ai.db import ConversationService
from max_ai.tools.registry import ToolRegistry
from max_ai.tools.search import AnthropicWebSearch
from max_ai.voice.loop import _run_agent_turn
from max_ai.voice.state_machine import AssistantState, StateMachine
from max_ai.voice.transcribe import DeepgramTranscriber
from max_ai.voice.vad import VoiceActivityDetector
from max_ai.voice.wakeword import WakeWordDetector

console = Console()


async def voice_listen_loop(
    client: anthropic.AsyncAnthropic,
    registry: ToolRegistry,
    conversation_service: ConversationService,
    event_queue: asyncio.Queue[dict[str, Any]],
    system_prompt: str,
) -> None:
    """Run the always-listening wake word detection loop."""
    if not settings.picovoice_access_key:
        console.print(
            "[red]Error:[/] MAX_AI_PICOVOICE_ACCESS_KEY is not set. Add it to your .env file."
        )
        return
    if not settings.deepgram_api_key:
        console.print(
            "[red]Error:[/] MAX_AI_DEEPGRAM_API_KEY is not set. Add it to your .env file."
        )
        return
    if not settings.elevenlabs_api_key:
        console.print(
            "[red]Error:[/] MAX_AI_ELEVENLABS_API_KEY is not set. Add it to your .env file."
        )
        return

    state_machine = StateMachine()
    wake_detector = WakeWordDetector(
        access_key=settings.picovoice_access_key,
        keyword_path=settings.porcupine_keyword_path,
    )
    vad = VoiceActivityDetector(silence_threshold_ms=settings.vad_silence_threshold_ms)
    transcriber = DeepgramTranscriber(api_key=settings.deepgram_api_key)

    audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
    frame_buffer = bytearray()
    accumulated_transcript = ""
    utterance_done_event = asyncio.Event()

    main_loop = asyncio.get_event_loop()

    web_search_tool = (
        AnthropicWebSearch(settings.web_search_max_uses) if settings.enable_web_search else None
    )
    agent = Agent(client, registry, system_prompt, web_search_tool=web_search_tool)
    conv_id = await conversation_service.create_conversation()

    def _on_audio(indata: Any, frames: int, time_info: Any, status: Any) -> None:
        main_loop.call_soon_threadsafe(audio_queue.put_nowait, bytes(indata))

    async def _handle_utterance_end() -> None:
        nonlocal accumulated_transcript
        if not accumulated_transcript.strip():
            await transcriber.stop()
            state_machine.transition(AssistantState.IDLE)
            return

        await transcriber.stop()
        state_machine.transition(AssistantState.PROCESSING)

        full_response = await _run_agent_turn(agent, accumulated_transcript, conv_id)
        await conversation_service.append_message(conv_id, "user", accumulated_transcript)
        accumulated_transcript = ""

        if full_response:
            await conversation_service.append_message(conv_id, "assistant", full_response)
            state_machine.transition(AssistantState.SPEAKING)
            from max_ai.voice.tts import speak  # lazy: optional dep

            await speak(
                full_response,
                api_key=settings.elevenlabs_api_key,
                voice_id=settings.elevenlabs_voice_id,
                model_id=settings.elevenlabs_tts_model,
                output_device=settings.tts_output_device,
            )
            state_machine.on_tts_complete()
        else:
            state_machine.transition(AssistantState.IDLE)

    console.print(
        Panel(
            "[bold cyan]max-ai wake word[/] — Always-listening mode\n"
            "[dim]Say [bold]'hey max'[/] to activate, then speak your request[/]",
            border_style="cyan",
        )
    )

    import sounddevice as sd  # lazy: optional dep (but declared in main deps)

    with sd.InputStream(
        samplerate=wake_detector.sample_rate,
        channels=1,
        dtype="int16",
        blocksize=wake_detector.frame_length,
        device=settings.voice_input_device,
        callback=_on_audio,
    ):
        console.print("[dim]Listening for wake word…[/]")

        while True:
            audio_task: asyncio.Task[bytes] = asyncio.create_task(audio_queue.get())
            event_task: asyncio.Task[dict[str, Any]] = asyncio.create_task(event_queue.get())

            done, _ = await asyncio.wait(
                {audio_task, event_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            if audio_task in done:
                event_task.cancel()
                chunk = audio_task.result()
                current_state = state_machine.state

                if current_state == AssistantState.IDLE:
                    frame_buffer.extend(chunk)
                    frame_size = wake_detector.frame_length * 2  # bytes (int16 = 2 bytes)
                    while len(frame_buffer) >= frame_size:
                        frame = bytes(frame_buffer[:frame_size])
                        del frame_buffer[:frame_size]
                        if wake_detector.process(frame):
                            console.print("[bold yellow]Wake word detected![/] Listening…")
                            state_machine.transition(AssistantState.LISTENING)
                            vad.reset()
                            accumulated_transcript = ""
                            utterance_done_event.clear()

                            def _on_transcript(text: str, is_final: bool) -> None:
                                nonlocal accumulated_transcript
                                if is_final:
                                    accumulated_transcript = text

                            def _on_utterance_end() -> None:
                                main_loop.call_soon_threadsafe(utterance_done_event.set)

                            await transcriber.start(
                                on_transcript=_on_transcript,
                                on_utterance_end=_on_utterance_end,
                            )
                            frame_buffer.clear()
                            break

                elif current_state == AssistantState.LISTENING:
                    await transcriber.send(chunk)
                    silence_exceeded = vad.update(chunk)
                    if silence_exceeded or utterance_done_event.is_set():
                        utterance_done_event.clear()
                        await _handle_utterance_end()

            else:
                audio_task.cancel()
                event = event_task.result()
                if state_machine.state == AssistantState.IDLE:
                    console.print("\n[bold yellow]◆ Background event[/]")
                    event_text = event["content"]
                    state_machine.transition(AssistantState.PROCESSING)
                    full_response = await _run_agent_turn(agent, event_text, conv_id)
                    if full_response:
                        state_machine.transition(AssistantState.SPEAKING)
                        from max_ai.voice.tts import speak  # lazy: optional dep

                        await speak(
                            full_response,
                            api_key=settings.elevenlabs_api_key,
                            voice_id=settings.elevenlabs_voice_id,
                            model_id=settings.elevenlabs_tts_model,
                            output_device=settings.tts_output_device,
                        )
                        state_machine.on_tts_complete()
                    else:
                        state_machine.transition(AssistantState.IDLE)
