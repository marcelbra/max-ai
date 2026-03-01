# max-ai Feature Specs

## Canonical Architecture Document

**[specs/architecture.md](architecture.md)** is the single authoritative design document.

It covers the event-driven architecture (typed events, 7 components, orchestrator state table, threading model, display contract, file layout) and shows how Features 1–4 map onto it.

All previous feature specs are superseded. See the archive section below.

---

## Feature Status

| # | Feature | Maps to (in architecture.md) | Status |
|---|---|---|---|
| 1 | Wake Word Detection | `WakeWordDetector` component; Section 8.1 | Design |
| 1a | Deepgram Streaming Transcription | `StreamingTranscriber` component; Section 8.2 | Design |
| 2 | Agent State Control (`set_next_state`) | `AgentDone.next_state`; Section 8.3 | Design |
| 3 | Subagent Spawning | `TaskResult` event; Section 8.4 | Deferred |
| 4 | Visual Status Dot | `Display` Protocol; Section 8.5 | Deferred |

---

## Current Baseline

Push-to-talk voice agent. User presses Enter to record, releases to send. ElevenLabs batch STT. Deepgram streaming STT already wired in (`voice/transcribe.py`). Agent loop with concurrent tool execution. ElevenLabs TTS + sounddevice playback. Interruptible via Enter.

No event bus. No orchestrator. No wake word.

---

## Archived Spec Files (Superseded)

These files are kept for reference but are superseded by `architecture.md`:

| File | Superseded by |
|---|---|
| [feature-1-wake-word.md](feature-1-wake-word.md) | architecture.md §2, §8.1 |
| [feature-1a-deepgram-transcription.md](feature-1a-deepgram-transcription.md) | architecture.md §2, §8.2 |
| [feature-2-free-order-of-actions.md](feature-2-free-order-of-actions.md) | architecture.md §3, §8.3 |
| [always-listening.md](always-listening.md) | architecture.md (full replacement) |
