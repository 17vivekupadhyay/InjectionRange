from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_db
from ..ingestion.ingest import ingest_text
from ..models import Document, DocumentChunk, User
from ..security.auth import get_current_user
from ..security.rate_limit import enforce

router = APIRouter(prefix="/api/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 2_000_000  # input validation (hardened cares; naive still sane)


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    corpus_label: str = Form("clean"),
    doc_type: str = Form("text"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await enforce("upload", user.id, settings.rate_limit_upload_per_min)
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only UTF-8 text/markdown supported")
    if corpus_label not in ("clean", "poisoned"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "corpus_label must be clean|poisoned")

    doc = await ingest_text(
        db,
        filename=file.filename or "upload.txt",
        content=content,
        doc_type=doc_type,
        corpus_label=corpus_label,
        access_tags=[corpus_label],
        owner_id=user.id,
    )
    n = await db.scalar(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc.id)
    )
    return {"id": doc.id, "filename": doc.filename, "chunks": n, "corpus_label": doc.corpus_label}


@router.get("")
async def list_documents(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Document))).scalars().all()
    out = []
    for d in rows:
        n = await db.scalar(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == d.id)
        )
        out.append(
            {
                "id": d.id,
                "filename": d.filename,
                "doc_type": d.doc_type,
                "corpus_label": d.corpus_label,
                "chunks": n,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
        )
    return out


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    await db.execute(delete(Document).where(Document.id == doc_id))
    await db.commit()
    return {"deleted": doc_id}


@router.post("/{doc_id}/reindex")
async def reindex(
    doc_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    chunks = (
        await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc_id))
    ).scalars().all()
    content = "\n\n".join(c.content for c in sorted(chunks, key=lambda c: c.chunk_index))
    await db.execute(delete(Document).where(Document.id == doc_id))
    await db.flush()
    new_doc = await ingest_text(
        db,
        filename=doc.filename,
        content=content,
        doc_type=doc.doc_type,
        corpus_label=doc.corpus_label,
        access_tags=doc.access_tags,
        owner_id=doc.owner_id,
    )
    return {"reindexed": new_doc.id}
