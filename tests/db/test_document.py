"""Tests for DocumentService."""

import pathlib
from collections.abc import AsyncGenerator

import pytest

from max_ai.db import DocumentService


@pytest.fixture
async def document_store(tmp_path: pathlib.Path) -> AsyncGenerator[DocumentService, None]:
    url = f"sqlite+aiosqlite:///{tmp_path}/docs.db"
    store = DocumentService(database_url=url)
    await store.init_db()
    yield store
    await store.close()


async def test_document_create_and_read(document_store: DocumentService) -> None:
    result = await document_store.create("My Doc", "Hello world")
    assert "created" in result.lower()
    doc = await document_store.get_by_title("My Doc")
    assert doc is not None
    assert doc["content"] == "Hello world"
    assert doc["status"] == "active"


async def test_document_duplicate_title_rejected(document_store: DocumentService) -> None:
    await document_store.create("Unique", "First")
    result = await document_store.create("Unique", "Second")
    assert "Error" in result


async def test_document_not_found_returns_none(document_store: DocumentService) -> None:
    doc = await document_store.get_by_title("Nonexistent")
    assert doc is None


async def test_document_edit_content(document_store: DocumentService) -> None:
    await document_store.create("Editable", "Old content")
    await document_store.edit("Editable", new_content="New content")
    doc = await document_store.get_by_title("Editable")
    assert doc is not None
    assert doc["content"] == "New content"


async def test_document_archive_hides_from_active(document_store: DocumentService) -> None:
    await document_store.create("Archive Me", "content")
    result = await document_store.archive("Archive Me")
    assert "archived" in result.lower()
    doc = await document_store.get_by_title("Archive Me")
    assert doc is None  # no longer active


async def test_document_list_active_only(document_store: DocumentService) -> None:
    await document_store.create("Active Doc", "content")
    await document_store.create("To Archive", "content")
    await document_store.archive("To Archive")
    docs = await document_store.list_all()
    titles = [d["title"] for d in docs]
    assert "Active Doc" in titles
    assert "To Archive" not in titles


async def test_document_search_by_content(document_store: DocumentService) -> None:
    await document_store.create("Python Tips", "Use list comprehensions for speed")
    await document_store.create("Go Notes", "Use goroutines for concurrency")
    results = await document_store.search("comprehensions")
    assert len(results) == 1
    assert results[0]["title"] == "Python Tips"
