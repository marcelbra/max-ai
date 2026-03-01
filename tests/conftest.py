"""Shared test fixtures."""

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import anthropic
import pytest
from anthropic.resources import AsyncMessages

from max_ai.tools.registry import ToolRegistry


@pytest.fixture
def empty_registry() -> ToolRegistry:
    return ToolRegistry()


@pytest.fixture
def mock_anthropic_client() -> anthropic.AsyncAnthropic:
    client = cast(anthropic.AsyncAnthropic, MagicMock(spec=anthropic.AsyncAnthropic))
    client.messages = cast(AsyncMessages, MagicMock(spec=AsyncMessages))  # type: ignore[misc]
    client.messages.create = AsyncMock()  # type: ignore[method-assign]
    return client
