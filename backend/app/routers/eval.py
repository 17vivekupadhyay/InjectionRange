from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..eval.retrieval_eval import run_retrieval_eval

router = APIRouter(prefix="/api/eval", tags=["eval"])


@router.post("/run")
async def run_eval(k: int | None = None, db: AsyncSession = Depends(get_db)):
    """Retrieval-quality eval harness: recall@k + MRR over the golden set."""
    return await run_retrieval_eval(db, k=k)
