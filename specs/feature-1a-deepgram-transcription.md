# Feature 1a: Deepgram Streaming Transcription

Prerequisite for Feature 1 (Wake Word). Implement and merge this first.

## What This Adds

A `DeepgramTranscriber` class that opens a Deepgram WebSocket, streams raw PCM audio, and fires callbacks for interim/final transcripts and utterance-end events. No integration with the wake word loop yet — just the client, config, dependency, and tests.

---

## New File: `src/max_ai/voice/transcribe.py`

```python
class DeepgramTranscriber:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._connection: Any | None = None  # deepgram LiveClient

    async def start(
        self,
        on_transcript: Callable[[str, bool], None],
        on_utterance_end: Callable[[], None],
    ) -> None:
        """Open Deepgram WebSocket.

        Calls on_transcript(text, is_final) for each transcript result.
        Calls on_utterance_end() when Deepgram fires the UtteranceEnd event.

        Options:
          model="nova-2", language="en", smart_format=True,
          interim_results=True, utterance_end_ms=1500,
          vad_events=True, encoding="linear16", sample_rate=16000
        """

    async def send(self, audio_chunk: bytes) -> None:
        """Send raw int16 PCM bytes to the open WebSocket."""

    async def stop(self) -> None:
        """Close the WebSocket connection."""
```

Lazy import inside `start()`:
```python
async def start(self, ...) -> None:
    from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents  # lazy
    ...
```

---

## Modified Files

### `src/max_ai/config.py`

Add:
```python
deepgram_api_key: str = ""
```

### `pyproject.toml`

Add mypy override:
```toml
[[tool.mypy.overrides]]
module = ["deepgram", "deepgram.*"]
ignore_missing_imports = true
```

Add to `wake-word` extras (create the group if it doesn't exist yet):
```toml
[project.optional-dependencies]
wake-word = [
    "deepgram-sdk>=3.0",
]
```

---

## New Environment Variable

| Env Var | Required | Description |
|---|---|---|
| `MAX_AI_DEEPGRAM_API_KEY` | Yes (wake word mode) | From deepgram.com |

---

## Tests: `tests/voice/test_transcribe.py`

- Mock Deepgram client — test `on_transcript` callback fires with correct text and `is_final` flag
- Test `on_utterance_end` callback fires when Deepgram sends UtteranceEnd event
- Test `stop()` closes the connection

---

## Notes

- The `deepgram-sdk` import is lazy (inside `start()`) so importing the module at the top level does not fail when the package is not installed.
- `send()` must be a no-op (or raise) if called before `start()`.
- `stop()` must be safe to call more than once.
