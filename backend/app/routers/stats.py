from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_db
from ..models import Conversation, Document, DocumentChunk, Message, SecurityTestRun
from ..security.mode import current_mode

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db)):
    async def count(model, *where):
        stmt = select(func.count()).select_from(model)
        for w in where:
            stmt = stmt.where(w)
        return await db.scalar(stmt)

    return {
        "mode": current_mode(),
        "offline_llm": settings.offline_llm,
        "offline_embeddings": settings.offline_embeddings,
        "documents": await count(Document),
        "documents_clean": await count(Document, Document.corpus_label == "clean"),
        "documents_poisoned": await count(Document, Document.corpus_label == "poisoned"),
        "chunks": await count(DocumentChunk),
        "conversations": await count(Conversation),
        "messages": await count(Message),
        "security_test_runs": await count(SecurityTestRun),
    }
