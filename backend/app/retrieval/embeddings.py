"""Embedding provider abstraction.

Real: OpenAI embeddings. Offline: a deterministic hashed bag-of-words vector so
the entire pipeline (ingestion, dense retrieval, eval, VectorGuard runs) works in
CI with no API key. The offline embedder is intentionally simple but stable —
same text always maps to the same vector, and lexically similar texts land near
each other, which is enough for the security testbed to exercise real code paths.
"""
from __future__ import annotations

import hashlib
import math
import re

from ..config import settings

_TOKEN = re.compile(r"[a-z0-9]+")


def _offline_embed(text: str) -> list[float]:
    dim = settings.embedding_dim
    vec = [0.0] * dim
    for tok in _TOKEN.findall(text.lower()):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
        # a second hashed slot adds a little signal / reduces collisions
        vec[(h // dim) % dim] += 0.5
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class Embedder:
    def __init__(self) -> None:
        self.offline = settings.offline_embeddings
        self._client = None
        if not self.offline:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if self.offline:
            return [_offline_embed(t) for t in texts]
        resp = await self._client.embeddings.create(
            model=settings.embedding_model, input=texts
        )
        return [d.embedding for d in resp.data]

    async def embed_one(self, text: str) -> list[float]:
        return (await self.embed([text]))[0]


embedder = Embedder()
