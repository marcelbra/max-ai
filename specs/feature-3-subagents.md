# Feature 3: Subagent Spawning

## Depends On
Feature 2 (agent.next_state). The main agent should call `set_next_state("idle")` after spawning — so it can be done while the subagent runs in the background.

---

## What This Adds

The agent can offload long-running tasks to a background subagent. The main agent responds immediately and returns to idle. The subagent runs a separate Anthropic API call, and when it finishes it delivers its result to the user via TTS (when the main agent is not busy).

**Example:**
```
User: "Max, find me the best noise-cancelling headphones under 300 euros"

Main agent:
  1. spawn_subagent("Search for best noise-cancelling headphones under €300...")
  2. message: "On it. I'll let you know when I have results."
  3. set_next_state("idle")

[30 seconds pass, user does other things]

Subagent finishes → TTS: "I found the results for headphones. The Sony WH-1000XM5
  at 279 euros has the best noise cancellation..."
```

---

## When to Spawn a Subagent

The agent decides. Via system prompt guidance:

**Spawn when:**
- Task involves multiple sequential tool calls (research + summarize)
- Task involves web search + synthesis
- User says "look into this", "do some research", "take your time"
- Task will clearly take more than ~5 seconds

**Do NOT spawn when:**
- Single tool call (skip song, check weather, set timer)
- Simple Q&A with no external lookups
- Anything instant

---

## New File: `src/max_ai/agent/subagent.py`

```python
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import anthropic

from max_ai.tools.registry import ToolRegistry


SUBAGENT_SYSTEM_PROMPT = """You are a background worker for Max, a voice assistant.
You have been given a specific task to complete.

Rules:
- Complete the task thoroughly.
- Your output will be read aloud, so write in natural spoken prose.
- No markdown. No bullet points. No bold or italic text. No headers.
- Be concise: 2-4 sentences unless the task explicitly asks for detail.
- If a tool call fails, retry once, then report the failure clearly in plain speech.
- Do not say "certainly" or "of course" or similar filler phrases."""


class SubagentStatus(Enum):
    SPAWNED = "spawned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DELIVERED = "delivered"


@dataclass
class SubagentTask:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    status: SubagentStatus = SubagentStatus.SPAWNED
    result: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    notify_when_done: bool = True
    priority: str = "normal"
    _asyncio_task: asyncio.Task[None] | None = field(default=None, repr=False)


class SubagentManager:
    def __init__(self, max_concurrent: int = 3) -> None:
        self.tasks: dict[str, SubagentTask] = {}
        self._max_concurrent = max_concurrent

    def spawn(
        self,
        description: str,
        notify_when_done: bool = True,
        priority: str = "normal",
    ) -> SubagentTask:
        task = SubagentTask(
            description=description,
            notify_when_done=notify_when_done,
            priority=priority,
        )
        self.tasks[task.task_id] = task
        return task

    def get_active_tasks(self) -> list[SubagentTask]:
        active_statuses = {SubagentStatus.SPAWNED, SubagentStatus.RUNNING}
        return [task for task in self.tasks.values() if task.status in active_statuses]

    def active_count(self) -> int:
        return len(self.get_active_tasks())

    def is_at_capacity(self) -> bool:
        return self.active_count() >= self._max_concurrent

    def cancel(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if task is None:
            return False
        if task.status not in {SubagentStatus.SPAWNED, SubagentStatus.RUNNING}:
            return False
        if task._asyncio_task is not None:
            task._asyncio_task.cancel()
        task.status = SubagentStatus.CANCELLED
        return True


async def run_subagent(
    task: SubagentTask,
    client: anthropic.AsyncAnthropic,
    registry: ToolRegistry,
    event_queue: asyncio.Queue[dict[str, Any]],
    model: str,
    timeout_seconds: int,
) -> None:
    """Run a subagent task in the background. Puts result into event_queue when done."""
    task.status = SubagentStatus.RUNNING

    async def _execute() -> None:
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": task.description}
        ]
        tools = registry.get_api_tools()

        # Simple single-shot call — subagents don't loop over tool use
        # (they may need multiple rounds; keep it simple: one pass, up to 5 tool calls)
        for _ in range(5):
            response = await client.messages.create(
                model=model,
                system=SUBAGENT_SYSTEM_PROMPT,
                messages=messages,
                tools=tools if tools else [],
                max_tokens=512,
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                text_blocks = [block.text for block in response.content if block.type == "text"]
                task.result = " ".join(text_blocks).strip()
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        try:
                            result = await registry.execute(block.name, block.input)
                        except Exception as exception:
                            result = f"Error: {exception}"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })
                messages.append({"role": "user", "content": tool_results})
                continue

            break  # unexpected stop reason

        if task.result is None:
            task.result = "I wasn't able to complete that task."

    try:
        await asyncio.wait_for(_execute(), timeout=timeout_seconds)
        task.status = SubagentStatus.COMPLETED
        task.completed_at = datetime.now()

        if task.notify_when_done:
            await event_queue.put({
                "type": "subagent_result",
                "task_id": task.task_id,
                "result": task.result,
            })

    except asyncio.TimeoutError:
        task.status = SubagentStatus.FAILED
        task.error = "timed out"
        await event_queue.put({
            "type": "subagent_error",
            "task_id": task.task_id,
            "message": "The background task I was working on timed out. Want me to try again?",
        })

    except asyncio.CancelledError:
        task.status = SubagentStatus.CANCELLED
        raise

    except Exception as exception:
        task.status = SubagentStatus.FAILED
        task.error = str(exception)
        await event_queue.put({
            "type": "subagent_error",
            "task_id": task.task_id,
            "message": f"The background task failed: {exception}",
        })
```

---

## New File: `src/max_ai/tools/subagent.py`

```python
import asyncio
from typing import Any

import anthropic

from max_ai.agent.subagent import SubagentManager, SubagentTask, run_subagent
from max_ai.tools.base import BaseTool, ToolDefinition
from max_ai.tools.registry import ToolRegistry


class SubagentTools(BaseTool):
    def __init__(
        self,
        manager: SubagentManager,
        client: anthropic.AsyncAnthropic,
        subagent_registry: ToolRegistry,
        event_queue: asyncio.Queue[dict[str, Any]],
        model: str,
        timeout_seconds: int,
    ) -> None:
        self._manager = manager
        self._client = client
        self._subagent_registry = subagent_registry
        self._event_queue = event_queue
        self._model = model
        self._timeout_seconds = timeout_seconds

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="spawn_subagent",
                description=(
                    "Delegate a long-running task to a background subagent.\n\n"
                    "Use this when a task will take more than a few seconds: research, "
                    "multi-step workflows, web search + synthesis, file analysis.\n\n"
                    "Do NOT use for: single tool calls, simple Q&A, anything instant.\n\n"
                    "IMPORTANT: The subagent has no conversation history. Include ALL "
                    "relevant context in task_description."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "task_description": {
                            "type": "string",
                            "description": (
                                "Self-contained description of what the subagent should do. "
                                "Include all context — the subagent cannot see the conversation."
                            ),
                        },
                        "notify_when_done": {
                            "type": "boolean",
                            "description": "Whether to notify the user via TTS when done. Default true.",
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["normal", "high"],
                            "description": "Task priority. Default 'normal'.",
                        },
                    },
                    "required": ["task_description"],
                },
            ),
            ToolDefinition(
                name="list_background_tasks",
                description=(
                    "List all active background tasks. "
                    "Use when user asks 'what are you working on' or 'any updates'."
                ),
                input_schema={"type": "object", "properties": {}, "required": []},
            ),
            ToolDefinition(
                name="cancel_background_task",
                description=(
                    "Cancel a running background task. "
                    "Use when user says 'cancel that research' or 'never mind about X'."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "The task ID to cancel (from list_background_tasks).",
                        }
                    },
                    "required": ["task_id"],
                },
            ),
        ]

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        if tool_name == "spawn_subagent":
            return await self._spawn(tool_input)
        if tool_name == "list_background_tasks":
            return self._list_tasks()
        if tool_name == "cancel_background_task":
            return self._cancel(tool_input["task_id"])
        return f"Unknown tool: {tool_name}"

    async def _spawn(self, tool_input: dict[str, Any]) -> str:
        if self._manager.is_at_capacity():
            count = self._manager.active_count()
            return (
                f"Already running {count} background tasks. "
                "Ask the user if they want to wait or cancel one first."
            )

        task = self._manager.spawn(
            description=tool_input["task_description"],
            notify_when_done=tool_input.get("notify_when_done", True),
            priority=tool_input.get("priority", "normal"),
        )

        asyncio_task = asyncio.create_task(
            run_subagent(
                task=task,
                client=self._client,
                registry=self._subagent_registry,
                event_queue=self._event_queue,
                model=self._model,
                timeout_seconds=self._timeout_seconds,
            )
        )
        task._asyncio_task = asyncio_task

        return f"Background task started (id: {task.task_id})."

    def _list_tasks(self) -> str:
        active = self._manager.get_active_tasks()
        if not active:
            return "No background tasks running."
        lines = [f"{task.task_id}: {task.description[:80]} ({task.status.value})" for task in active]
        return "\n".join(lines)

    def _cancel(self, task_id: str) -> str:
        if self._manager.cancel(task_id):
            return f"Task {task_id} cancelled."
        return f"Task {task_id} not found or already finished."
```

---

## Changes to `cli.py`

```python
from max_ai.agent.subagent import SubagentManager
from max_ai.tools.subagent import SubagentTools

# Build subagent registry (restricted tool subset)
subagent_registry = ToolRegistry()
subagent_registry.register(DocumentTools(document_service=document_service))
if settings.enable_web_search:
    # web search tool added separately (same as main agent)
    pass  # handled via web_search_tool param in run_subagent

subagent_manager = SubagentManager(max_concurrent=settings.subagent_max_concurrent)

registry.register(SubagentTools(
    manager=subagent_manager,
    client=client,
    subagent_registry=subagent_registry,
    event_queue=event_queue,
    model=settings.subagent_model or settings.model,
    timeout_seconds=settings.subagent_timeout_s,
))
```

---

## Changes to `voice/listen_loop.py` (and `voice/loop.py`)

Both loops already handle `event_queue`. Extend event dispatch to handle subagent events:

```python
event = await event_queue.get()

match event.get("type"):
    case "subagent_result":
        await _deliver_subagent_result(event["result"], state_machine)
    case "subagent_error":
        await _deliver_subagent_result(event["message"], state_machine)
    case _:
        # existing: timer events etc.
        user_text = event.get("text", "")
        ...


async def _deliver_subagent_result(result: str, state_machine: StateMachine) -> None:
    """Wait for a safe delivery window, then speak the result."""
    # Don't interrupt SPEAKING or PROCESSING
    while state_machine.state in (AssistantState.SPEAKING, AssistantState.PROCESSING):
        await asyncio.sleep(0.3)

    # If user is mid-utterance, wait a moment
    if state_machine.state == AssistantState.LISTENING:
        await asyncio.sleep(2.0)

    state_machine.transition(AssistantState.SPEAKING)
    await speak(f"Update on your earlier request: {result}", ...)
    state_machine.on_tts_complete()
```

For push-to-talk `voice/loop.py`: same logic, but without the full state machine. Just check if TTS is currently playing and queue if so.

---

## Changes to `config.py`

```python
subagent_model: str = ""       # empty = use same model as main agent
subagent_max_concurrent: int = 3
subagent_timeout_s: int = 120
```

---

## Changes to `agent/system_prompt.j2`

Add:
```
For long-running tasks (research, web search + synthesis, multi-step workflows),
use spawn_subagent. Pass ALL relevant context in task_description — the subagent
has no conversation history. Then tell the user you're working on it and call
set_next_state("idle").

For instant tasks (single tool call, simple Q&A), handle directly. Don't spawn
a subagent for anything that finishes in seconds.
```

---

## Subagent Tool Subset

Subagents can use:
- `DocumentTools` — read/write documents
- `AnthropicWebSearch` — if enabled

Subagents cannot use:
- `SetNextStateTool` — irrelevant (subagents don't control the state machine)
- `SubagentTools` — no recursive spawning
- `SpotifyTools`, `CalendarTools`, `TimerTool`, `AlarmTool` — side effects on user's environment

---

## New Environment Variables

| Env Var | Required | Description |
|---|---|---|
| `MAX_AI_SUBAGENT_MODEL` | No | Model for subagents. Defaults to main model. |
| `MAX_AI_SUBAGENT_MAX_CONCURRENT` | No | Max parallel subagents. Default: 3 |
| `MAX_AI_SUBAGENT_TIMEOUT_S` | No | Timeout per subagent in seconds. Default: 120 |

---

## No New Dependencies

This feature requires no new packages.

---

## Edge Cases

| Scenario | Behavior |
|---|---|
| `spawn_subagent` called when at max_concurrent | Returns error message; main agent tells user |
| Subagent exceeds timeout | `SubagentStatus.FAILED`; error event in queue → TTS notification |
| Multiple subagents finish simultaneously | Events queue up; delivered one at a time |
| User cancels mid-run | `asyncio.Task.cancel()` → `CancelledError` handled → `CANCELLED` status |
| Subagent needs conversation history | Must be packed into `task_description` by main agent — enforced by design |
| LISTENING when result arrives | Wait 2 seconds, then deliver |

---

## Tests

**`tests/agent/test_subagent.py`**
- `SubagentManager.spawn()` creates task with `SPAWNED` status
- `SubagentManager.cancel()` returns True for active task, False for completed
- `SubagentManager.is_at_capacity()` returns True when max reached
- `run_subagent()` with mocked Anthropic client: RUNNING → COMPLETED → event_queue
- `run_subagent()` timeout: FAILED → error event in queue
- `run_subagent()` cancelled: `CancelledError` propagates cleanly, status = CANCELLED

**`tests/tools/test_subagent.py`**
- `spawn_subagent` calls `manager.spawn()` and creates asyncio task
- `spawn_subagent` when at capacity returns capacity message
- `list_background_tasks` returns formatted active task list
- `cancel_background_task` with valid ID returns success message
- `cancel_background_task` with invalid ID returns not-found message

**`tests/voice/test_listen_loop.py`** (extend)
- `subagent_result` event in queue → `_deliver_subagent_result` called
- Delivery waits when state is SPEAKING
- Delivery waits when state is PROCESSING
- Delivery proceeds when state is IDLE
