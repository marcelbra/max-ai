"""Conversation and message persistence."""

import json
import uuid
from typing import Any

from sqlalchemy import select

from max_ai.db.base import BaseService
from max_ai.db.models import Conversation, Message


class ConversationService(BaseService):
    async def create_conversation(self, title: str | None = None) -> str:
        conv_id = str(uuid.uuid4())
        async with self.session_factory() as session:
            session.add(Conversation(id=conv_id, title=title))
            await session.commit()
        return conv_id

    async def append_message(self, conv_id: str, role: str, content: Any) -> None:
        serialized = json.dumps(content, default=str)
        async with self.session_factory() as session:
            session.add(Message(conversation_id=conv_id, role=role, content=serialized))
            await session.commit()

    async def get_messages(self, conv_id: str) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Message).where(Message.conversation_id == conv_id).order_by(Message.id)
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
            {"id": c.id, "title": c.title, "created_at": c.created_at.isoformat()} for c in rows
        ]
