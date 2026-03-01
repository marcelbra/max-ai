> **Superseded** — This spec is archived. The canonical design is in [architecture.md](architecture.md) (§3 state table `AgentDone` row, §8.3 Feature 2 mapping).

# Feature 2: Free Order of Actions

## Depends On
Feature 1 (state machine). The `set_next_state` tool is meaningful in both modes, but `StateMachine` from Feature 1 is needed to act on it in wake word mode.

---

## What This Adds

A `set_next_state` tool the agent can call during any turn. After TTS finishes, the voice loop reads the agent's declared state and transitions accordingly instead of always going to IDLE.

**Without this feature:** Every turn ends the same way — agent speaks, then waits for the next push-to-talk input (or returns to IDLE in wake word mode).

**With this feature:**
- Agent asks a question → calls `set_next_state("listening")` → after speaking, automatically starts listening again
- Agent completes a task → calls `set_next_state("idle")` → returns to idle as before
- Agent never calls it → defaults to `"idle"` (no behavior change)

**Works in both modes:**
- Push-to-talk: `"listening"` means auto-start recording immediately after TTS (skip waiting for Enter)
- Wake word: `"listening"` means transition to `LISTENING` state after TTS

---

## How It Works

`set_next_state` is a normal tool registered in the `ToolRegistry`. When the agent calls it, the tool sets `agent.next_state` as a side effect and returns `"ok"` to the API. The agent loop continues normally (feeding "ok" back). After `run()` completes, the caller reads `agent.next_state`.

If called multiple times, the last call wins. If never called, `next_state` stays `None` → defaults to idle.

---

## Changes to `agent/agent.py`

Add one attribute and reset it at the top of `run()`:

```python
class Agent:
    def __init__(self, ...) -> None:
        ...
        self.next_state: str | None = None  # set by set_next_state tool during run()

    async def run(self, user_message: str, ...) -> AsyncIterator[str]:
        self.next_state = None  # reset at start of every turn
        ...
        # rest of run() unchanged
```

No other changes to `agent.py`. The tool is executed via the registry like any other tool.

---

## New File: `src/max_ai/tools/state.py`

```python
from collections.abc import Callable
from typing import Any

from max_ai.tools.base import BaseTool, ToolDefinition


class SetNextStateTool(BaseTool):
    def __init__(self, on_state: Callable[[str], None]) -> None:
        """
        on_state: called with "listening" or "idle" when agent invokes this tool.
        In practice: lambda state: setattr(agent, "next_state", state)
        """
        self._on_state = on_state

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="set_next_state",
                description=(
                    "Set the assistant's next state after you finish responding.\n\n"
                    "Use 'listening' when:\n"
                    "- You asked the user a question\n"
                    "- You need follow-up input before the task is complete\n\n"
                    "Use 'idle' when:\n"
                    "- A task or action is complete and no follow-up is needed\n"
                    "- You delivered information and asked no question\n\n"
                    "Call this once per turn. If called multiple times, the last call wins. "
                    "If you don't call it, the system defaults to 'idle'."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "enum": ["listening", "idle"],
                            "description": "The state to transition to after TTS playback completes.",
                        }
                    },
                    "required": ["state"],
                },
            )
        ]

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        self._on_state(tool_input["state"])
        return "ok"
```

---

## Changes to `cli.py`

Register `SetNextStateTool` after the agent is created, passing a setter that writes to `agent.next_state`:

```python
agent = Agent(client=client, registry=registry, system=system_prompt)

registry.register(
    SetNextStateTool(on_state=lambda state: setattr(agent, "next_state", state))
)
```

---

## Changes to `voice/listen_loop.py` (wake word mode)

After the agent turn, read `agent.next_state` and tell the state machine what to do after TTS:

```python
from max_ai.voice.state_machine import AssistantState

full_response = await _run_agent_turn(agent, transcript, conversation_id)

if full_response:
    # Determine post-TTS state
    if agent.next_state == "listening":
        state_machine.set_post_speak_state(AssistantState.LISTENING)
    else:
        state_machine.set_post_speak_state(AssistantState.IDLE)

    state_machine.transition(AssistantState.SPEAKING)
    await speak(full_response, ...)
    state_machine.on_tts_complete()  # transitions to the declared state
else:
    state_machine.transition(AssistantState.IDLE)
```

---

## Changes to `voice/loop.py` (push-to-talk mode)

After agent turn + TTS, check `agent.next_state`:

```python
# After speaking:
if agent.next_state == "listening":
    auto_start = True  # skip waiting for Enter, go straight to recording
else:
    auto_start = False  # normal: wait for Enter
```

`auto_start` already exists in `loop.py` (it's set when the user interrupts TTS). Reuse the same mechanism.

---

## Changes to `agent/system_prompt.j2`

Add at the end of the system prompt:

```
After completing a request, call set_next_state:
- "listening" — if you asked a question or need the user's follow-up
- "idle" — if the task is done and no follow-up is needed
If unsure, use "idle". Keep it one call per turn.
```

---

## Edge Cases

| Scenario | Behavior |
|---|---|
| Agent calls `set_next_state` twice | Last call wins — attribute is overwritten each time |
| Agent never calls it | `agent.next_state` stays `None` → treated as `"idle"` |
| Agent calls it before a tool result returns | Captured immediately; API still gets `"ok"` result; loop continues normally |
| Push-to-talk + `"listening"` | Auto-starts recording after TTS, same as when user interrupts TTS |

---

## Tests

**`tests/tools/test_state.py`**
- `execute()` calls `on_state` with correct value (`"listening"` or `"idle"`)
- `definitions()` returns one tool with correct name and enum values
- Calling execute twice calls `on_state` twice (last call wins at the agent level, not tool level)

**`tests/agent/test_agent.py`** (extend existing)
- `agent.next_state` is `None` at start of each `run()` call even if previous run set it
- After a turn where set_next_state tool is called, `agent.next_state` reflects the value

**`tests/voice/test_listen_loop.py`** (extend)
- `agent.next_state == "listening"` → `set_post_speak_state(LISTENING)` called
- `agent.next_state == None` → `set_post_speak_state(IDLE)` called

---

## No New Dependencies

This feature requires no new packages.
