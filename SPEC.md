# max-ai Technical Specification

**Date:** 2026-03-01
**Status:** Blueprint for implementation

---

## Overview

Four features transform the system from a manual push-to-talk CLI into a fully hands-free, responsive, multi-tasking voice assistant.

| # | Feature | Paper | Status |
|---|---|---|---|
| 1 | Wake Word Detection | [specs/feature-1-wake-word.md](specs/feature-1-wake-word.md) | Build first |
| 2 | Free Order of Actions | [specs/feature-2-free-order-of-actions.md](specs/feature-2-free-order-of-actions.md) | Depends on Feature 1 |
| 3 | Subagent Spawning | [specs/feature-3-subagents.md](specs/feature-3-subagents.md) | Depends on Feature 2 |
| 4 | Visual Status Dot | [specs/feature-4-ui-dot.md](specs/feature-4-ui-dot.md) | Standalone, anytime after Feature 1 |

**Implementation order:** 1 → 2 → 3. Feature 4 can be done at any time independently.

## CLI Flags

```
max-ai                   # push-to-talk mode (unchanged)
max-ai --wakeword        # always-listening mode (requires Features 1+)
max-ai --wakeword --ui   # wake word mode + visual dot (requires Features 1+4)
```

Both modes coexist. Push-to-talk (`voice/loop.py`) is never modified.

---

## Current State (baseline)

- **Interaction:** Push-to-talk. User presses Enter to record, releases to send.
- **STT:** ElevenLabs batch transcription (WAV → text).
- **Agent:** `Agent.run(user_message) -> AsyncIterator[str]`. Yields text at `end_turn`. Tool loop with `ToolRegistry`.
- **TTS:** ElevenLabs TTS + sounddevice playback. Interruptible via Enter key.
- **Background events:** `asyncio.Queue[dict[str, Any]]` already exists. TimerTool puts events in; voice loop injects them as agent turns.
- **No state machine.** No continuous audio monitoring. No wake word. No subagents.

---

## Feature 1: Wake Word Detection

### Goal
Replace push-to-talk with always-listening mode. User says "hey max" → assistant starts listening → Deepgram streams transcription → instruction-end detected → agent runs.

### State Machine

```
IDLE ──(wake word)──▶ LISTENING ──(utterance end)──▶ PROCESSING
  ▲                                                       │
  │                                                 agent runs
  │                                                       │
  └────────────────── SPEAKING ◀─────────────────────────┘
         ▲                │
  (TTS starts)     (TTS done → agent.next_state)
                          │
                    "idle"  → IDLE
                    "listening" → LISTENING
                    None (default) → IDLE
```

States:

| State | Audio | Description |
|---|---|---|
| `IDLE` | Porcupine running on raw chunks | Waiting for wake word |
| `LISTENING` | Deepgram WebSocket open, chunks streamed | Capturing user instruction |
| `PROCESSING` | Audio paused | Agent running |
| `SPEAKING` | Audio paused | TTS playing |

### New Files

**`voice/state_machine.py`**
```python
class AssistantState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"

class StateMachine:
    state: AssistantState
    pending_next_state: AssistantState | None

    def transition(self, new_state: AssistantState) -> None
    def set_post_speak_state(self, state: AssistantState) -> None
    def on_tts_complete(self) -> None  # transitions to pending or IDLE
    def on_change(self, callback: Callable[[AssistantState, AssistantState], None]) -> None
```

**`voice/wakeword.py`** (lazy import of `pvporcupine`)
```python
class WakeWordDetector:
    def __init__(self, access_key: str, keyword_path: str | None = None) -> None
    def process(self, audio_chunk: np.ndarray) -> bool  # True = wake word detected
    def close(self) -> None
    @property
    def frame_length(self) -> int  # Porcupine required frame size (512)
    @property
    def sample_rate(self) -> int   # Always 16000
```

**`voice/vad.py`** (lazy import of `torch`)
```python
class VoiceActivityDetector:
    def __init__(self, silence_threshold_ms: int = 1800) -> None
    def is_speech(self, audio_chunk: np.ndarray) -> bool
    def update(self, audio_chunk: np.ndarray) -> bool  # Returns True if silence threshold exceeded
    def reset(self) -> None
```

**`voice/transcribe.py`** (lazy import of `deepgram`)
```python
class DeepgramTranscriber:
    async def start(
        self,
        api_key: str,
        on_transcript: Callable[[str, bool], None],
        on_utterance_end: Callable[[], None],
    ) -> None
    async def send(self, audio_chunk: bytes) -> None
    async def stop(self) -> None
```

**`voice/listen_loop.py`** — new entry point for wake word mode
```python
async def voice_listen_loop(
    client: anthropic.AsyncAnthropic,
    registry: ToolRegistry,
    conversation_service: ConversationService,
    event_queue: asyncio.Queue[dict[str, Any]],
    system_prompt: str,
) -> None
```

### Modified Files

**`voice/loop.py`** — keep existing `voice_chat_loop()` unchanged (push-to-talk still works).

**`cli.py`** — detect mode from config:
```python
if settings.picovoice_access_key and settings.deepgram_api_key:
    await voice_listen_loop(...)
else:
    await voice_chat_loop(...)  # existing push-to-talk
```

**`config.py`** — add:
```python
picovoice_access_key: str = ""
porcupine_keyword_path: str = ""   # path to .ppn file; empty = use built-in "hey max" if available
deepgram_api_key: str = ""
vad_silence_threshold_ms: int = 1800
vad_min_words: int = 3
```

**`pyproject.toml`** — add mypy overrides:
```toml
[[tool.mypy.overrides]]
module = ["pvporcupine", "pvporcupine.*"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["deepgram", "deepgram.*"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["torch", "torch.*"]
ignore_missing_imports = true
```

Add optional extras group:
```toml
[project.optional-dependencies]
wake-word = ["pvporcupine>=3.0", "deepgram-sdk>=3.0", "torch>=2.0", "numpy>=1.24"]
```

### Instruction End Detection (two layers)

1. **Primary:** Deepgram `UtteranceEnd` event (`utterance_end_ms=1500`) — Deepgram's own VAD.
2. **Fallback:** Local silero-vad silence ≥ `vad_silence_threshold_ms` (1800ms).
3. **Guard:** Discard if transcript has fewer than `vad_min_words` (3) words.

### Testing

- Mock `pvporcupine.Porcupine` — test that `process()` returning `≥ 0` triggers state transition.
- Mock Deepgram WebSocket — test transcript accumulation and utterance-end callback.
- `StateMachine` tests: valid transitions, invalid transitions rejected, `on_tts_complete` default to IDLE.
- `VoiceActivityDetector` tests: silence threshold logic with synthetic audio.

---

## Feature 2: Free Order of Actions

### Goal
The agent can call `set_next_state("listening" | "idle")` at any point during its turn. After TTS finishes, the voice loop transitions to the agent-specified state instead of always going to IDLE.

### How It Works

The agent calls `set_next_state` as a regular tool. The tool sets `agent.next_state` as a side effect and returns `"ok"` to the API. After `run()` completes, the caller reads `agent.next_state`.

If called multiple times, the last call wins (attribute is overwritten). If never called, `next_state` stays `None` → defaults to IDLE.

### Modified Files

**`agent/agent.py`**
```python
class Agent:
    next_state: str | None = None   # set by set_next_state tool during run()

    async def run(self, user_message: str, ...) -> AsyncIterator[str]:
        self.next_state = None   # reset at start of every run
        # ... existing loop unchanged ...
        # set_next_state is executed via registry like any other tool
```

**`tools/state.py`** — new file
```python
class SetNextStateTool(BaseTool):
    def __init__(self, set_state: Callable[[str], None]) -> None:
        self._set_state = set_state

    def definitions(self) -> list[ToolDefinition]:
        return [ToolDefinition(
            name="set_next_state",
            description="""Set the assistant's next state after responding.

Use 'listening' when:
- You asked the user a question
- You expect follow-up input

Use 'idle' when:
- A task is done and no follow-up is needed
- You delivered information with no question asked""",
            input_schema={
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "enum": ["listening", "idle"],
                    }
                },
                "required": ["state"],
            },
        )]

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        self._set_state(tool_input["state"])
        return "ok"
```

**`cli.py`**
```python
agent = Agent(client=client, registry=registry, system=system_prompt)
registry.register(SetNextStateTool(set_state=lambda state: setattr(agent, "next_state", state)))
```

**`voice/listen_loop.py`** — after agent turn:
```python
async for text_chunk in agent.run(transcript):
    full_response += text_chunk

state_machine.set_post_speak_state(
    AssistantState(agent.next_state) if agent.next_state else AssistantState.IDLE
)
state_machine.transition(AssistantState.SPEAKING)
await speak(full_response, ...)
state_machine.on_tts_complete()  # transitions to pending_next_state or IDLE
```

**`agent/system_prompt.j2`** — add:
```
After completing a request:
- Call set_next_state("listening") if you asked a question or need follow-up.
- Call set_next_state("idle") if the task is complete and no follow-up is needed.
- If unsure, prefer "idle".
```

### Edge Cases

| Scenario | Behavior |
|---|---|
| Agent calls `set_next_state` twice | Last call wins (attribute overwritten) |
| Agent never calls it | `next_state = None` → default IDLE |
| Agent calls it before a tool result | Captured immediately; API gets "ok" result |

### Testing

- Test `SetNextStateTool.execute()` calls the setter with the correct state.
- Test that `agent.next_state` is reset to `None` at the start of each `run()`.
- Test voice loop reads `agent.next_state` and transitions correctly (mock state machine).
- Test "last call wins" by invoking the setter twice.

---

## Feature 3: Subagent Spawning

### Goal
The agent can offload long-running tasks (research, multi-step workflows) to a background async subagent. The main agent immediately returns to IDLE/LISTENING. When the subagent finishes, it delivers the result via TTS when the main agent is idle.

### Architecture

```
Main Agent
  └── spawn_subagent(task_description)
        │
        └── asyncio.create_task(run_subagent(...))
              │
        Background:
        Separate Anthropic API call
        Own system prompt (TTS-friendly prose)
        Subset of tools (web search, documents)
              │
        On complete:
        event_queue.put({"type": "subagent_result", "task_id": ..., "result": ...})
              │
        Voice loop picks up event → speaks result via TTS
```

### New Files

**`agent/subagent.py`**
```python
class SubagentStatus(Enum):
    SPAWNED = "spawned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DELIVERED = "delivered"

@dataclass
class SubagentTask:
    task_id: str                    # uuid4()[:8]
    description: str
    status: SubagentStatus
    result: str | None
    error: str | None
    created_at: datetime
    completed_at: datetime | None
    notify_when_done: bool
    priority: str                   # "normal" | "high"
    _asyncio_task: asyncio.Task[None] | None  # for cancellation

class SubagentManager:
    def __init__(self, max_concurrent: int = 3) -> None
    def spawn(self, description: str, notify: bool, priority: str) -> SubagentTask
    def get_active_tasks(self) -> list[SubagentTask]
    def cancel(self, task_id: str) -> bool
    def active_count(self) -> int

async def run_subagent(
    task: SubagentTask,
    manager: SubagentManager,
    client: anthropic.AsyncAnthropic,
    registry: ToolRegistry,
    event_queue: asyncio.Queue[dict[str, Any]],
    model: str,
    timeout_seconds: int,
) -> None
```

**`tools/subagent.py`**
```python
class SubagentTools(BaseTool):
    def __init__(
        self,
        manager: SubagentManager,
        client: anthropic.AsyncAnthropic,
        registry: ToolRegistry,
        event_queue: asyncio.Queue[dict[str, Any]],
        model: str,
        max_concurrent: int,
        timeout_seconds: int,
    ) -> None

    # Tools exposed:
    # spawn_subagent(task_description, notify_when_done=True, priority="normal") -> str
    # list_background_tasks() -> str
    # cancel_background_task(task_id) -> str
```

**Subagent system prompt** (in `agent/subagent.py` as a constant):
```
You are a background worker for Max, a voice assistant. Complete the task described to you.

Rules:
- Your output will be read aloud, so write in natural spoken prose.
- No markdown, no bullet points, no bold text.
- Be concise: 2-4 sentences unless the task explicitly asks for detail.
- If a tool call fails, retry once, then report the failure plainly.
```

### Modified Files

**`cli.py`**
```python
subagent_manager = SubagentManager(max_concurrent=settings.subagent_max_concurrent)
registry.register(SubagentTools(
    manager=subagent_manager,
    client=client,
    registry=subagent_registry,  # separate registry: web search + documents only
    event_queue=event_queue,
    model=settings.subagent_model,
    max_concurrent=settings.subagent_max_concurrent,
    timeout_seconds=settings.subagent_timeout_s,
))
```

**`voice/listen_loop.py`** — extend event handling:
```python
event = await event_queue.get()
if event["type"] == "subagent_result":
    # Wait for safe delivery window (not SPEAKING or PROCESSING)
    while state_machine.state in (AssistantState.SPEAKING, AssistantState.PROCESSING):
        await asyncio.sleep(0.3)
    state_machine.transition(AssistantState.SPEAKING)
    await speak(f"Update: {event['result']}", ...)
    state_machine.on_tts_complete()
```

**`config.py`** — add:
```python
subagent_model: str = ""          # defaults to settings.model if empty
subagent_max_concurrent: int = 3
subagent_timeout_s: int = 120
```

### Subagent Tool Subset

Subagents get their own `ToolRegistry` with a restricted set:
- `AnthropicWebSearch` (if enabled)
- `DocumentTools`
- NOT: `SetNextStateTool`, `SubagentTools`, `SpotifyTools`, `CalendarTools`, `TimerTool`, `AlarmTool`

### Edge Cases

| Scenario | Behavior |
|---|---|
| Subagent exceeds timeout | Task cancelled; event_queue gets `{"type": "subagent_error", "message": "timed out"}` |
| Multiple subagents complete simultaneously | Events queue up; delivered one at a time |
| `spawn_subagent` called when at max_concurrent | Tool returns error message; main agent tells user |
| User cancels via `cancel_background_task` | asyncio.Task cancelled; status set to CANCELLED |
| Subagent needs conversation history | Main agent must include all context in `task_description` — by design |

### Testing

- Test `SubagentManager.spawn()` creates task with correct initial state.
- Test `run_subagent()` with mocked Anthropic client — RUNNING → COMPLETED → event_queue.
- Test `run_subagent()` timeout cancellation.
- Test `cancel_background_task` cancels the asyncio task.
- Test event delivery in voice loop (mock state machine + mock speak).
- Test max_concurrent guard: 4th spawn rejected when 3 active.

---

## Feature 4: Visual Status Dot (Deferred)

### Goal
A browser page served locally shows a single dot whose appearance reflects `AssistantState`. Purely cosmetic — no impact on voice behavior.

### Architecture

```
StateMachine.on_change callback
        │
        ▼
FastAPI WebSocket broadcast
        │
        ▼
Browser: dot CSS class = state name
```

### New Files

**`ui/__init__.py`**

**`ui/server.py`**
```python
app: FastAPI

@app.websocket("/ws/status")
async def status_websocket(websocket: WebSocket) -> None

async def broadcast_state(state: AssistantState) -> None

def start_server(host: str, port: int) -> None  # starts uvicorn in background thread
```

**`ui/static/index.html`** — single HTML page:
- Full-page white background, single centered `<div id="dot">`
- CSS animations for each state (idle, listening, processing, speaking)
- JS WebSocket client that sets `dot.className = state`
- Auto-reconnect on disconnect

### Dot Appearance

| State | Color | Size | Animation |
|---|---|---|---|
| `idle` | Black (#111) | 20px | None |
| `idle` + background subagents | Black | 20px | Faint blue ring pulse (3s) |
| `listening` | Blue (#3b82f6) | 30px | Shimmer pulse (1.5s) |
| `processing` | Blue (#3b82f6) | 30px | Slow breathe (2s) |
| `speaking` | Blue (#3b82f6) | 30px | Rapid vibrate (50ms) |

### Modified Files

**`config.py`** — add:
```python
ui_enabled: bool = False
ui_host: str = "127.0.0.1"
ui_port: int = 8420
```

**`voice/state_machine.py`** — `on_change` callback already built in Feature 1; `ui/server.py` registers `broadcast_state` as a listener.

**`cli.py`** — if `settings.ui_enabled`:
```python
from max_ai.ui.server import start_server
start_server(host=settings.ui_host, port=settings.ui_port)
state_machine.on_change(lambda old, new: asyncio.run_coroutine_threadsafe(broadcast_state(new), loop))
```

**`pyproject.toml`** — add optional extras:
```toml
[project.optional-dependencies]
ui = ["fastapi>=0.110", "uvicorn>=0.29", "websockets>=12.0"]
```

### WebSocket Message Format

```json
{"state": "idle", "background_tasks": 0}
```

`background_tasks` > 0 triggers the faint ring animation on the idle dot.

### Testing

- Test `broadcast_state` sends correct JSON to connected clients.
- Test WebSocket endpoint accepts connections and sends current state on connect.
- Test state change → broadcast called (mock WebSocket clients).

---

## Configuration Keys Reference

### New keys added across all features

| Key | Type | Default | Feature | Env Var |
|---|---|---|---|---|
| `picovoice_access_key` | `str` | `""` | 1 | `MAX_AI_PICOVOICE_ACCESS_KEY` |
| `porcupine_keyword_path` | `str` | `""` | 1 | `MAX_AI_PORCUPINE_KEYWORD_PATH` |
| `deepgram_api_key` | `str` | `""` | 1 | `MAX_AI_DEEPGRAM_API_KEY` |
| `vad_silence_threshold_ms` | `int` | `1800` | 1 | `MAX_AI_VAD_SILENCE_THRESHOLD_MS` |
| `vad_min_words` | `int` | `3` | 1 | `MAX_AI_VAD_MIN_WORDS` |
| `subagent_model` | `str` | `""` | 3 | `MAX_AI_SUBAGENT_MODEL` |
| `subagent_max_concurrent` | `int` | `3` | 3 | `MAX_AI_SUBAGENT_MAX_CONCURRENT` |
| `subagent_timeout_s` | `int` | `120` | 3 | `MAX_AI_SUBAGENT_TIMEOUT_S` |
| `ui_enabled` | `bool` | `False` | 4 | `MAX_AI_UI_ENABLED` |
| `ui_host` | `str` | `"127.0.0.1"` | 4 | `MAX_AI_UI_HOST` |
| `ui_port` | `int` | `8420` | 4 | `MAX_AI_UI_PORT` |

**Mode detection logic in `cli.py`:**
- Wake word mode: `picovoice_access_key != ""` AND `deepgram_api_key != ""`
- Otherwise: existing push-to-talk mode

---

## Dependencies Reference

| Package | Version | Feature | Why | Install group |
|---|---|---|---|---|
| `pvporcupine` | `>=3.0` | 1 | Wake word detection | `wake-word` extra |
| `deepgram-sdk` | `>=3.0` | 1 | Streaming STT | `wake-word` extra |
| `torch` | `>=2.0` | 1 | silero-vad (VAD) | `wake-word` extra |
| `numpy` | `>=1.24` | 1 | Audio array ops | `wake-word` extra |
| `fastapi` | `>=0.110` | 4 | WebSocket server | `ui` extra |
| `uvicorn` | `>=0.29` | 4 | ASGI server | `ui` extra |
| `websockets` | `>=12.0` | 4 | WebSocket support | `ui` extra |

Features 2 and 3 add **no new dependencies** (pure Python + existing Anthropic SDK).

---

## New Files Summary

| File | Feature | Purpose |
|---|---|---|
| `voice/state_machine.py` | 1 | `AssistantState` enum, `StateMachine` class |
| `voice/wakeword.py` | 1 | Porcupine wrapper |
| `voice/vad.py` | 1 | silero-vad silence detector |
| `voice/transcribe.py` | 1 | Deepgram streaming client |
| `voice/listen_loop.py` | 1 | Wake word mode main loop |
| `tools/state.py` | 2 | `SetNextStateTool` |
| `agent/subagent.py` | 3 | `SubagentTask`, `SubagentManager`, `run_subagent()` |
| `tools/subagent.py` | 3 | `SubagentTools` (spawn/list/cancel) |
| `ui/__init__.py` | 4 | Package marker |
| `ui/server.py` | 4 | FastAPI + WebSocket broadcast |
| `ui/static/index.html` | 4 | Dot UI page |

## Modified Files Summary

| File | Features | What changes |
|---|---|---|
| `config.py` | 1, 3, 4 | New settings fields |
| `cli.py` | 1, 2, 3, 4 | Mode detection, new tool registration, optional UI start |
| `agent/agent.py` | 2 | Add `next_state: str | None` attribute, reset at start of `run()` |
| `agent/system_prompt.j2` | 2 | Add `set_next_state` guidance |
| `voice/loop.py` | — | Unchanged (push-to-talk preserved) |
| `pyproject.toml` | 1, 4 | New optional extras, mypy overrides |
