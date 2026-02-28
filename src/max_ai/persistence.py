"""SQLAlchemy-backed conversation persistence. Works with SQLite or PostgreSQL."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import ForeignKey, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from max_ai.config import settings


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    title: Mapped[str | None] = mapped_column(nullable=True)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    role: Mapped[str]
    content: Mapped[str]  # JSON-serialized content blocks
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str]
    content: Mapped[str]
    status: Mapped[str] = mapped_column(default="active")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))


def _ensure_db_dir(database_url: str) -> None:
    """Create parent directory for SQLite databases if needed."""
    if "sqlite" in database_url:
        # Extract path from sqlite+aiosqlite:///path
        path_part = database_url.split("///", 1)[-1]
        db_path = Path(path_part).expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)


class ConversationStore:
    def __init__(self, database_url: str = settings.database_url) -> None:
        _ensure_db_dir(database_url)
        self.engine = create_async_engine(database_url, echo=False)
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession)

    async def init_db(self) -> None:
        """Create tables if they don't exist (dev convenience — use alembic in prod)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def create_conversation(self, title: str | None = None) -> str:
        conv_id = str(uuid.uuid4())
        async with self.session_factory() as session:
            session.add(Conversation(id=conv_id, title=title))
            await session.commit()
        return conv_id

    async def append_message(self, conv_id: str, role: str, content: Any) -> None:
        serialized = json.dumps(content, default=str)
        async with self.session_factory() as session:
            session.add(
                Message(conversation_id=conv_id, role=role, content=serialized)
            )
            await session.commit()

    async def get_messages(self, conv_id: str) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Message)
                .where(Message.conversation_id == conv_id)
                .order_by(Message.id)
            )
            rows = result.scalars().all()
        return [{"role": m.role, "content": json.loads(m.content)} for m in rows]

    async def list_conversations(self, limit: int = 20) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Conversation).order_by(Conversation.created_at.desc()).limit(limit)
            )
            rows = result.scalars().all()
        return [
            {"id": c.id, "title": c.title, "created_at": c.created_at.isoformat()}
            for c in rows
        ]

    async def close(self) -> None:
        await self.engine.dispose()


class DocumentStore:
    def __init__(self, database_url: str = settings.database_url) -> None:
        _ensure_db_dir(database_url)
        self.engine = create_async_engine(database_url, echo=False)
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession)

    async def init_db(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def create(self, title: str, content: str) -> str:
        async with self.session_factory() as session:
            existing = await session.execute(
                select(Document).where(Document.title == title, Document.status == "active")
            )
            if existing.scalar_one_or_none():
                return f"Error: a document with title '{title}' already exists."
            doc = Document(id=str(uuid.uuid4()), title=title, content=content)
            session.add(doc)
            await session.commit()
        return f"Document '{title}' created."

    async def get_by_title(self, title: str) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Document).where(Document.title == title, Document.status == "active")
            )
            doc = result.scalar_one_or_none()
        if doc is None:
            return None
        return {
            "id": doc.id,
            "title": doc.title,
            "content": doc.content,
            "status": doc.status,
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat(),
        }

    async def edit(
        self, title: str, new_title: str | None = None, new_content: str | None = None
    ) -> str:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Document).where(Document.title == title, Document.status == "active")
            )
            doc = result.scalar_one_or_none()
            if doc is None:
                return f"Error: document '{title}' not found."
            if new_title is not None:
                doc.title = new_title
            if new_content is not None:
                doc.content = new_content
            doc.updated_at = datetime.now(UTC)
            await session.commit()
        return f"Document '{title}' updated."

    async def archive(self, title: str) -> str:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Document).where(Document.title == title, Document.status == "active")
            )
            doc = result.scalar_one_or_none()
            if doc is None:
                return f"Error: document '{title}' not found."
            doc.status = "archived"
            doc.updated_at = datetime.now(UTC)
            await session.commit()
        return f"Document '{title}' archived."

    async def list_all(self, include_archived: bool = False) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            query = select(Document)
            if not include_archived:
                query = query.where(Document.status == "active")
            query = query.order_by(Document.created_at.desc())
            result = await session.execute(query)
            docs = result.scalars().all()
        return [
            {
                "title": d.title,
                "status": d.status,
                "created_at": d.created_at.isoformat(),
                "updated_at": d.updated_at.isoformat(),
            }
            for d in docs
        ]

    async def search(self, query: str) -> list[dict[str, Any]]:
        pattern = f"%{query}%"
        async with self.session_factory() as session:
            result = await session.execute(
                select(Document).where(
                    Document.status == "active",
                    or_(Document.title.like(pattern), Document.content.like(pattern)),
                ).order_by(Document.created_at.desc())
            )
            docs = result.scalars().all()
        return [
            {
                "title": d.title,
                "created_at": d.created_at.isoformat(),
                "updated_at": d.updated_at.isoformat(),
            }
            for d in docs
        ]

    async def close(self) -> None:
        await self.engine.dispose()
