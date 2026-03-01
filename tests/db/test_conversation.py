"""Tests for ConversationService."""

import pathlib
from collections.abc import AsyncGenerator

import pytest

from max_ai.db import ConversationService


@pytest.fixture
async def conversation_store(tmp_path: pathlib.Path) -> AsyncGenerator[ConversationService, None]:
    url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    store = ConversationService(database_url=url)
    await store.init_db()
    yield store
    await store.close()


async def test_create_conversation_returns_id(conversation_store: ConversationService) -> None:
    conv_id = await conversation_store.create_conversation("My Chat")
    assert conv_id
    assert len(conv_id) == 36  # UUID format


async def test_append_and_get_messages(conversation_store: ConversationService) -> None:
    conv_id = await conversation_store.create_conversation()
    await conversation_store.append_message(conv_id, "user", "Hello")
    await conversation_store.append_message(conv_id, "assistant", "Hi!")
    messages = await conversation_store.get_messages(conv_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[1]["role"] == "assistant"


async def test_messages_ordered_by_insertion(conversation_store: ConversationService) -> None:
    conv_id = await conversation_store.create_conversation()
    for i in range(4):
        await conversation_store.append_message(conv_id, "user", f"msg {i}")
    messages = await conversation_store.get_messages(conv_id)
    assert [m["content"] for m in messages] == [f"msg {i}" for i in range(4)]


async def test_list_conversations(conversation_store: ConversationService) -> None:
    await conversation_store.create_conversation("First")
    await conversation_store.create_conversation("Second")
    convs = await conversation_store.list_conversations()
    assert len(convs) == 2
    titles = {c["title"] for c in convs}
    assert titles == {"First", "Second"}
