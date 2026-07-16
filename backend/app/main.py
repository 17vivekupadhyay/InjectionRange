"""InjectionRange FastAPI app.

A production-grade RAG pipeline that doubles as a purpose-built VectorGuard
red-team target. Startup: create schema, register prompt-side canaries, seed an
admin, and auto-ingest the clean/poisoned corpus if the store is empty.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from .db import SessionLocal, init_db
from .ingestion.ingest import ingest_corpus_dir
from .models import Document
from .routers import admin, auth, chat, conversations, documents, eval, search, stats
from .security.auth import bootstrap_default_user
from .security.canary import register_prompt_canaries
from .security.mode import current_mode

CORPUS_CANDIDATES = [
    Path("/examples/rag_docs"),
    Path(__file__).resolve().parents[2] / "examples" / "rag_docs",
]


async def _auto_ingest_corpus() -> None:
    async with SessionLocal() as db:
        count = await db.scalar(select(func.count()).select_from(Document))
        if count:
            return
        for root in CORPUS_CANDIDATES:
            if root.exists():
                await ingest_corpus_dir(db, root)
                break


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with SessionLocal() as db:
        await register_prompt_canaries(db)
        await bootstrap_default_user(db)
    await _auto_ingest_corpus()
    yield


app = FastAPI(title="InjectionRange", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, documents, chat, conversations, search, eval, stats, admin):
    app.include_router(r.router)


@app.get("/health")
async def health():
    return {"status": "ok", "mode": current_mode()}
