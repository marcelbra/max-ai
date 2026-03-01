"""Tests for ConversationService."""

import pathlib
from collections.abc import AsyncGenerator

import pytest

from max_ai.db import ConversationService


@pytest.fixture
async def conversation_service(tmp_path: pathlib.Path) -> AsyncGenerator[ConversationService, None]:
    url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    async with ConversationService(database_url=url) as conversation_service:
        yield conversation_service


async def test_create_conversation_returns_id(conversation_service: ConversationService) -> None:
    conv_id = await conversation_service.create_conversation("My Chat")
    assert conv_id
    assert len(conv_id) == 36  # UUID format


async def test_append_and_get_messages(conversation_service: ConversationService) -> None:
    conv_id = await conversation_service.create_conversation()
    await conversation_service.append_message(conv_id, "user", "Hello")
    await conversation_service.append_message(conv_id, "assistant", "Hi!")
    messages = await conversation_service.get_messages(conv_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[1]["role"] == "assistant"


async def test_messages_ordered_by_insertion(conversation_service: ConversationService) -> None:
    conv_id = await conversation_service.create_conversation()
    for i in range(4):
        await conversation_service.append_message(conv_id, "user", f"msg {i}")
    messages = await conversation_service.get_messages(conv_id)
    assert [m["content"] for m in messages] == [f"msg {i}" for i in range(4)]


async def test_list_conversations(conversation_service: ConversationService) -> None:
    await conversation_service.create_conversation("First")
    await conversation_service.create_conversation("Second")
    convs = await conversation_service.list_conversations()
    assert len(convs) == 2
    titles = {c["title"] for c in convs}
    assert titles == {"First", "Second"}
