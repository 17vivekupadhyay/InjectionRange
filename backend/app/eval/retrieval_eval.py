"""Retrieval-quality metrics: recall@k and MRR against the golden set."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..retrieval.hybrid import retrieve
from .golden_set import GOLDEN_SET


async def run_retrieval_eval(db: AsyncSession, k: int | None = None) -> dict:
    k = k or settings.rerank_top_n
    per_query = []
    recall_hits = 0
    reciprocal_ranks = []

    for item in GOLDEN_SET:
        candidates = await retrieve(db, item["query"], top_n=k)
        retrieved_files = [c.filename for c in candidates]
        expected = set(item["expected_files"])

        hit = any(f in expected for f in retrieved_files)
        recall_hits += 1 if hit else 0

        rr = 0.0
        for rank, f in enumerate(retrieved_files, start=1):
            if f in expected:
                rr = 1.0 / rank
                break
        reciprocal_ranks.append(rr)

        per_query.append(
            {
                "query": item["query"],
                "expected": sorted(expected),
                "retrieved": retrieved_files,
                "hit": hit,
                "reciprocal_rank": round(rr, 4),
            }
        )

    n = len(GOLDEN_SET)
    return {
        "k": k,
        "num_queries": n,
        "recall_at_k": round(recall_hits / n, 4) if n else 0.0,
        "mrr": round(sum(reciprocal_ranks) / n, 4) if n else 0.0,
        "per_query": per_query,
    }
