> **Superseded** — This spec is archived. The canonical design is in [architecture.md](architecture.md) (§2 WakeWordDetector component, §8.1 Feature 1 mapping).

# Feature 1: Wake Word Detection

## What This Adds

A second operating mode for max-ai. The existing push-to-talk mode is unchanged. When started with `--wakeword`, the assistant runs continuously: it listens for "hey max", then streams audio to Deepgram, then detects when you've stopped speaking, then runs the agent — all hands-free.

```
max-ai             # existing push-to-talk mode (unchanged)
max-ai --wakeword  # new always-listening mode
```

---

## State Machine

```
IDLE ──(wake word detected)──▶ LISTENING ──(utterance end)──▶ PROCESSING
  ▲                                                               │
  └───────────────────── SPEAKING ◀──────────────────────────────┘
                              │
                        (TTS done → IDLE by default, or
                         agent-specified state — see Feature 2)
```

| State | What's Running | Description |
|---|---|---|
| `IDLE` | Porcupine on every audio chunk | Waiting for "hey max" |
| `LISTENING` | Deepgram WebSocket open, chunks streamed | Capturing instruction |
| `PROCESSING` | Audio paused | Agent running |
| `SPEAKING` | Audio paused | TTS playing |

---

## CLI Change

**`src/max_ai/__main__.py`** — add argument parsing:

```python
import argparse

def run_cli() -> None:
    parser = argparse.ArgumentParser(prog="max-ai")
    parser.add_argument("--wakeword", action="store_true", help="Run in always-listening wake word mode")
    args = parser.parse_args()
    asyncio.run(main(wakeword_mode=args.wakeword))
```

**`src/max_ai/cli.py`** — `main()` accepts the flag:

```python
async def main(wakeword_mode: bool = False) -> None:
    ...
    if wakeword_mode:
        await voice_listen_loop(client, registry, conversation_service, event_queue, system_prompt)
    else:
        await voice_chat_loop(client, registry, conversation_service, event_queue, system_prompt)
```

---

## New Files

### `src/max_ai/voice/state_machine.py`

```python
from enum import Enum
from typing import Callable

class AssistantState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"

class StateMachine:
    def __init__(self) -> None:
        self.state: AssistantState = AssistantState.IDLE
        self.pending_next_state: AssistantState | None = None
        self._listeners: list[Callable[[AssistantState, AssistantState], None]] = []

    def transition(self, new_state: AssistantState) -> None:
        old = self.state
        self.state = new_state
        for listener in self._listeners:
            listener(old, new_state)

    def set_post_speak_state(self, state: AssistantState) -> None:
        """Called by set_next_state tool (Feature 2). Stores what to do after TTS."""
        self.pending_next_state = state

    def on_tts_complete(self) -> None:
        """Called when TTS finishes. Transitions to pending or IDLE."""
        next_state = self.pending_next_state or AssistantState.IDLE
        self.pending_next_state = None
        self.transition(next_state)

    def on_change(self, callback: Callable[[AssistantState, AssistantState], None]) -> None:
        self._listeners.append(callback)
```

---

### `src/max_ai/voice/wakeword.py`

Lazy import of `pvporcupine` (optional dependency — only imported when wake word mode is active).

```python
class WakeWordDetector:
    def __init__(self, access_key: str, keyword_path: str = "") -> None:
        """
        access_key: Picovoice access key
        keyword_path: path to .ppn file. If empty, uses built-in "hey max" (if available)
                      or falls back to "porcupine" (the default built-in keyword).
        """

    def process(self, audio_chunk: bytes) -> bool:
        """Process one frame of audio. Returns True if wake word detected.
        audio_chunk must be exactly frame_length * 2 bytes (int16 PCM).
        """

    @property
    def frame_length(self) -> int:
        """Number of int16 samples per frame required by Porcupine (typically 512)."""

    @property
    def sample_rate(self) -> int:
        """Always 16000."""

    def close(self) -> None:
        """Release Porcupine resources."""
```

Import pattern inside `__init__`:
```python
def __init__(self, access_key: str, keyword_path: str = "") -> None:
    import pvporcupine  # lazy — only when wake word mode used
    if keyword_path:
        self._handle = pvporcupine.create(access_key=access_key, keyword_paths=[keyword_path])
    else:
        self._handle = pvporcupine.create(access_key=access_key, keywords=["hey google"])
        # Note: Picovoice free tier built-ins don't include "hey max".
        # User must either use a built-in keyword or provide a custom .ppn file.
        # See: https://console.picovoice.ai/ to train "hey max" keyword.
```

---

### `src/max_ai/voice/vad.py`

Local VAD using silero-vad. Used as fallback when Deepgram utterance-end isn't sufficient.

```python
class VoiceActivityDetector:
    def __init__(self, silence_threshold_ms: int = 1800, sample_rate: int = 16000) -> None:
        """
        silence_threshold_ms: consecutive silence duration before declaring utterance done.
        Loads silero-vad model lazily on first use.
        """

    def is_speech(self, audio_chunk: bytes) -> bool:
        """Returns True if chunk contains speech. audio_chunk is int16 PCM bytes."""

    def update(self, audio_chunk: bytes) -> bool:
        """Feed chunk and track silence duration.
        Returns True if silence_threshold_ms of consecutive silence has elapsed.
        Resets silence counter on any speech detection.
        """

    def reset(self) -> None:
        """Reset silence counter. Call when entering LISTENING state."""
```

Import pattern:
```python
def _load_model(self) -> None:
    import torch  # lazy
    model, utils = torch.hub.load(repo_or_dir="snakers4/silero-vad", model="silero_vad")
    self._model = model
    self._get_speech_timestamps = utils[0]
```

---

### `src/max_ai/voice/transcribe.py`

See **[Feature 1a: Deepgram Streaming Transcription](feature-1a-deepgram-transcription.md)** — implement and merge that spec first.

---

### `src/max_ai/voice/listen_loop.py`

The main loop for wake word mode. Replaces the push-to-talk loop when `--wakeword` is used.

```python
async def voice_listen_loop(
    client: anthropic.AsyncAnthropic,
    registry: ToolRegistry,
    conversation_service: ConversationService,
    event_queue: asyncio.Queue[dict[str, Any]],
    system_prompt: str,
) -> None:
    """
    Main loop for wake word mode.

    Audio pipeline runs in a background thread (sounddevice InputStream callback).
    Audio chunks are pushed to an asyncio.Queue.

    Main async loop processes:
    - Audio chunks: route to Porcupine (IDLE) or Deepgram (LISTENING)
    - Background events from event_queue (timers, subagent results)
    - State machine transitions
    """
```

**Loop pseudocode:**
```python
state_machine = StateMachine()
wake_detector = WakeWordDetector(access_key=settings.picovoice_access_key, ...)
vad = VoiceActivityDetector(silence_threshold_ms=settings.vad_silence_threshold_ms)
transcriber = DeepgramTranscriber(api_key=settings.deepgram_api_key)
audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
accumulated_transcript = ""

# Start sounddevice InputStream in background thread → puts chunks in audio_queue

while True:
    # Wait for audio chunk or background event
    chunk = await audio_queue.get()  # or event_queue — use asyncio.wait()

    if state_machine.state == IDLE:
        if wake_detector.process(chunk):
            state_machine.transition(LISTENING)
            vad.reset()
            accumulated_transcript = ""
            await transcriber.start(on_transcript=..., on_utterance_end=...)

    elif state_machine.state == LISTENING:
        await transcriber.send(chunk)
        if vad.update(chunk):  # local fallback: silence threshold exceeded
            await _handle_utterance_end(accumulated_transcript)

    # Deepgram on_utterance_end callback also calls _handle_utterance_end()

async def _handle_utterance_end(transcript: str) -> None:
    if len(transcript.split()) < settings.vad_min_words:
        # Too short — go back to IDLE silently
        state_machine.transition(IDLE)
        return

    await transcriber.stop()
    state_machine.transition(PROCESSING)

    full_response = await _run_agent_turn(agent, transcript, conversation_id)
    if full_response:
        state_machine.transition(SPEAKING)
        await speak(full_response, ...)
        state_machine.on_tts_complete()
    else:
        state_machine.transition(IDLE)
```

---

## Modified Files

### `src/max_ai/config.py`

Add fields:
```python
picovoice_access_key: str = ""
porcupine_keyword_path: str = ""   # empty = use built-in keyword
# deepgram_api_key already added in Feature 1a
vad_silence_threshold_ms: int = 1800
vad_min_words: int = 3
```

### `pyproject.toml`

Add mypy overrides (deepgram override already added in Feature 1a):
```toml
[[tool.mypy.overrides]]
module = ["pvporcupine", "pvporcupine.*"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["torch", "torch.*"]
ignore_missing_imports = true
```

Extend the `wake-word` extras group (deepgram-sdk already added in Feature 1a):
```toml
[project.optional-dependencies]
wake-word = [
    "pvporcupine>=3.0",
    "deepgram-sdk>=3.0",
    "torch>=2.0",
    "numpy>=1.24",
]
```

---

## New Environment Variables

| Env Var | Required | Description |
|---|---|---|
| `MAX_AI_PICOVOICE_ACCESS_KEY` | Yes (wake word mode) | From console.picovoice.ai |
| `MAX_AI_PORCUPINE_KEYWORD_PATH` | No | Path to custom .ppn file |
| `MAX_AI_DEEPGRAM_API_KEY` | Yes (wake word mode) | Added in Feature 1a |
| `MAX_AI_VAD_SILENCE_THRESHOLD_MS` | No | Default: 1800 |
| `MAX_AI_VAD_MIN_WORDS` | No | Default: 3 |

---

## Dependencies

| Package | Why | Install |
|---|---|---|
| `pvporcupine>=3.0` | Wake word detection | `uv sync --extra wake-word` |
| `deepgram-sdk>=3.0` | Streaming STT | `uv sync --extra wake-word` |
| `torch>=2.0` | silero-vad model | `uv sync --extra wake-word` |
| `numpy>=1.24` | Audio array operations | `uv sync --extra wake-word` |

---

## Tests

**`tests/voice/test_state_machine.py`**
- All valid transitions succeed
- `on_tts_complete()` defaults to IDLE when no pending state
- `on_tts_complete()` uses pending state when set
- `on_change` callbacks fire on each transition

**`tests/voice/test_wakeword.py`**
- Mock `pvporcupine.create()` — returns mock handle
- `process()` returns True when mock handle returns `>= 0`
- `process()` returns False when mock handle returns `-1`

**`tests/voice/test_vad.py`**
- `update()` returns False when silence is below threshold
- `update()` returns True after threshold exceeded
- `reset()` clears accumulated silence

**`tests/voice/test_transcribe.py`** — see Feature 1a

**`tests/voice/test_listen_loop.py`**
- Mock all audio/network components
- Test IDLE → LISTENING transition on wake word
- Test LISTENING → PROCESSING on utterance end
- Test short transcript (< min_words) goes back to IDLE, not PROCESSING
- Test background event from event_queue is handled during IDLE

---

## Notes

- The `WakeWordDetector` frame length from Porcupine is typically 512 samples. The audio callback must buffer incoming audio and emit exact-sized frames to Porcupine.
- During SPEAKING, Porcupine should NOT be running — otherwise TTS audio may trigger a false wake word detection. Pause wake word detection when state is SPEAKING or PROCESSING.
- Custom "hey max" keyword: train via https://console.picovoice.ai/ (free tier, takes ~1 min). Download the `.ppn` file and set `MAX_AI_PORCUPINE_KEYWORD_PATH`.
- silero-vad model is downloaded from torch hub on first use (~3MB). Cached in `~/.cache/torch/hub/`.
