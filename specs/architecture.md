# Voice Assistant Architecture

**Status:** Canonical — supersedes all previous feature specs
**Replaces:** `feature-1-wake-word.md`, `feature-1a-deepgram-transcription.md`, `feature-2-free-order-of-actions.md`, `always-listening.md`

---

## Core Principle

**One event bus. One orchestrator that transitions state. Everything else is a component.**

The orchestrator's main loop never awaits long operations. Anything that takes time (agent turn, TTS playback) is fired as a background task that puts a result event on the bus when done.

---

## 1. Typed Event Catalog

All events are frozen dataclasses. The `Event` union is the only type that flows through the bus.

```python
# voice/events.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal, Union


@dataclass(frozen=True)
class AudioFrame:
    data: bytes


@dataclass(frozen=True)
class WakeWordDetected:
    pass


@dataclass(frozen=True)
class TranscriptPartial:
    text: str


@dataclass(frozen=True)
class TranscriptFinal:
    text: str


@dataclass(frozen=True)
class UtteranceEnd:
    transcript: str


@dataclass(frozen=True)
class AgentText:
    text: str


@dataclass(frozen=True)
class AgentDone:
    next_state: Literal["idle", "listening"] | None


@dataclass(frozen=True)
class TTSDone:
    pass


@dataclass(frozen=True)
class TimerFired:
    message: str


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    result: str


@dataclass(frozen=True)
class StateChanged:
    previous: AssistantState
    current: AssistantState


Event = Union[
    AudioFrame,
    WakeWordDetected,
    TranscriptPartial,
    TranscriptFinal,
    UtteranceEnd,
    AgentText,
    AgentDone,
    TTSDone,
    TimerFired,
    TaskResult,
    StateChanged,
]

EventBus = asyncio.Queue[Event]
```

### AssistantState

```python
# voice/events.py (continued)
from enum import Enum

class AssistantState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
```

---

## 2. Component Interfaces

Seven components. Each has a single, clear contract.

| Component | File | Produces events | Invoked by |
|---|---|---|---|
| `AudioCapture` | `voice/audio_capture.py` | `AudioFrame` | Orchestrator (started once) |
| `WakeWordDetector` | `voice/wakeword.py` | `WakeWordDetected` | Orchestrator (feeds `AudioFrame`) |
| `StreamingTranscriber` | `voice/transcribe.py` | `TranscriptPartial`, `UtteranceEnd` | Orchestrator (start/send/stop) |
| `Orchestrator` | `voice/orchestrator.py` | `StateChanged` | Entry point (`cli.py`) |
| `Agent` | `agent/agent.py` | `AgentText`, `AgentDone` | Orchestrator (via background task) |
| `TTSPlayer` | `voice/tts.py` | `TTSDone` | Orchestrator (via background task) |
| `Display` | `voice/display.py` | — | Orchestrator (direct call) |

### AudioCapture

```python
class AudioCapture:
    @contextlib.asynccontextmanager
    async def running(self, bus: EventBus) -> AsyncIterator[None]:
        """Start the sounddevice InputStream. Yield. Stop on exit."""
```

### WakeWordDetector

```python
class WakeWordDetector:
    def __init__(self, access_key: str, keyword_path: str = "") -> None: ...

    def process(self, audio_frame: bytes) -> bool:
        """Feed exactly frame_length int16 samples. Returns True on detection."""

    @property
    def frame_length(self) -> int: ...   # typically 512

    @property
    def sample_rate(self) -> int: ...    # always 16000

    def close(self) -> None: ...
```

Lazy import: `import pvporcupine` inside `__init__`.

### StreamingTranscriber

```python
class StreamingTranscriber:
    async def start(self, bus: EventBus) -> None:
        """Open Deepgram WebSocket. Puts TranscriptPartial and UtteranceEnd onto bus."""

    async def send(self, audio_chunk: bytes) -> None:
        """Send raw int16 PCM bytes to the open connection."""

    async def stop(self) -> None:
        """Close the connection. Safe to call multiple times."""
```

Lazy import: `from deepgram import ...` inside `start()`.

### Agent

```python
class Agent:
    next_state: str | None  # reset to None at start of every run()

    async def run(self, message: str) -> AsyncIterator[AgentText | AgentDone]:
        """
        Yield AgentText for each text block streamed.
        Yield AgentDone(next_state=self.next_state) at end_turn.
        No awareness of audio, TTS, or display.
        """
```

### TTSPlayer

```python
class TTSPlayer:
    async def speak(self, text: str, stop_event: asyncio.Event) -> None:
        """Play TTS audio. Returns when done or stop_event is set."""
```

### Display (Protocol)

```python
class Display(Protocol):
    def on_state_change(self, previous: AssistantState, current: AssistantState) -> None: ...
    def on_agent_text(self, text: str) -> None: ...
    def on_tool_use(self, tool_names: list[str]) -> None: ...
```

Terminal implementation shows one-line status:
- `○ idle` — waiting for wake word
- `● listening…` — capturing audio
- `⟳ thinking…` — agent running
- `◆ speaking…` — TTS playing

Swappable: Feature 4's WebSocket UI implements the same Protocol.

---

## 3. Orchestrator State Table

The heart of the design. Every meaningful event × state combination is defined.

| Event | `IDLE` | `LISTENING` | `PROCESSING` | `SPEAKING` |
|---|---|---|---|---|
| `AudioFrame` | Feed to WakeWordDetector | Feed to Transcriber | discard | discard |
| `WakeWordDetected` | → **LISTENING**; start transcriber; reset VAD | ignore | ignore | ignore |
| `UtteranceEnd(t)` | — | if `len(t.split()) < min_words` → **IDLE**; else → **PROCESSING**, spawn agent task | ignore | queue for after SPEAKING |
| `AgentText(text)` | — | — | accumulate in response buffer | — |
| `AgentDone(next)` | — | — | if buffer non-empty → **SPEAKING**, spawn TTS task; else → **IDLE** | — |
| `TTSDone` | — | — | — | `next_state == "listening"` → **LISTENING**; else → **IDLE** |
| `TimerFired(msg)` | → **PROCESSING**, inject message | queue | queue | queue |
| `TaskResult(result)` | → **PROCESSING**, inject message | queue | queue | queue |
| `StateChanged` | passed to Display | passed to Display | passed to Display | passed to Display |

**Queued events** (during PROCESSING/SPEAKING) are replayed in order when the orchestrator returns to IDLE.

---

## 4. Threading Model

sounddevice callbacks run in a C thread. Crossing into asyncio safely:

```python
# voice/audio_capture.py

def _sd_callback(
    indata: npt.NDArray[np.int16],
    frames: int,
    time: Any,
    status: sd.CallbackFlags,
) -> None:
    # Called from C thread — never await here
    loop.call_soon_threadsafe(bus.put_nowait, AudioFrame(data=indata.tobytes()))
```

`call_soon_threadsafe` schedules `put_nowait` to run on the next event loop tick — safe from any thread. No locks needed. `put_nowait` is used (not `await bus.put()`) because we are not in a coroutine.

The asyncio event loop runs in the main thread. The orchestrator loop, agent task, and TTS task all run as coroutines/tasks on that loop. No additional threads are created by the orchestrator.

---

## 5. Orchestrator Loop (non-blocking)

```python
# voice/orchestrator.py

async def run(self) -> None:
    async with self._audio_capture.running(self._bus):
        while True:
            event = await self._bus.get()
            await self._dispatch(event)   # never awaits agent or TTS directly
```

Long operations are always background tasks that post results back to the bus:

```python
# Spawned when UtteranceEnd arrives with enough words:
async def _agent_task(self, transcript: str) -> None:
    async for event in self._agent.run(transcript):   # yields AgentText | AgentDone
        await self._bus.put(event)

# Spawned when AgentDone arrives with accumulated text:
async def _tts_task(self, text: str) -> None:
    await self._tts_player.speak(text, self._tts_stop_event)
    await self._bus.put(TTSDone())
```

`asyncio.create_task()` is used so `_dispatch` returns immediately and the bus stays responsive.

---

## 6. Display Contract

The `Display` Protocol is the only coupling between the orchestrator and the UI. The orchestrator calls display methods synchronously (no await) — display implementations must be non-blocking.

```python
# voice/display.py

class Display(Protocol):
    def on_state_change(self, previous: AssistantState, current: AssistantState) -> None: ...
    def on_agent_text(self, text: str) -> None: ...
    def on_tool_use(self, tool_names: list[str]) -> None: ...


class TerminalDisplay:
    """Single-line status display using Rich."""

    def on_state_change(self, previous: AssistantState, current: AssistantState) -> None:
        icons = {
            AssistantState.IDLE: "○ idle",
            AssistantState.LISTENING: "● listening…",
            AssistantState.PROCESSING: "⟳ thinking…",
            AssistantState.SPEAKING: "◆ speaking…",
        }
        # overwrite current line in terminal

    def on_agent_text(self, text: str) -> None:
        # append to transcript area

    def on_tool_use(self, tool_names: list[str]) -> None:
        # show tool names in status line
```

Feature 4's WebSocket display implements the same Protocol. Swapping display = one constructor argument.

---

## 7. File Layout

### New files to create

| File | Purpose |
|---|---|
| `voice/events.py` | Typed event dataclasses + `Event` union + `AssistantState` enum |
| `voice/audio_capture.py` | sounddevice → EventBus bridge (replaces recorder.py's stream setup) |
| `voice/wakeword.py` | Porcupine wrapper (lazy import of `pvporcupine`) |
| `voice/vad.py` | silero-vad silence detector (lazy import of `torch`) |
| `voice/orchestrator.py` | State machine + event routing (replaces `loop.py`) |
| `voice/display.py` | `Display` Protocol + `TerminalDisplay` implementation |

### Files to modify

| File | Change |
|---|---|
| `agent/agent.py` | Yield `AgentText \| AgentDone` instead of `str`; add `next_state` attr |
| `voice/transcribe.py` | Emit `UtteranceEnd` event onto bus (already close to this shape) |
| `voice/tts.py` | Accept `stop_event: asyncio.Event`; return when done or stopped |
| `cli.py` | Wire up components, pass to `Orchestrator`; remove inline mode detection |
| `config.py` | Add wake-word fields (picovoice key, vad thresholds) |
| `pyproject.toml` | `wake-word` extras group; mypy overrides for `pvporcupine`, `torch` |

### Files to delete / supersede

| File | Reason |
|---|---|
| `voice/loop.py` | Replaced by `orchestrator.py`; push-to-talk becomes a simpler orchestrator config |
| `voice/recorder.py` | Audio capture moves to `audio_capture.py`; denoising to `audio_processing.py` |
| `voice/stt.py` | ElevenLabs batch STT kept as fallback only (no longer primary path) |

### No circular imports

Import graph (arrows = depends on):

```
cli.py
  → orchestrator.py → events.py
  → orchestrator.py → audio_capture.py → events.py
  → orchestrator.py → wakeword.py (lazy pvporcupine)
  → orchestrator.py → vad.py (lazy torch)
  → orchestrator.py → transcribe.py → events.py
  → orchestrator.py → agent/agent.py → events.py
  → orchestrator.py → tts.py
  → orchestrator.py → display.py → events.py
```

`events.py` is the only shared leaf. Nothing in `events.py` imports from other voice modules.

---

## 8. Feature Mapping

How Features 1–4 from the original specs map onto this architecture:

### Feature 1: Wake Word Detection

`WakeWordDetector` in `voice/wakeword.py`. The orchestrator feeds `AudioFrame` events to it in `IDLE` state. On detection it puts `WakeWordDetected` onto the bus and the state table handles the transition.

Push-to-talk mode is a degenerate case: `WakeWordDetector` is replaced by a keyboard listener that puts `WakeWordDetected` on Enter press. Same orchestrator, different trigger.

### Feature 1a: Deepgram Streaming Transcription

`StreamingTranscriber` in `voice/transcribe.py` (already exists, needs minor changes). It receives `AudioFrame` data forwarded by the orchestrator during `LISTENING` state and puts `TranscriptPartial` and `UtteranceEnd` events onto the bus.

### Feature 2: Agent State Control (`set_next_state`)

`Agent.next_state` attribute (set by the `set_next_state` tool during a turn). `AgentDone.next_state` carries this value to the orchestrator. The state table row for `TTSDone` reads it to decide the next state.

### Feature 3: Subagent Spawning

Subagents run as background asyncio tasks and put `TaskResult` events onto the bus when done. The orchestrator's `IDLE` row for `TaskResult` injects the result as a new agent turn. No new components needed — just new event types and one new state table row.

### Feature 4: WebSocket UI (Visual Status Dot)

Implement `Display` Protocol in a WebSocket server class. Pass it to `Orchestrator` instead of `TerminalDisplay`. The orchestrator code is unchanged.

---

## 9. Configuration

New fields in `config.py` (all prefixed `MAX_AI_`):

| Env Var | Default | Description |
|---|---|---|
| `MAX_AI_PICOVOICE_ACCESS_KEY` | `""` | From console.picovoice.ai. Empty = push-to-talk mode. |
| `MAX_AI_PORCUPINE_KEYWORD_PATH` | `""` | Path to custom `.ppn` file. Empty = use built-in keyword. |
| `MAX_AI_DEEPGRAM_API_KEY` | `""` | Already exists. Required for wake-word mode. |
| `MAX_AI_VAD_SILENCE_THRESHOLD_MS` | `1800` | Silence duration before utterance-end fallback fires. |
| `MAX_AI_VAD_MIN_WORDS` | `3` | Minimum words in transcript before passing to agent. |

Mode detection (no CLI flag needed):

```python
# cli.py
if settings.picovoice_access_key and settings.deepgram_api_key:
    wake_word_detector = WakeWordDetector(settings.picovoice_access_key, settings.porcupine_keyword_path)
else:
    wake_word_detector = KeyboardWakeWordDetector()  # push-to-talk

orchestrator = Orchestrator(
    audio_capture=AudioCapture(),
    wake_word_detector=wake_word_detector,
    transcriber=StreamingTranscriber(settings.deepgram_api_key),
    agent=agent,
    tts_player=TTSPlayer(),
    display=TerminalDisplay(),
    config=OrchestratorConfig(min_words=settings.vad_min_words),
)
await orchestrator.run()
```

---

## 10. New Dependencies

| Package | Why | Extras group |
|---|---|---|
| `pvporcupine>=3.0` | Wake word detection | `wake-word` |
| `torch>=2.0` | silero-vad local VAD fallback | `wake-word` |

`deepgram-sdk` and `numpy` already present. Install with `uv sync --extra wake-word`.

New mypy overrides in `pyproject.toml`:

```toml
[[tool.mypy.overrides]]
module = ["pvporcupine", "pvporcupine.*"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["torch", "torch.*"]
ignore_missing_imports = true
```

---

## 11. Tests

Each component is independently testable because every component communicates only via events or typed method calls — no global state.

| Test file | What it covers |
|---|---|
| `tests/voice/test_events.py` | `AssistantState` transitions valid; `Event` union exhaustive |
| `tests/voice/test_audio_capture.py` | Mock sounddevice; verify `AudioFrame` put on bus |
| `tests/voice/test_wakeword.py` | Mock `pvporcupine.create()`; `process()` returns True/False correctly |
| `tests/voice/test_vad.py` | `update()` returns False below threshold; True after; `reset()` clears counter |
| `tests/voice/test_transcriber.py` | Mock Deepgram; `TranscriptPartial` and `UtteranceEnd` put on bus |
| `tests/voice/test_orchestrator.py` | State table: every meaningful event × state combination |
| `tests/voice/test_display.py` | `TerminalDisplay` calls correct Rich methods per state |
| `tests/tools/test_state.py` | `SetNextStateTool.execute()` sets `agent.next_state`; correct enum values |
| `tests/agent/test_agent.py` | `next_state` resets per turn; `AgentDone` carries correct value |

Orchestrator tests mock all components and drive the bus directly — no real audio, no real network.

---

## Verification Checklist

Before implementation begins, verify this document:

- [ ] Every current feature in the codebase maps to a named component (Section 8)
- [ ] State table covers all meaningful event × state combinations (Section 3)
- [ ] Threading model has no async calls from sounddevice callbacks (Section 4)
- [ ] File layout has no circular imports (Section 7)
- [ ] Display Protocol is implementable in < 50 lines for terminal (Section 6)
