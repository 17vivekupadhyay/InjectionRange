from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..retrieval.hybrid import retrieve
from ..schemas import RetrievedChunk, SearchRequest, SearchResponse
from ..security.mode import current_mode

router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search(body: SearchRequest, db: AsyncSession = Depends(get_db)):
    """Retrieval debug endpoint — powers the frontend debug view and VectorGuard's
    local RAG scan inspection (chunk metadata + scores + corpus label)."""
    candidates = await retrieve(
        db,
        body.query,
        top_k=body.top_k,
        doc_type=body.doc_type,
        access_tag=body.access_tag,
    )
    return SearchResponse(
        query=body.query,
        mode=current_mode(),
        results=[
            RetrievedChunk(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                filename=c.filename,
                section_path=c.section_path,
                content=c.content,
                corpus_label=c.corpus_label,
                dense_score=round(c.dense_score, 4),
                bm25_score=round(c.bm25_score, 4),
                rrf_score=round(c.rrf_score, 6),
                rerank_score=round(c.rerank_score, 4),
            )
            for c in candidates
        ],
    )
