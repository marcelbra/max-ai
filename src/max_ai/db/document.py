"""Document persistence."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select

from max_ai.db.base import BaseService
from max_ai.db.models import Document


class DocumentService(BaseService):
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
                select(Document)
                .where(
                    Document.status == "active",
                    or_(Document.title.like(pattern), Document.content.like(pattern)),
                )
                .order_by(Document.created_at.desc())
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
