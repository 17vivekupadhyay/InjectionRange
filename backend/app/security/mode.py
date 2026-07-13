"""Runtime-mutable security mode.

Sourced from config at startup but toggleable via the auth-gated admin endpoint
so a demo can flip naive<->hardened without a redeploy. Everything downstream
reads `current_mode()` rather than settings directly.
"""
from __future__ import annotations

from ..config import SecurityMode, settings

_mode: SecurityMode = settings.rag_security_mode


def current_mode() -> SecurityMode:
    return _mode


def set_mode(mode: SecurityMode) -> None:
    global _mode
    if mode not in ("naive", "hardened"):
        raise ValueError(f"invalid mode: {mode}")
    _mode = mode


def is_hardened() -> bool:
    return _mode == "hardened"
