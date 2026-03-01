"""Tests for DocumentTools."""

import pytest

from max_ai.db import DocumentService
from max_ai.tools.documents import DocumentTools


@pytest.fixture
async def document_tools(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path}/docs.db"
    store = DocumentService(database_url=url)
    await store.init_db()
    yield DocumentTools(store=store)
    await store.close()


async def test_document_create(document_tools):
    result = await document_tools.execute(
        "document_create", {"title": "My Doc", "content": "Hello"}
    )
    assert "created" in result.lower()


async def test_document_read(document_tools):
    await document_tools.execute(
        "document_create", {"title": "Read Me", "content": "contents here"}
    )
    result = await document_tools.execute("document_read", {"title": "Read Me"})
    assert "Read Me" in result
    assert "contents here" in result


async def test_document_read_not_found(document_tools):
    result = await document_tools.execute("document_read", {"title": "Nope"})
    assert "not found" in result


async def test_document_edit(document_tools):
    await document_tools.execute("document_create", {"title": "Editable", "content": "old"})
    await document_tools.execute("document_edit", {"title": "Editable", "new_content": "new"})
    result = await document_tools.execute("document_read", {"title": "Editable"})
    assert "new" in result


async def test_document_archive(document_tools):
    await document_tools.execute("document_create", {"title": "To Archive", "content": "bye"})
    result = await document_tools.execute("document_archive", {"title": "To Archive"})
    assert "archived" in result.lower()


async def test_document_list(document_tools):
    await document_tools.execute("document_create", {"title": "Doc A", "content": "a"})
    await document_tools.execute("document_create", {"title": "Doc B", "content": "b"})
    result = await document_tools.execute("document_list", {})
    assert "Doc A" in result
    assert "Doc B" in result


async def test_document_list_empty(document_tools):
    result = await document_tools.execute("document_list", {})
    assert "No documents" in result


async def test_document_search(document_tools):
    await document_tools.execute(
        "document_create", {"title": "Python Tips", "content": "use comprehensions"}
    )
    await document_tools.execute(
        "document_create", {"title": "Go Notes", "content": "use goroutines"}
    )
    result = await document_tools.execute("document_search", {"query": "comprehensions"})
    assert "Python Tips" in result
    assert "Go Notes" not in result


async def test_document_search_no_match(document_tools):
    result = await document_tools.execute("document_search", {"query": "xyznotfound"})
    assert "No documents" in result


async def test_document_unknown_tool(document_tools):
    result = await document_tools.execute("document_nonexistent", {})
    assert "Unknown tool" in result
