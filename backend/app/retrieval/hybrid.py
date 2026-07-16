"""Hybrid retrieval: dense (pgvector) + BM25 (tsvector) fused with RRF, then rerank.

Both naive and hardened modes call this identical pipeline — the security
difference lives entirely downstream in prompt construction and validation, so any
delta VectorGuard reports is attributable to hardening, not retrieval quality.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Document, DocumentChunk
from .embeddings import embedder
from .rerank import rerank

RRF_K = 60


@dataclass
class Candidate:
    chunk_id: str
    document_id: str
    filename: str
    section_path: str
    content: str
    corpus_label: str
    dense_score: float = 0.0
    bm25_score: float = 0.0
    rrf_score: float = 0.0
    rerank_score: float = 0.0
    meta: dict = field(default_factory=dict)


def _base_query(doc_type: str | None, access_tag: str | None):
    """Metadata pre-filter applied BEFORE vector/BM25 scoring."""
    stmt = select(DocumentChunk, Document).join(
        Document, DocumentChunk.document_id == Document.id
    )
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)
    if access_tag:
        stmt = stmt.where(Document.access_tags.contains([access_tag]))
    return stmt


async def _dense(
    db: AsyncSession, query_vec: list[float], top_k: int, doc_type, access_tag
) -> list[tuple[DocumentChunk, Document, float]]:
    distance = DocumentChunk.embedding.cosine_distance(query_vec)
    stmt = (
        _base_query(doc_type, access_tag)
        .where(DocumentChunk.embedding.isnot(None))
        .add_columns(distance.label("distance"))
        .order_by(distance)
        .limit(top_k)
    )
    rows = await db.execute(stmt)
    out = []
    for chunk, doc, dist in rows:
        out.append((chunk, doc, 1.0 - float(dist)))  # cosine similarity
    return out


async def _bm25(
    db: AsyncSession, query: str, top_k: int, doc_type, access_tag
) -> list[tuple[DocumentChunk, Document, float]]:
    tsquery = func.plainto_tsquery("english", query)
    rank = func.ts_rank(DocumentChunk.tsv, tsquery)
    stmt = (
        _base_query(doc_type, access_tag)
        .where(DocumentChunk.tsv.op("@@")(tsquery))
        .add_columns(rank.label("rank"))
        .order_by(rank.desc())
        .limit(top_k)
    )
    rows = await db.execute(stmt)
    return [(chunk, doc, float(r)) for chunk, doc, r in rows]


def _fuse(dense, bm25) -> list[Candidate]:
    """Reciprocal rank fusion over the two ranked lists."""
    cand: dict[str, Candidate] = {}

    def ensure(chunk: DocumentChunk, doc: Document) -> Candidate:
        if chunk.id not in cand:
            cand[chunk.id] = Candidate(
                chunk_id=chunk.id,
                document_id=doc.id,
                filename=doc.filename,
                section_path=chunk.section_path,
                content=chunk.content,
                corpus_label=chunk.corpus_label,
            )
        return cand[chunk.id]

    for rank_idx, (chunk, doc, score) in enumerate(dense):
        c = ensure(chunk, doc)
        c.dense_score = score
        c.rrf_score += 1.0 / (RRF_K + rank_idx + 1)
    for rank_idx, (chunk, doc, score) in enumerate(bm25):
        c = ensure(chunk, doc)
        c.bm25_score = score
        c.rrf_score += 1.0 / (RRF_K + rank_idx + 1)

    return sorted(cand.values(), key=lambda c: c.rrf_score, reverse=True)


async def retrieve(
    db: AsyncSession,
    query: str,
    *,
    top_k: int | None = None,
    top_n: int | None = None,
    doc_type: str | None = None,
    access_tag: str | None = None,
) -> list[Candidate]:
    top_k = top_k or settings.retrieve_top_k
    top_n = top_n or settings.rerank_top_n

    query_vec = await embedder.embed_one(query)
    dense = await _dense(db, query_vec, top_k, doc_type, access_tag)
    bm25 = await _bm25(db, query, top_k, doc_type, access_tag)

    fused = _fuse(dense, bm25)
    if not fused:
        return []
    return rerank(query, fused, top_n)


def top_confidence(candidates: list[Candidate]) -> float:
    """Confidence = best rerank score. Used by the hardened confidence gate."""
    return max((c.rerank_score for c in candidates), default=0.0)
