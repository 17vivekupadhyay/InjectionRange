"""Ingestion service: text -> chunks -> embeddings -> stored chunks with BM25 tsv."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Document, DocumentChunk
from ..retrieval.embeddings import embedder
from ..security.canary import register_document_canary
from .chunking import chunk_document


async def ingest_text(
    db: AsyncSession,
    *,
    filename: str,
    content: str,
    doc_type: str = "text",
    corpus_label: str = "clean",
    access_tags: list[str] | None = None,
    owner_id: str | None = None,
    plant_canary: bool = False,
) -> Document:
    doc = Document(
        filename=filename,
        doc_type=doc_type,
        corpus_label=corpus_label,
        access_tags=access_tags or [],
        owner_id=owner_id,
    )
    db.add(doc)
    await db.flush()  # get doc.id

    title = Path(filename).stem.replace("_", " ").replace("-", " ").title()
    chunks = chunk_document(
        content,
        title=title,
        target_tokens=settings.chunk_size_default,
        strategy=settings.chunk_strategy,
    )
    embeddings = await embedder.embed([c.embed_text for c in chunks]) if chunks else []

    for c, emb in zip(chunks, embeddings):
        db.add(
            DocumentChunk(
                document_id=doc.id,
                section_path=c.section_path,
                chunk_index=c.chunk_index,
                char_offset=c.char_offset,
                contextual_prefix=c.contextual_prefix,
                content=c.content,
                token_count=c.token_count,
                corpus_label=corpus_label,
                embedding=emb,
            )
        )
    await db.flush()

    # Populate the BM25 tsvector column from Postgres full-text search.
    await db.execute(
        sql_text(
            "UPDATE document_chunks "
            "SET tsv = to_tsvector('english', coalesce(contextual_prefix,'') || ' ' || content) "
            "WHERE document_id = :doc_id"
        ),
        {"doc_id": doc.id},
    )

    if plant_canary:
        # a document-side leakage path for system_prompt_leak-style objectives
        await register_document_canary(db, doc.id, settings.canary_system_marker)

    await db.commit()
    await db.refresh(doc)
    return doc


async def ingest_corpus_dir(db: AsyncSession, root: Path) -> dict:
    """Load examples/rag_docs/{clean,poisoned}/*.md into the store. Idempotent-ish:
    skips files already ingested by filename."""
    from sqlalchemy import select

    summary = {"clean": 0, "poisoned": 0, "skipped": 0}
    for label in ("clean", "poisoned"):
        sub = root / label
        if not sub.exists():
            continue
        for path in sorted(sub.glob("*.md")):
            existing = await db.scalar(
                select(Document).where(Document.filename == path.name)
            )
            if existing:
                summary["skipped"] += 1
                continue
            content = path.read_text(encoding="utf-8")
            # Plant a document-side canary in a subset of clean docs.
            plant = label == "clean" and path.stem.endswith("_canary")
            await ingest_text(
                db,
                filename=path.name,
                content=content,
                corpus_label=label,
                access_tags=[label],
                plant_canary=plant,
            )
            summary[label] += 1
    return summary
