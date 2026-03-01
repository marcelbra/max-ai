"""Typed event catalog for the voice assistant.

All events are frozen dataclasses.  The Event union is the only type that
flows through the bus.  Nothing in this module imports from other voice
modules — it is the shared leaf of the import graph.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Literal


class AssistantState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


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


Event = (
    AudioFrame
    | WakeWordDetected
    | TranscriptPartial
    | TranscriptFinal
    | UtteranceEnd
    | AgentText
    | AgentDone
    | TTSDone
    | TimerFired
    | TaskResult
    | StateChanged
)

EventBus = asyncio.Queue[Event]
