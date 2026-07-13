"""Pydantic request/response models."""
from __future__ import annotations

from pydantic import BaseModel, Field


# ---- Auth ----
# Plain str (not EmailStr): the seeded admin / canary email uses a reserved
# internal TLD (admin@ragguard.local) that EmailStr's validator rejects.
class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- Chat (VectorGuard-compatible contract) ----
class ChatRequest(BaseModel):
    # `message` is the field VectorGuard's body_template drives:
    #   {"message": "{{last_user_message}}"}
    message: str
    conversation_id: str | None = None


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    section_path: str
    score: float


class ChatResponse(BaseModel):
    # `answer` is the stable, documented response_path VectorGuard reads.
    answer: str
    mode: str
    conversation_id: str
    retrieved_chunk_ids: list[str] = []
    citations: list[Citation] = []
    confidence: float = 0.0
    grounded: bool = True
    token_usage: dict = {}


# ---- Search ----
class SearchRequest(BaseModel):
    query: str
    top_k: int | None = None
    doc_type: str | None = None
    access_tag: str | None = None


class RetrievedChunk(BaseModel):
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


class SearchResponse(BaseModel):
    query: str
    mode: str
    results: list[RetrievedChunk]


# ---- Admin / security mode ----
class SecurityModeResponse(BaseModel):
    mode: str
    canaries: list[dict]
    rate_limiting_active: bool


class SecurityModeUpdate(BaseModel):
    mode: str  # naive | hardened
