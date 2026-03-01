"""Shared engine/session setup for all services."""

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from max_ai.config import settings
from max_ai.db.models import Base


def _ensure_db_dir(database_url: str) -> None:
    """Create parent directory for SQLite databases if needed."""
    if "sqlite" in database_url:
        path_part = database_url.split("///", 1)[-1]
        db_path = Path(path_part).expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)


class BaseService:
    def __init__(self, database_url: str = settings.database_url) -> None:
        _ensure_db_dir(database_url)
        self.engine = create_async_engine(database_url, echo=False)
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession)

    async def init_db(self) -> None:
        """Create tables if they don't exist (dev convenience — use alembic in prod)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()
