"""Reranking.

Real deployments would call a cross-encoder (e.g. bge-reranker-v2) or a hosted
reranker. Offline, we approximate one with a blend of lexical overlap and the dense
similarity already computed during retrieval — so a strong semantic match isn't
thrown away by crude keyword counting. The interface is identical either way.
"""
from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for", "on",
    "with", "as", "by", "that", "this", "it", "be", "you", "your", "what", "which",
    "how", "does", "do", "use", "used", "i", "we", "me", "my", "can", "will",
}

# Weighting between lexical overlap and the retrieval dense score.
_LEX_W = 0.4
_DENSE_W = 0.6


def _overlap_score(query: str, text: str) -> float:
    q = {w for w in _TOKEN.findall(query.lower()) if w not in _STOP}
    if not q:
        return 0.0
    d = _TOKEN.findall(text.lower())
    if not d:
        return 0.0
    dset = set(d)
    overlap = len(q & dset) / len(q)
    density = sum(1 for t in d if t in q) / len(d)
    return 0.85 * overlap + 0.15 * density


def rerank(query: str, candidates: list, top_n: int) -> list:
    """candidates: objects with `.content` and `.dense_score`; sets `.rerank_score`
    and returns the top_n sorted descending."""
    for c in candidates:
        lexical = _overlap_score(query, c.content)
        dense = max(0.0, getattr(c, "dense_score", 0.0))
        c.rerank_score = round(_LEX_W * lexical + _DENSE_W * dense, 6)
    ranked = sorted(candidates, key=lambda c: c.rerank_score, reverse=True)
    return ranked[:top_n]
