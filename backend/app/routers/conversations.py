from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Conversation

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(Conversation).order_by(Conversation.created_at.desc()))
    ).scalars().all()
    return [
        {"id": c.id, "title": c.title, "created_at": c.created_at.isoformat() if c.created_at else None}
        for c in rows
    ]


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    convo = await db.get(Conversation, conversation_id)
    if not convo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    await db.refresh(convo, ["messages"])
    return {
        "id": convo.id,
        "title": convo.title,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "mode": m.mode,
                "retrieved_chunk_ids": m.retrieved_chunk_ids,
                "token_usage": m.token_usage,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in convo.messages
        ],
    }
