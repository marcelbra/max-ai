"""SQLAlchemy-backed conversation persistence. Works with SQLite or PostgreSQL."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import ForeignKey, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from max_ai.config import settings


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    title: Mapped[str | None] = mapped_column(nullable=True)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    role: Mapped[str]
    content: Mapped[str]  # JSON-serialized content blocks
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


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
