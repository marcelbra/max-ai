"""Tests for ConversationStore and DocumentStore."""

import pytest

from max_ai.db import ConversationService, DocumentService


@pytest.fixture
async def conversation_store(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    store = ConversationService(database_url=url)
    await store.init_db()
    yield store
    await store.close()


@pytest.fixture
async def document_store(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path}/docs.db"
    store = DocumentService(database_url=url)
    await store.init_db()
    yield store
    await store.close()


# --- ConversationStore ---


async def test_create_conversation_returns_id(conversation_store):
    conv_id = await conversation_store.create_conversation("My Chat")
    assert conv_id
    assert len(conv_id) == 36  # UUID format


async def test_append_and_get_messages(conversation_store):
    conv_id = await conversation_store.create_conversation()
    await conversation_store.append_message(conv_id, "user", "Hello")
    await conversation_store.append_message(conv_id, "assistant", "Hi!")
    messages = await conversation_store.get_messages(conv_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[1]["role"] == "assistant"


async def test_messages_ordered_by_insertion(conversation_store):
    conv_id = await conversation_store.create_conversation()
    for i in range(4):
        await conversation_store.append_message(conv_id, "user", f"msg {i}")
    messages = await conversation_store.get_messages(conv_id)
    assert [m["content"] for m in messages] == [f"msg {i}" for i in range(4)]


async def test_list_conversations(conversation_store):
    await conversation_store.create_conversation("First")
    await conversation_store.create_conversation("Second")
    convs = await conversation_store.list_conversations()
    assert len(convs) == 2
    titles = {c["title"] for c in convs}
    assert titles == {"First", "Second"}


# --- DocumentStore ---


async def test_document_create_and_read(document_store):
    result = await document_store.create("My Doc", "Hello world")
    assert "created" in result.lower()
    doc = await document_store.get_by_title("My Doc")
    assert doc is not None
    assert doc["content"] == "Hello world"
    assert doc["status"] == "active"


async def test_document_duplicate_title_rejected(document_store):
    await document_store.create("Unique", "First")
    result = await document_store.create("Unique", "Second")
    assert "Error" in result


async def test_document_not_found_returns_none(document_store):
    doc = await document_store.get_by_title("Nonexistent")
    assert doc is None


async def test_document_edit_content(document_store):
    await document_store.create("Editable", "Old content")
    await document_store.edit("Editable", new_content="New content")
    doc = await document_store.get_by_title("Editable")
    assert doc is not None
    assert doc["content"] == "New content"


async def test_document_archive_hides_from_active(document_store):
    await document_store.create("Archive Me", "content")
    result = await document_store.archive("Archive Me")
    assert "archived" in result.lower()
    doc = await document_store.get_by_title("Archive Me")
    assert doc is None  # no longer active


async def test_document_list_active_only(document_store):
    await document_store.create("Active Doc", "content")
    await document_store.create("To Archive", "content")
    await document_store.archive("To Archive")
    docs = await document_store.list_all()
    titles = [d["title"] for d in docs]
    assert "Active Doc" in titles
    assert "To Archive" not in titles


async def test_document_search_by_content(document_store):
    await document_store.create("Python Tips", "Use list comprehensions for speed")
    await document_store.create("Go Notes", "Use goroutines for concurrency")
    results = await document_store.search("comprehensions")
    assert len(results) == 1
    assert results[0]["title"] == "Python Tips"
