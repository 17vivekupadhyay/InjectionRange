"""Token counting. tiktoken when available, whitespace approximation otherwise."""
from __future__ import annotations

try:
    import tiktoken

    _enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))

except Exception:  # pragma: no cover - fallback path

    def count_tokens(text: str) -> int:
        return max(1, round(len(text.split()) * 1.3))
