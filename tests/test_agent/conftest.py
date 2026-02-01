"""Test fixtures for agent tests."""

from dataclasses import dataclass
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from max_ai.db import Base


@dataclass
class MockAgentDeps:
    """Mock dependencies for agent tool tests."""

    db: AsyncSession


@pytest.fixture
async def async_db():
    """Create an async in-memory SQLite database for testing."""
    # SQLite async URL
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session


@pytest.fixture
def mock_ctx(async_db):
    """Create a mock RunContext for tool testing."""

    class MockRunContext:
        def __init__(self, deps):
            self.deps = deps

    return MockRunContext(MockAgentDeps(db=async_db))
