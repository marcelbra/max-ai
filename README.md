# max-ai

A personal AI agent you talk to. Powered by Claude, it listens through your microphone, thinks, uses tools, and speaks back. It can control Spotify, manage documents, schedule calendar events, set timers, and answer questions — all via natural conversation.

## Features

| Capability | What it does |
|---|---|
| **Voice I/O** | Push-to-talk recording with noise reduction, ElevenLabs STT/TTS, interrupt mid-speech |
| **Spotify** | Play/pause, search tracks, control volume, queue music |
| **Documents** | Create, read, edit, archive, and search markdown notes (stored in SQLite) |
| **Calendar** | List, create, update, and delete macOS Calendar events |
| **Timers** | Background timers that fire as agent messages |
| **Web Search** | Real-time search via Anthropic's built-in server tool |
| **Persistence** | Full conversation history saved to SQLite, resumed on next start |

## Requirements

- Python 3.12+
- macOS (Calendar integration is macOS-only; other features work anywhere)
- Microphone + speakers (for voice mode)
- [uv](https://docs.astral.sh/uv/) — fast Python package manager

## Setup

### 1. Install dependencies

```bash
git clone https://github.com/yourname/max-ai
cd max-ai
make install
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in the required key:

```env
MAX_AI_ANTHROPIC_API_KEY=sk-ant-...   # required
```

See the full list of environment variables below.

### 3. (Optional) Install dev tools

```bash
make dev   # installs dev deps + pre-commit hooks
```

### 4. Run

```bash
make voice
```

Press `Enter` to start recording. Press `Enter` again to send. Press `x` to quit.

---

## Environment Variables

All variables use the `MAX_AI_` prefix. Only the Anthropic API key is required.

| Variable | Required | Default | Description |
|---|---|---|---|
| `MAX_AI_ANTHROPIC_API_KEY` | **Yes** | — | Your Anthropic API key |
| `MAX_AI_MODEL` | No | `claude-sonnet-4-6` | Claude model to use |
| `MAX_AI_MAX_TOKENS` | No | `4096` | Max tokens per response |
| `MAX_AI_DATABASE_URL` | No | `sqlite+aiosqlite://~/.max-ai/max_ai.db` | Database connection string |
| `MAX_AI_ELEVENLABS_API_KEY` | Voice only | — | ElevenLabs API key |
| `MAX_AI_ELEVENLABS_VOICE_ID` | No | `JBFqnCBsd6RMkjVDRZzb` | Voice preset (default: George) |
| `MAX_AI_ELEVENLABS_TTS_MODEL` | No | `eleven_turbo_v2_5` | TTS model |
| `MAX_AI_ELEVENLABS_STT_MODEL` | No | `scribe_v1` | STT model |
| `MAX_AI_ELEVENLABS_STT_LANGUAGE` | No | `en` | Speech language (ISO 639-1) |
| `MAX_AI_SPOTIFY_CLIENT_ID` | Spotify only | — | Spotify app client ID |
| `MAX_AI_SPOTIFY_CLIENT_SECRET` | Spotify only | — | Spotify app client secret |
| `MAX_AI_SPOTIFY_REDIRECT_URI` | No | `http://127.0.0.1:8888/callback` | OAuth redirect URI |
| `MAX_AI_LANGWATCH_API_KEY` | No | — | LangWatch tracing key (optional) |
| `MAX_AI_ENABLE_WEB_SEARCH` | No | `true` | Enable Anthropic web search tool |
| `MAX_AI_WEB_SEARCH_MAX_USES` | No | `5` | Max searches per agent turn |
| `MAX_AI_DEBUG` | No | `false` | Save raw/denoised audio to `~/.max-ai/debug/` |

---

## Optional Integrations

### Spotify

1. Create an app at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Copy the Client ID and Secret into `.env`
3. Run `make setup-spotify` — opens a browser for OAuth, saves token to `~/.max-ai/`

### macOS Calendar

```bash
make setup-calendar   # grants Calendar permissions via osascript
```

### LangWatch (tracing)

Add `MAX_AI_LANGWATCH_API_KEY` to `.env`. Agent turns are automatically traced.

---

## Make Targets

| Target | Description |
|---|---|
| `make voice` | Start the agent (voice mode) |
| `make install` | Install dependencies |
| `make dev` | Install dev deps + pre-commit hooks |
| `make test` | Run all tests |
| `make lint` | Check code style with ruff |
| `make lint-fix` | Auto-fix formatting issues |
| `make typecheck` | Run mypy (strict mode) |
| `make setup-spotify` | Spotify OAuth setup |
| `make setup-calendar` | Grant Calendar permissions |
| `make voice-dev` | Debug mode: record and save WAV files |
| `make migrate` | Run Alembic migrations (production) |
| `make clean` | Remove caches |

---

## Architecture

```
src/max_ai/
├── cli.py                   # Entry point
├── config.py                # Settings (pydantic-settings)
├── persistence.py           # SQLAlchemy models: conversations, documents
├── agent/
│   ├── loop.py              # Agentic loop: tool_use → execute → repeat
│   ├── prompts.py           # Jinja2 system prompt loader
│   └── tools/
│       ├── registry.py      # Tool dispatcher (concurrent execution)
│       ├── spotify.py       # Spotify playback tools
│       ├── documents.py     # Markdown document CRUD
│       ├── calendar.py      # macOS Calendar tools (JXA)
│       ├── timer.py         # Background timer tool
│       └── alarm.py         # Audio alarm (beeps)
└── voice/
    ├── loop.py              # Voice REPL: record → transcribe → agent → speak
    ├── recorder.py          # Microphone capture + noise reduction
    ├── stt.py               # ElevenLabs speech-to-text
    └── tts.py               # ElevenLabs text-to-speech + playback
```

### Agent Loop

1. Call Claude with conversation history + tool schemas
2. On `tool_use` → execute tools concurrently, append results, loop
3. On `end_turn` → yield text response, done

### Voice Loop

1. Wait for `Enter` → record until `Enter` again
2. Denoise audio (two-pass spectral gating)
3. Transcribe via ElevenLabs STT
4. Run agent turn (with spinner + tool labels)
5. Synthesize and play TTS response
6. Save turn to SQLite, resume from next input

---

## Development

```bash
# Run all checks (required before committing)
make lint && make typecheck && make test

# Auto-fix formatting then test
make lint-fix && make test

# Debug audio pipeline
make voice-dev
```

Tests are in `tests/` and mirror the `src/` layout. All tests use in-memory SQLite — no external API calls.
