from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import User
from ..schemas import SecurityModeResponse, SecurityModeUpdate
from ..security.auth import require_admin
from ..security.canary import canary_status
from ..security.mode import current_mode, is_hardened, set_mode

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/security-mode", response_model=SecurityModeResponse)
async def get_security_mode(db: AsyncSession = Depends(get_db)):
    return SecurityModeResponse(
        mode=current_mode(),
        canaries=await canary_status(db),
        rate_limiting_active=is_hardened(),
    )


@router.post("/security-mode", response_model=SecurityModeResponse)
async def set_security_mode(
    body: SecurityModeUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Auth-gated toggle for demo/testing. Flips real behavior, not just a label."""
    if body.mode not in ("naive", "hardened"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "mode must be naive|hardened")
    set_mode(body.mode)
    return SecurityModeResponse(
        mode=current_mode(),
        canaries=await canary_status(db),
        rate_limiting_active=is_hardened(),
    )
