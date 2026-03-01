# Feature 4: Visual Status Dot

## Depends On
Feature 1 (state machine). The dot reflects `AssistantState` — which only exists in wake word mode.

## Standalone
This feature has no dependencies on Features 2 or 3. It can be implemented any time after Feature 1.

---

## What This Adds

A browser page served locally at `http://127.0.0.1:8420` showing a single centered dot. The dot animates to reflect the assistant's current state. Enabled with the `--ui` flag (or `MAX_AI_UI_ENABLED=true`).

```
max-ai --wakeword --ui   # wake word mode + dot UI
```

---

## Dot Appearance

| State | Color | Size | Animation |
|---|---|---|---|
| `idle` | Black (#111) | 20px | None — static |
| `idle` + background subagents running | Black (#111) | 20px | Faint blue ring, slow pulse (3s) |
| `listening` | Blue (#3b82f6) | 30px | Shimmer glow pulse (1.5s) |
| `processing` | Blue (#3b82f6) | 30px | Slow breathe (scale 1→1.15, 2s) |
| `speaking` | Blue (#3b82f6) | 30px | Rapid jitter/vibrate (50ms) |

---

## CLI Change

**`src/max_ai/__main__.py`**

```python
parser.add_argument("--ui", action="store_true", help="Enable visual status dot UI at localhost:8420")
```

**`src/max_ai/cli.py`**

```python
async def main(wakeword_mode: bool = False, ui_enabled: bool = False) -> None:
    ...
    state_machine = StateMachine()  # created here, passed to voice_listen_loop

    if ui_enabled:
        from max_ai.ui.server import UIServer
        ui_server = UIServer(host=settings.ui_host, port=settings.ui_port)
        ui_server.start()  # starts FastAPI in background thread
        state_machine.on_change(lambda old, new: ui_server.broadcast_state(new))
```

---

## New Files

### `src/max_ai/ui/__init__.py`

Empty.

---

### `src/max_ai/ui/server.py`

```python
import asyncio
import json
import threading
from typing import Any

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from max_ai.voice.state_machine import AssistantState


class UIServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8420) -> None:
        self._host = host
        self._port = port
        self._app = FastAPI()
        self._connected_clients: set[WebSocket] = set()
        self._current_state: AssistantState = AssistantState.IDLE
        self._background_task_count: int = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self._app.get("/")
        async def index() -> HTMLResponse:
            # Serve index.html inline (no static file server needed)
            html = (Path(__file__).parent / "static" / "index.html").read_text()
            return HTMLResponse(html)

        @self._app.websocket("/ws/status")
        async def status_websocket(websocket: WebSocket) -> None:
            await websocket.accept()
            self._connected_clients.add(websocket)
            try:
                # Send current state immediately on connect
                await websocket.send_text(self._make_message())
                while True:
                    await websocket.receive_text()  # keepalive (client sends nothing)
            except Exception:
                pass
            finally:
                self._connected_clients.discard(websocket)

    def _make_message(self) -> str:
        return json.dumps({
            "state": self._current_state.value,
            "background_tasks": self._background_task_count,
        })

    def start(self) -> None:
        """Start FastAPI server in a background daemon thread."""
        import uvicorn

        self._loop = asyncio.new_event_loop()

        def run() -> None:
            asyncio.set_event_loop(self._loop)
            config = uvicorn.Config(
                app=self._app,
                host=self._host,
                port=self._port,
                log_level="error",
                loop="asyncio",
            )
            server = uvicorn.Server(config)
            self._loop.run_until_complete(server.serve())

        thread = threading.Thread(target=run, daemon=True, name="ui-server")
        thread.start()

    def broadcast_state(self, new_state: AssistantState) -> None:
        """Called from StateMachine.on_change. Thread-safe."""
        self._current_state = new_state
        if self._loop is None or not self._connected_clients:
            return
        asyncio.run_coroutine_threadsafe(self._broadcast(), self._loop)

    def set_background_task_count(self, count: int) -> None:
        """Called by SubagentManager when task count changes. Thread-safe."""
        self._background_task_count = count
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._broadcast(), self._loop)

    async def _broadcast(self) -> None:
        message = self._make_message()
        dead_clients: set[WebSocket] = set()
        for client in list(self._connected_clients):
            try:
                await client.send_text(message)
            except Exception:
                dead_clients.add(client)
        self._connected_clients -= dead_clients
```

---

### `src/max_ai/ui/static/index.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Max</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      background: white;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      overflow: hidden;
    }

    #dot {
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: #111;
      transition: background 0.3s ease, width 0.3s ease, height 0.3s ease;
    }

    /* IDLE */
    #dot.idle {
      width: 20px;
      height: 20px;
      background: #111;
      animation: none;
      box-shadow: none;
    }

    /* IDLE with background subagents */
    #dot.idle.has-background {
      animation: background-pulse 3s ease-in-out infinite;
    }

    @keyframes background-pulse {
      0%, 100% { box-shadow: 0 0 6px 3px rgba(59,130,246,0.1); }
      50%       { box-shadow: 0 0 10px 5px rgba(59,130,246,0.25); }
    }

    /* LISTENING — shimmer glow */
    #dot.listening {
      width: 30px;
      height: 30px;
      background: #3b82f6;
      animation: shimmer 1.5s ease-in-out infinite;
    }

    @keyframes shimmer {
      0%, 100% { box-shadow: 0 0 8px 4px rgba(59,130,246,0.3); }
      50%       { box-shadow: 0 0 20px 10px rgba(59,130,246,0.6); }
    }

    /* PROCESSING — slow breathe */
    #dot.processing {
      width: 30px;
      height: 30px;
      background: #3b82f6;
      animation: breathe 2s ease-in-out infinite;
    }

    @keyframes breathe {
      0%, 100% { transform: scale(1); opacity: 0.7; }
      50%       { transform: scale(1.15); opacity: 1; }
    }

    /* SPEAKING — rapid jitter */
    #dot.speaking {
      width: 30px;
      height: 30px;
      background: #3b82f6;
      animation: vibrate 50ms linear infinite;
    }

    @keyframes vibrate {
      0%   { transform: translate(0, 0); }
      25%  { transform: translate(-2px, 1px); }
      50%  { transform: translate(2px, -1px); }
      75%  { transform: translate(-1px, -2px); }
      100% { transform: translate(1px, 2px); }
    }
  </style>
</head>
<body>
  <div id="dot" class="idle"></div>

  <script>
    const dot = document.getElementById('dot');

    function applyState(state, backgroundTasks) {
      // Remove all state classes
      dot.classList.remove('idle', 'listening', 'processing', 'speaking', 'has-background');

      dot.classList.add(state);

      if (state === 'idle' && backgroundTasks > 0) {
        dot.classList.add('has-background');
      }
    }

    function connect() {
      const ws = new WebSocket(`ws://${location.host}/ws/status`);

      ws.onmessage = (event) => {
        const { state, background_tasks } = JSON.parse(event.data);
        applyState(state, background_tasks || 0);
      };

      ws.onclose = () => {
        // Reconnect after 2s
        setTimeout(connect, 2000);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();
  </script>
</body>
</html>
```

---

## Changes to `config.py`

```python
ui_host: str = "127.0.0.1"
ui_port: int = 8420
```

(The `--ui` flag drives enabling, not a config field — keeps config clean.)

---

## Connecting Subagent Count (optional enhancement)

If Feature 3 is also implemented, wire `SubagentManager` to `UIServer.set_background_task_count()`:

In `cli.py`:
```python
if ui_enabled:
    # Hook subagent manager to update background task count in UI
    original_spawn = subagent_manager.spawn
    def spawn_and_notify(*args: Any, **kwargs: Any) -> SubagentTask:
        task = original_spawn(*args, **kwargs)
        ui_server.set_background_task_count(subagent_manager.active_count())
        return task
    subagent_manager.spawn = spawn_and_notify  # type: ignore[method-assign]
```

Or: add an `on_change` callback mechanism to `SubagentManager` (cleaner, but more code).

---

## New Environment Variables

| Env Var | Required | Description |
|---|---|---|
| `MAX_AI_UI_HOST` | No | Default: `127.0.0.1` |
| `MAX_AI_UI_PORT` | No | Default: `8420` |

---

## New Dependencies

| Package | Why | Install |
|---|---|---|
| `fastapi>=0.110` | WebSocket server + HTTP | `uv sync --extra ui` |
| `uvicorn>=0.29` | ASGI server | `uv sync --extra ui` |
| `websockets>=12.0` | WebSocket transport | `uv sync --extra ui` |

**`pyproject.toml`:**
```toml
[project.optional-dependencies]
ui = [
    "fastapi>=0.110",
    "uvicorn>=0.29",
    "websockets>=12.0",
]
```

**mypy overrides** (if fastapi/uvicorn have issues):
```toml
# fastapi and uvicorn are typed — no overrides needed
```

---

## Tests

**`tests/ui/test_server.py`**
- `UIServer.broadcast_state()` sends correct JSON to connected mock WebSocket clients
- WebSocket endpoint sends current state immediately on connect
- State change from IDLE → LISTENING → correct JSON `{"state": "listening", "background_tasks": 0}`
- `set_background_task_count(2)` → next broadcast includes `"background_tasks": 2`
- Dead client is removed from connected set on send error

---

## Notes

- The server runs in a daemon thread — it shuts down automatically when the main process exits.
- `uvicorn` log level is set to `"error"` to avoid cluttering the terminal output.
- The WebSocket client auto-reconnects every 2 seconds if the connection drops.
- Open `http://127.0.0.1:8420` in any browser. Works best as a small floating window.
