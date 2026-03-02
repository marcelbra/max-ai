> **Superseded** — This spec is archived. The canonical design is in [architecture.md](architecture.md), which replaces this document in full.

# Always-Listening Voice Mode

**Status:** Design — not yet implemented
**Replaces:** `feature-1-wake-word.md`, `feature-1a-deepgram-transcription.md`, `feature-2-free-order-of-actions.md`

---

## What This Is

An always-listening mode that replaces push-to-talk. The assistant waits silently until it hears "hey max", then transcribes the user's instruction via Deepgram, runs the agent, and speaks the response. The agent controls what happens next: it either returns to idle (wake word required again) or stays in listening mode (no wake word, just speak).

The existing push-to-talk mode (`voice/loop.py`) is unchanged.

---

## State Machine

```
IDLE ──(wake word)──▶ LISTENING ──(utterance end)──▶ PROCESSING
  ▲                                                       │
  │                                                  agent runs
  │                                                       │
  └──────────────────── SPEAKING ◀─────────────────────-─┘
                              │
                       TTS completes:
                       next_state == "listening" ──▶ LISTENING
                       next_state == "idle" | None ──▶ IDLE
```

| State | Audio | What's Happening |
|---|---|---|
| `IDLE` | Porcupine running on every frame | Waiting for wake word |
| `LISTENING` | Deepgram WebSocket open, frames streamed | Capturing user's instruction |
| `PROCESSING` | Audio paused | Agent running, tools executing |
| `SPEAKING` | Audio paused | TTS playing |

---

## End-to-End Flow

1. **IDLE** — A `sounddevice` input stream runs continuously in a background thread, pushing 512-sample int16 frames into an `asyncio.Queue`. The main loop feeds each frame to Porcupine. Porcupine is paused during `PROCESSING` and `SPEAKING` to avoid false triggers from TTS audio.

2. **Wake word detected → LISTENING** — Open a Deepgram WebSocket (`DeepgramTranscriber.start()`). Reset VAD. Stream all subsequent frames to Deepgram and also run local VAD on each frame.

3. **Utterance end detected → PROCESSING** — Two signals can trigger this:
   - Deepgram fires `UtteranceEnd` (primary, `utterance_end_ms=1500`)
   - Local VAD detects ≥ 1800ms of consecutive silence (fallback)

   If the transcript has fewer than 3 words, discard silently and return to IDLE (false trigger). Otherwise, close Deepgram, transition to PROCESSING, and run the agent.

4. **Agent done → SPEAKING** — Collect full agent response. Read `agent.next_state` (set by `set_next_state` tool during the turn). Store it as `pending_next_state` on the state machine. Transition to SPEAKING, play TTS.

5. **TTS done → IDLE or LISTENING** — `state_machine.on_tts_complete()` reads `pending_next_state`:
   - `"listening"` → LISTENING (Deepgram opens, next instruction expected without wake word)
   - `"idle"` or `None` → IDLE (Porcupine resumes, waits for next wake word)

---

## Agent State Control

The agent calls `set_next_state` as a regular tool during its turn. The tool sets `agent.next_state` as a side effect and returns `"ok"` to the API. After `run()` completes, the voice loop reads `agent.next_state` and hands it to the state machine.

**When to call it:**
- `"listening"` — agent asked a question or expects follow-up input
- `"idle"` — task is done, no follow-up needed
- Not called → defaults to `"idle"`

If called multiple times in one turn, the last call wins. `agent.next_state` is reset to `None` at the start of every `run()`.

---

## New Files

### `voice/state_machine.py`

```python
class AssistantState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"

class StateMachine:
    state: AssistantState                    # current state, starts IDLE
    pending_next_state: AssistantState | None  # set before SPEAKING; read by on_tts_complete

    def transition(self, new_state: AssistantState) -> None
        # Updates state, fires on_change callbacks.

    def set_post_speak_state(self, state: AssistantState) -> None
        # Called before transitioning to SPEAKING. Stores what to do after TTS.

    def on_tts_complete(self) -> None
        # Transitions to pending_next_state (or IDLE if None). Clears pending.

    def on_change(self, callback: Callable[[AssistantState, AssistantState], None]) -> None
        # Register a listener. Called with (old_state, new_state) on every transition.
```

### `voice/wakeword.py`

Wraps Porcupine. Lazy import (`import pvporcupine` inside `__init__`).

```python
class WakeWordDetector:
    def __init__(self, access_key: str, keyword_path: str = "") -> None
        # keyword_path: path to custom .ppn file.
        # If empty, uses built-in keyword (e.g. "hey google" — free tier doesn't include "hey max").
        # Train custom "hey max" at console.picovoice.ai, download .ppn, set MAX_AI_PORCUPINE_KEYWORD_PATH.

    def process(self, audio_frame: bytes) -> bool
        # Feed exactly frame_length int16 samples. Returns True if wake word detected.

    @property
    def frame_length(self) -> int   # typically 512 samples
    @property
    def sample_rate(self) -> int    # always 16000

    def close(self) -> None
```

The audio callback must buffer incoming audio and emit exact `frame_length`-sized chunks to `process()`.

### `voice/vad.py`

Local VAD using silero-vad. Used as utterance-end fallback when Deepgram's `UtteranceEnd` doesn't fire. Lazy import (`import torch` inside `_load_model`).

```python
class VoiceActivityDetector:
    def __init__(self, silence_threshold_ms: int = 1800, sample_rate: int = 16000) -> None

    def update(self, audio_chunk: bytes) -> bool
        # Feed int16 PCM chunk. Tracks consecutive silence duration.
        # Returns True when silence >= silence_threshold_ms (utterance ended).
        # Resets silence counter on any speech.

    def reset(self) -> None
        # Reset silence counter. Call when entering LISTENING state.
```

silero-vad model (~3MB) is downloaded from torch hub on first use, cached at `~/.cache/torch/hub/`.

### `voice/listen_loop.py`

Main entry point for always-listening mode.

```python
async def voice_listen_loop(
    client: anthropic.AsyncAnthropic,
    registry: ToolRegistry,
    conversation_service: ConversationService,
    event_queue: asyncio.Queue[dict[str, Any]],
    system_prompt: str,
) -> None
```

**Loop structure (pseudocode):**

```python
state_machine = StateMachine()
wake_detector = WakeWordDetector(settings.picovoice_access_key, settings.porcupine_keyword_path)
vad = VoiceActivityDetector(settings.vad_silence_threshold_ms)
transcriber = DeepgramTranscriber()
audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
accumulated_transcript = ""

# sounddevice InputStream → audio_queue (background thread)

while True:
    # Wait for audio frame or background event (timer, future: subagent result)
    done, _ = await asyncio.wait(
        [asyncio.create_task(audio_queue.get()), asyncio.create_task(event_queue.get())],
        return_when=asyncio.FIRST_COMPLETED,
    )

    if got audio frame:
        if state == IDLE:
            frame = buffer_to_frame(chunk)  # accumulate until frame_length samples
            if frame and wake_detector.process(frame):
                state_machine.transition(LISTENING)
                vad.reset()
                accumulated_transcript = ""
                await transcriber.start(
                    on_transcript=lambda text, is_final: accumulated_transcript += text,
                    on_utterance_end=lambda: handle_utterance_end(),
                )

        elif state == LISTENING:
            await transcriber.send(chunk)
            if vad.update(chunk):
                await handle_utterance_end()

    if got background event:
        # Background events (e.g. timers) are injected as agent turns
        # Wait for safe window, then process

async def handle_utterance_end() -> None:
    if len(accumulated_transcript.split()) < settings.vad_min_words:
        state_machine.transition(IDLE)
        return

    await transcriber.stop()
    state_machine.transition(PROCESSING)

    full_response = ""
    async for text_chunk in agent.run(accumulated_transcript):
        full_response += text_chunk

    post_speak_state = (
        AssistantState(agent.next_state) if agent.next_state else AssistantState.IDLE
    )
    state_machine.set_post_speak_state(post_speak_state)
    state_machine.transition(SPEAKING)
    await speak(full_response, ...)
    state_machine.on_tts_complete()
```

### `tools/state.py`

```python
class SetNextStateTool(BaseTool):
    def __init__(self, set_state: Callable[[str], None]) -> None

    def definitions(self) -> list[ToolDefinition]:
        # name: "set_next_state"
        # input: {"state": {"type": "string", "enum": ["listening", "idle"]}}

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        self._set_state(tool_input["state"])
        return "ok"
```

---

## Modified Files

### `agent/agent.py`

Add one attribute; reset it at the top of `run()`:

```python
class Agent:
    def __init__(self, ...) -> None:
        ...
        self.next_state: str | None = None

    async def run(self, user_message: str, ...) -> AsyncIterator[str]:
        self.next_state = None  # reset at start of every turn
        # rest of run() unchanged
```

`set_next_state` executes via the registry like any other tool — no special handling in the loop.

### `agent/system_prompt.j2`

Add to the end:

```
After completing a request, call set_next_state:
- "listening" — if you asked the user a question or need their follow-up
- "idle" — if the task is done and no follow-up is needed
If unsure, use "idle".
```

### `cli.py`

Register `SetNextStateTool` after creating the agent:

```python
agent = Agent(client=client, registry=registry, system=system_prompt)
registry.register(SetNextStateTool(set_state=lambda state: setattr(agent, "next_state", state)))
```

Mode detection (no CLI flag needed — mode is inferred from config):

```python
if settings.picovoice_access_key and settings.deepgram_api_key:
    await voice_listen_loop(client, registry, conversation_service, event_queue, system_prompt)
else:
    await voice_chat_loop(client, registry, conversation_service, event_queue, system_prompt)
```

### `config.py`

```python
# Wake word mode (all required when picovoice_access_key is set)
picovoice_access_key: str = ""
porcupine_keyword_path: str = ""  # empty = use built-in keyword
# deepgram_api_key already exists
vad_silence_threshold_ms: int = 1800
vad_min_words: int = 3
```

### `pyproject.toml`

New optional extras group:

```toml
[project.optional-dependencies]
wake-word = [
    "pvporcupine>=3.0",
    "deepgram-sdk>=3.0",
    "torch>=2.0",
    "numpy>=1.24",
]
```

New mypy overrides:

```toml
[[tool.mypy.overrides]]
module = ["pvporcupine", "pvporcupine.*"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["torch", "torch.*"]
ignore_missing_imports = true
```

(deepgram override may already exist from the push-to-talk Deepgram work)

---

## New Environment Variables

| Env Var | Required | Default | Description |
|---|---|---|---|
| `MAX_AI_PICOVOICE_ACCESS_KEY` | Yes (wake word) | `""` | From console.picovoice.ai |
| `MAX_AI_PORCUPINE_KEYWORD_PATH` | No | `""` | Path to custom .ppn file |
| `MAX_AI_DEEPGRAM_API_KEY` | Yes (wake word) | `""` | Already in config |
| `MAX_AI_VAD_SILENCE_THRESHOLD_MS` | No | `1800` | Silence duration before utterance end |
| `MAX_AI_VAD_MIN_WORDS` | No | `3` | Min words to pass to agent (anti-false-trigger) |

---

## New Dependencies

| Package | Why | Install |
|---|---|---|
| `pvporcupine>=3.0` | Wake word detection | `uv sync --extra wake-word` |
| `torch>=2.0` | silero-vad (local VAD fallback) | `uv sync --extra wake-word` |

`deepgram-sdk` and `numpy` already in use.

---

## Notes

**Wake word keyword:** Porcupine's free tier built-ins don't include "hey max". Options:
- Train a custom "hey max" keyword at [console.picovoice.ai](https://console.picovoice.ai/) (free, ~1 min). Download the `.ppn` file and set `MAX_AI_PORCUPINE_KEYWORD_PATH`.
- Use a built-in keyword (e.g. "porcupine", "hey google") as a temporary stand-in.

**Frame buffering:** Porcupine requires exactly 512 int16 samples per `process()` call. The sounddevice callback will deliver variable-size chunks. The listen loop must buffer incoming audio and only call `WakeWordDetector.process()` when a complete frame is ready.

**No TTS false triggers:** Porcupine must be paused while in `PROCESSING` or `SPEAKING` states. Resume only on transition back to `IDLE` or `LISTENING`.

**Push-to-talk preserved:** `voice/loop.py` and `voice/chat_loop()` are not touched. When both `picovoice_access_key` and `deepgram_api_key` are absent, the existing mode runs.

---

## Tests

**`tests/voice/test_state_machine.py`**
- Valid transitions succeed; `on_change` callbacks fire
- `on_tts_complete()` defaults to IDLE when `pending_next_state` is None
- `on_tts_complete()` uses `pending_next_state` when set; clears it afterward

**`tests/voice/test_wakeword.py`**
- Mock `pvporcupine.create()` — `process()` returns True when handle returns `>= 0`, False for `-1`

**`tests/voice/test_vad.py`**
- `update()` returns False while silence is below threshold
- `update()` returns True once threshold is exceeded
- `reset()` clears accumulated silence counter

**`tests/tools/test_state.py`**
- `execute()` calls `set_state` with correct value
- `definitions()` returns one tool with name `set_next_state` and correct enum values

**`tests/agent/test_agent.py`** (extend existing)
- `agent.next_state` is `None` at start of each `run()`, even if previous run set it
- After a turn that calls `set_next_state`, `agent.next_state` reflects the value

**`tests/voice/test_listen_loop.py`**
- IDLE → LISTENING on wake word (mock `WakeWordDetector.process()` returning True)
- LISTENING → PROCESSING on utterance end (mock Deepgram `on_utterance_end`)
- Short transcript (< `vad_min_words`) → returns to IDLE, agent not called
- `agent.next_state == "listening"` → state machine transitions to LISTENING after TTS
- `agent.next_state == None` → state machine transitions to IDLE after TTS
- Background event from `event_queue` handled while in IDLE
