"""
Conversation Memory Manager
Loads and manages conversation history from SQLite.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from backend.models import Message, async_session

logger = logging.getLogger(__name__)

# Max messages to include in LLM context
MAX_CONTEXT_MESSAGES = 30


async def get_messages(
    conversation_id: str, limit: int = MAX_CONTEXT_MESSAGES
) -> list[dict]:
    """Load recent messages for a conversation.

    Returns list of {"role": ..., "content": ...} dicts for LLM consumption.
    """
    async with async_session() as session:
        result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = list(reversed(result.scalars().all()))

    return [{"role": m.role, "content": m.content} for m in messages]


async def save_message(
    conversation_id: str, role: str, content: str
) -> Message:
    """Save a message to the conversation."""
    async with async_session() as session:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return msg
