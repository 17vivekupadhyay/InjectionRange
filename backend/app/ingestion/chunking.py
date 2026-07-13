"""Structure-aware chunking with recursive fallback + contextual enrichment.

Strategy:
  1. Split on markdown headers into sections, tracking the section path
     (e.g. "Security > Hardened Mode"). This keeps a chunk's provenance meaningful.
  2. Within each section, if the section exceeds the token target, recursively
     split on progressively finer separators (paragraph -> sentence -> word).
  3. Each emitted chunk carries a contextual prefix (doc title + section path),
     prepended before embedding per the contextual-retrieval technique.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .tokens import count_tokens

_HEADER = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
_RECURSIVE_SEPARATORS = ["\n\n", "\n", ". ", " "]


@dataclass
class Chunk:
    content: str
    section_path: str
    chunk_index: int
    char_offset: int
    contextual_prefix: str = ""
    token_count: int = 0
    embed_text: str = field(default="", repr=False)


def _recursive_split(text: str, target: int, seps: list[str]) -> list[str]:
    if count_tokens(text) <= target or not seps:
        return [text] if text.strip() else []
    sep, rest = seps[0], seps[1:]
    parts = text.split(sep)
    out: list[str] = []
    buf = ""
    for part in parts:
        candidate = (buf + sep + part) if buf else part
        if count_tokens(candidate) <= target:
            buf = candidate
        else:
            if buf:
                out.append(buf)
            if count_tokens(part) > target:
                out.extend(_recursive_split(part, target, rest))
                buf = ""
            else:
                buf = part
    if buf.strip():
        out.append(buf)
    return out


def _sections(text: str) -> list[tuple[str, str, int]]:
    """Return (section_path, body, char_offset) tuples using markdown headers."""
    matches = list(_HEADER.finditer(text))
    if not matches:
        return [("", text, 0)]

    sections: list[tuple[str, str, int]] = []
    stack: list[tuple[int, str]] = []  # (level, title)

    # Preamble before the first header
    if matches[0].start() > 0:
        pre = text[: matches[0].start()]
        if pre.strip():
            sections.append(("", pre, 0))

    for i, m in enumerate(matches):
        level = len(m.group(1))
        title = m.group(2).strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        path = " > ".join(t for _, t in stack)
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end]
        sections.append((path, body, body_start))
    return sections


def chunk_document(
    text: str,
    title: str,
    target_tokens: int = 500,
    strategy: str = "recursive",
) -> list[Chunk]:
    chunks: list[Chunk] = []
    idx = 0
    section_iter = _sections(text) if strategy != "flat" else [("", text, 0)]

    for section_path, body, offset in section_iter:
        for piece in _recursive_split(body.strip(), target_tokens, _RECURSIVE_SEPARATORS):
            piece = piece.strip()
            if not piece:
                continue
            prefix_parts = [p for p in (title, section_path) if p]
            prefix = " — ".join(prefix_parts)
            embed_text = f"{prefix}\n\n{piece}" if prefix else piece
            chunks.append(
                Chunk(
                    content=piece,
                    section_path=section_path,
                    chunk_index=idx,
                    char_offset=offset,
                    contextual_prefix=prefix,
                    token_count=count_tokens(piece),
                    embed_text=embed_text,
                )
            )
            idx += 1
    return chunks
