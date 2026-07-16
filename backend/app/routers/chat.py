"""VectorGuard-compatible chat endpoint.

Contract (see VECTORGUARD_TARGET.md):
  request : {"message": "...", "conversation_id": "optional"}
  response: {"answer": "...", "mode": "...", "conversation_id": "...",
             "retrieved_chunk_ids": [...], "citations": [...], ...}
`answer` is the stable response_path VectorGuard reads. The endpoint is usable
unauthenticated so it works as a generic HTTP target with zero adapter code.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..generation.generate import generate_answer
from ..models import Conversation, Message, User
from ..schemas import ChatRequest, ChatResponse, Citation
from ..security.auth import get_optional_user
from ..security.rate_limit import enforce
from ..config import settings

router = APIRouter(prefix="/api", tags=["chat"])


async def _load_history(db: AsyncSession, conversation_id: str) -> list[dict]:
    convo = await db.get(Conversation, conversation_id)
    if not convo:
        return []
    await db.refresh(convo, ["messages"])
    return [{"role": m.role, "content": m.content} for m in convo.messages]


async def _ensure_conversation(
    db: AsyncSession, conversation_id: str | None, user: User | None, first_msg: str
) -> Conversation:
    if conversation_id:
        convo = await db.get(Conversation, conversation_id)
        if convo:
            return convo
    convo = Conversation(
        id=conversation_id or None,
        user_id=user.id if user else None,
        title=first_msg[:60],
    )
    db.add(convo)
    await db.flush()
    return convo


def _citations(result) -> list[Citation]:
    return [
        Citation(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            filename=c.filename,
            section_path=c.section_path,
            score=round(c.rerank_score, 4),
        )
        for c in result.candidates
    ]


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request_ip: str = "anon",
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    await enforce("chat", user.id if user else "anon", settings.rate_limit_chat_per_min)

    history = await _load_history(db, body.conversation_id) if body.conversation_id else []
    result = await generate_answer(db, query=body.message, history=history)

    convo = await _ensure_conversation(db, body.conversation_id, user, body.message)
    chunk_ids = [c.chunk_id for c in result.candidates]
    db.add(Message(conversation_id=convo.id, role="user", content=body.message))
    db.add(
        Message(
            conversation_id=convo.id,
            role="assistant",
            content=result.answer,
            mode=result.mode,
            retrieved_chunk_ids=chunk_ids,
            token_usage=result.token_usage,
        )
    )
    await db.commit()

    return ChatResponse(
        answer=result.answer,
        mode=result.mode,
        conversation_id=convo.id,
        retrieved_chunk_ids=chunk_ids,
        citations=_citations(result),
        confidence=round(result.confidence, 4),
        grounded=result.grounded,
        token_usage=result.token_usage,
    )


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """SSE streaming for the frontend. Not the VectorGuard target — /api/chat is."""
    await enforce("chat", user.id if user else "anon", settings.rate_limit_chat_per_min)
    history = await _load_history(db, body.conversation_id) if body.conversation_id else []
    result = await generate_answer(db, query=body.message, history=history)
    convo = await _ensure_conversation(db, body.conversation_id, user, body.message)
    chunk_ids = [c.chunk_id for c in result.candidates]
    db.add(Message(conversation_id=convo.id, role="user", content=body.message))
    db.add(
        Message(
            conversation_id=convo.id,
            role="assistant",
            content=result.answer,
            mode=result.mode,
            retrieved_chunk_ids=chunk_ids,
            token_usage=result.token_usage,
        )
    )
    await db.commit()

    async def event_stream():
        meta = {"conversation_id": convo.id, "mode": result.mode, "citations": [c.model_dump() for c in _citations(result)]}
        yield f"event: meta\ndata: {json.dumps(meta)}\n\n"
        for word in result.answer.split(" "):
            yield f"data: {json.dumps({'token': word + ' '})}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
