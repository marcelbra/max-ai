"""Tests for client creation."""

from unittest.mock import patch

import anthropic
import pytest


def test_create_client_raises_without_api_key() -> None:
    from max_ai.client import create_client

    with patch("max_ai.client.settings") as mock_settings:
        mock_settings.anthropic_api_key = ""
        with pytest.raises(ValueError, match="MAX_AI_ANTHROPIC_API_KEY"):
            create_client()


def test_create_client_returns_async_anthropic() -> None:
    from max_ai.client import create_client

    with patch("max_ai.client.settings") as mock_settings:
        mock_settings.anthropic_api_key = "sk-test-key"
        client = create_client()
    assert isinstance(client, anthropic.AsyncAnthropic)
