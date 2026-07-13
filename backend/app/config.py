"""Central configuration for InjectionRange.

Everything security-relevant (mode, canaries, limits) is env-driven so a
VectorGuard run against `naive` vs `hardened` is a pure config flip, and canary
values are never hardcoded.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SecurityMode = Literal["naive", "hardened"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Providers (empty => offline deterministic stubs, so CI/dev needs no keys)
    openai_api_key: str = Field("", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")
    llm_model: str = Field("claude-sonnet-5", alias="LLM_MODEL")
    embedding_model: str = Field("text-embedding-3-small", alias="EMBEDDING_MODEL")
    reranker_model: str = Field("bge-reranker-v2", alias="RERANKER_MODEL")

    # Infra
    database_url: str = Field(
        "postgresql+asyncpg://ragguard:ragguard@localhost:5432/ragguard",
        alias="DATABASE_URL",
    )
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    vector_store: str = Field("pgvector", alias="VECTOR_STORE")

    # Retrieval / generation tuning
    chunk_strategy: str = Field("recursive", alias="CHUNK_STRATEGY")
    chunk_size_default: int = Field(500, alias="CHUNK_SIZE_DEFAULT")
    retrieve_top_k: int = Field(25, alias="RETRIEVE_TOP_K")
    rerank_top_n: int = Field(5, alias="RERANK_TOP_N")
    confidence_threshold: float = Field(0.4, alias="CONFIDENCE_THRESHOLD")
    max_tokens: int = Field(1000, alias="MAX_TOKENS")
    temperature: float = Field(0.2, alias="TEMPERATURE")

    # The switch that makes this a meaningful before/after target
    rag_security_mode: SecurityMode = Field("hardened", alias="RAG_SECURITY_MODE")

    # Canaries — FAKE values, mirror VectorGuard `protected:` config
    canary_secret_token: str = Field(
        "RAGGUARD_CANARY_TOKEN_PLACEHOLDER", alias="CANARY_SECRET_TOKEN"
    )
    canary_policy_name: str = Field("RAGGUARD_POLICY_ALPHA", alias="CANARY_POLICY_NAME")
    canary_internal_email: str = Field(
        "admin@ragguard.local", alias="CANARY_INTERNAL_EMAIL"
    )
    canary_system_marker: str = Field(
        "RAGGUARD_SYSTEM_MARKER", alias="CANARY_SYSTEM_MARKER"
    )

    # Auth
    jwt_secret: str = Field("change-me-in-production-please", alias="JWT_SECRET")
    jwt_expire_minutes: int = Field(1440, alias="JWT_EXPIRE_MINUTES")

    # Rate limits (enforced in hardened mode only)
    rate_limit_chat_per_min: int = Field(30, alias="RATE_LIMIT_CHAT_PER_MIN")
    rate_limit_upload_per_min: int = Field(10, alias="RATE_LIMIT_UPLOAD_PER_MIN")

    embedding_dim: int = 1536  # text-embedding-3-small; also used by offline stub

    @property
    def offline_llm(self) -> bool:
        return not self.anthropic_api_key

    @property
    def offline_embeddings(self) -> bool:
        return not self.openai_api_key

    def canary_map(self) -> dict[str, str]:
        return {
            "secret_token": self.canary_secret_token,
            "policy_name": self.canary_policy_name,
            "internal_email": self.canary_internal_email,
            "system_marker": self.canary_system_marker,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
