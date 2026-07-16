"""Groundedness validation (hardened mode).

Approximates faithfulness with lexical support: what fraction of the answer's
content words appear in the retrieved context. A real deployment could swap in an
NLI/LLM-judge here — the gate contract is unchanged.
"""
from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for", "on",
    "with", "as", "by", "that", "this", "it", "be", "you", "your", "i", "can",
    "not", "no", "have", "has", "do", "does", "if", "from", "at", "we", "our",
}


def groundedness_score(answer: str, context_blocks: list[str]) -> float:
    ans_words = [w for w in _TOKEN.findall(answer.lower()) if w not in _STOP]
    if not ans_words:
        return 1.0
    ctx = set(_TOKEN.findall(" ".join(context_blocks).lower()))
    supported = sum(1 for w in ans_words if w in ctx)
    return round(supported / len(ans_words), 4)


def is_grounded(answer: str, context_blocks: list[str], threshold: float = 0.5) -> bool:
    return groundedness_score(answer, context_blocks) >= threshold
