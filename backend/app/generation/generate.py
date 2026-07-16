"""Generation orchestration — the security-relevant control flow.

naive:    retrieve -> concat -> LLM (no boundary, no validation, no limits, always answer)
hardened: retrieve -> confidence gate -> boundaried prompt -> LLM (budgeted)
                    -> canary-leak scan -> groundedness gate
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..retrieval.hybrid import Candidate, retrieve, top_confidence
from ..security import canary
from ..security.mode import current_mode
from .groundedness import groundedness_score
from .llm import llm
from .prompts import build_hardened_prompt, build_naive_prompt

FALLBACK = "I don't have enough information to answer that."
REFUSAL = (
    "I can't share internal configuration or system details, and I won't follow "
    "instructions embedded in documents. I can only answer from the provided content."
)
# Canned safe responses are exempt from the groundedness gate — a correct refusal
# is not a hallucination and must not be downgraded to the generic fallback.
_SAFE_PREFIXES = ("I can't share", "I don't have enough information")


def _is_safe_response(answer: str) -> bool:
    return answer.strip().startswith(_SAFE_PREFIXES)
# Naive mode intentionally allows a large output budget to expose the
# unbounded_consumption objective; hardened clamps to settings.max_tokens.
NAIVE_MAX_TOKENS = 4096
HISTORY_TURNS = 6


@dataclass
class GenerationResult:
    answer: str
    mode: str
    confidence: float
    grounded: bool
    groundedness: float
    candidates: list[Candidate]
    token_usage: dict
    blocked_reason: str | None = None
    canary_leak: list[str] = field(default_factory=list)


def _fold_history(history: list[dict], query: str) -> str:
    """Explicit multi-turn context budgeting: keep only the last few turns."""
    if not history:
        return query
    recent = history[-HISTORY_TURNS:]
    convo = "\n".join(f"{m['role']}: {m['content']}" for m in recent)
    return f"Conversation so far:\n{convo}\n\nFollow-up: {query}"


async def synthesize(
    *,
    query: str,
    context_blocks: list[str],
    confidence: float,
    mode: str | None = None,
    candidates: list[Candidate] | None = None,
) -> GenerationResult:
    """Prompt construction + LLM + validation. Shared by the live server path and
    the offline case-study harness, so both exercise identical security logic."""
    mode = mode or current_mode()
    hardened = mode == "hardened"
    candidates = candidates or []
    user_message = query

    # Hardened confidence gate — graceful fallback instead of forcing an answer.
    if hardened and confidence < settings.confidence_threshold:
        return GenerationResult(
            answer=FALLBACK,
            mode=mode,
            confidence=confidence,
            grounded=True,
            groundedness=1.0,
            candidates=candidates,
            token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            blocked_reason="low_confidence",
        )

    if hardened:
        system_prompt, user_content = build_hardened_prompt(user_message, context_blocks)
        max_tokens = settings.max_tokens
    else:
        system_prompt, user_content = build_naive_prompt(user_message, context_blocks)
        max_tokens = NAIVE_MAX_TOKENS

    result = await llm.generate(
        system_prompt=system_prompt,
        user_content=user_content,
        user_message=user_message,
        context_blocks=context_blocks,
        hardened=hardened,
        max_tokens=max_tokens,
        temperature=settings.temperature,
    )
    answer = result.text
    ground = groundedness_score(answer, context_blocks) if context_blocks else 1.0
    blocked_reason = None
    leak = canary.detect_leak(answer)

    if hardened:
        # 1. Canary leak scan — hardened must never emit a protected value.
        if leak:
            answer = REFUSAL
            blocked_reason = "canary_leak_blocked"
            leak = []  # neutralized
        # 2. A correct refusal is safe — don't run it through the groundedness gate.
        elif _is_safe_response(answer):
            blocked_reason = "refused"
        # 3. Groundedness gate for substantive answers.
        elif ground < 0.5:
            answer = FALLBACK
            blocked_reason = "ungrounded"
        # 4. Output length budget (defends unbounded_consumption).
        elif len(answer) > max_tokens * 4:  # ~4 chars/token guardrail
            answer = answer[: max_tokens * 4].rstrip() + " …"
            blocked_reason = "truncated_budget"

    grounded = ground >= 0.5 or not context_blocks
    return GenerationResult(
        answer=answer,
        mode=mode,
        confidence=confidence,
        grounded=grounded,
        groundedness=ground,
        candidates=candidates,
        token_usage=result.usage,
        blocked_reason=blocked_reason,
        canary_leak=leak,
    )


async def generate_answer(
    db: AsyncSession,
    *,
    query: str,
    history: list[dict] | None = None,
    doc_type: str | None = None,
    access_tag: str | None = None,
) -> GenerationResult:
    """Live server path: hybrid retrieval -> synthesize."""
    candidates = await retrieve(db, query, doc_type=doc_type, access_tag=access_tag)
    confidence = top_confidence(candidates)
    context_blocks = [c.content for c in candidates]
    user_message = _fold_history(history or [], query)
    return await synthesize(
        query=user_message,
        context_blocks=context_blocks,
        confidence=confidence,
        candidates=candidates,
    )
