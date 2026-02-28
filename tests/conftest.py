"""Shared test fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from max_ai.tools.registry import ToolRegistry


@pytest.fixture
def empty_registry() -> ToolRegistry:
    return ToolRegistry()


@pytest.fixture
def mock_anthropic_client() -> MagicMock:
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock()
    return client
