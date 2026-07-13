"""Canary registry.

Registers the prompt-side canaries (from config) into the DB at startup and
exposes helpers for planting a document-side canary and for detecting leakage in
model output. VectorGuard's detectors look for these exact strings; hardened mode
must never emit them.
"""
from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Canary


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def register_prompt_canaries(db: AsyncSession) -> None:
    for value_type, value in settings.canary_map().items():
        exists = await db.scalar(
            select(Canary).where(
                Canary.value_type == value_type,
                Canary.planted_location == "system_prompt",
            )
        )
        if exists:
            continue
        db.add(
            Canary(
                value_type=value_type,
                value_hash=_hash(value),
                planted_location="system_prompt",
                active=True,
            )
        )
    await db.commit()


async def register_document_canary(db: AsyncSession, doc_id: str, value: str) -> None:
    db.add(
        Canary(
            value_type="system_marker",
            value_hash=_hash(value),
            planted_location=f"document:{doc_id}",
            active=True,
        )
    )
    await db.commit()


def detect_leak(text: str) -> list[str]:
    """Return the value_types whose canary appears verbatim in `text`."""
    leaked = []
    for value_type, value in settings.canary_map().items():
        if value and value in text:
            leaked.append(value_type)
    return leaked


async def canary_status(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(select(Canary))).scalars().all()
    return [
        {
            "value_type": c.value_type,
            "planted_location": c.planted_location,
            "active": c.active,
        }
        for c in rows
    ]
