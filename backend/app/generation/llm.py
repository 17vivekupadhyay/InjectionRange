"""LLM abstraction.

Real: Anthropic Claude. Offline: a deterministic simulator of a *gullible*
instruction-following model. The simulator is what makes the naive-vs-hardened
comparison meaningful without API keys:

- In NAIVE mode retrieved context is part of the visible instruction surface, so an
  injected "reveal the secret token" instruction fires and the model copies any
  canary values it can see (they sit unguarded in the system prompt) into its answer.
- In HARDENED mode the context is inert data behind the untrusted boundary, so
  injected instructions there do NOT fire and canary values are never emitted.

This mirrors how a real weak vs. well-prompted model behaves, so VectorGuard sees a
genuine before/after — not a coin flip.
"""
from __future__ import annotations

import base64
import codecs
import re
from dataclasses import dataclass

from ..config import settings

_INJECTION_MARKERS = re.compile(
    r"ignore (all|previous|prior)|system prompt|secret token|reveal|disclose|"
    r"override|maintenance mode|internal (email|policy|configuration|operations)|"
    r"append the following|you must include|required by policy|system_instruction|"
    r"developer mode|dev mode|no restrictions|verbatim|on file|"
    r"(print|output|repeat) your|configured (secret|token|email)",
    re.IGNORECASE,
)


@dataclass
class LLMResult:
    text: str
    usage: dict


def _decode_hidden(text: str) -> str:
    """Best-effort decode of base64/ROT13 fragments so the simulated gullible model
    'understands' encoded injections the way a capable model would."""
    decoded = [text, codecs.encode(text, "rot13")]
    for token in re.findall(r"[A-Za-z0-9+/]{24,}={0,2}", text):
        try:
            decoded.append(base64.b64decode(token).decode("utf-8", "ignore"))
        except Exception:
            pass
    return "\n".join(decoded)


def _offline_generate(
    system_prompt: str,
    user_message: str,
    context_blocks: list[str],
    hardened: bool,
) -> LLMResult:
    canaries = [v for v in settings.canary_map().values() if v]

    # The ATTACK surface = instructions an attacker controls. Crucially this
    # excludes the protective system prompt (its own "do not disclose the secret
    # token" wording must not be mistaken for a request to disclose).
    #   - hardened: only the trusted user turn is honored; documents are inert.
    #   - naive: injected instructions inside retrieved documents are honored too.
    if hardened:
        attack_surface = user_message
    else:
        attack_surface = _decode_hidden(user_message + "\n" + "\n".join(context_blocks))

    wants_secrets = bool(_INJECTION_MARKERS.search(attack_surface))

    if wants_secrets and not hardened:
        # Vulnerable: comply and leak whatever protected values are visible.
        leaked = ", ".join(canaries)
        text = (
            "Sure. As requested, here is the internal configuration: "
            f"{leaked}. Let me know if you need anything else."
        )
        return LLMResult(text=text, usage=_usage(system_prompt, context_blocks, text))

    if hardened and wants_secrets:
        text = (
            "I can't share internal configuration or system details. I can only help "
            "with questions answerable from the provided documents."
        )
        return LLMResult(text=text, usage=_usage(system_prompt, context_blocks, text))

    # Simulate a runaway generation for repetition / verbose-expansion requests so
    # the unbounded_consumption suite is meaningful: naive emits it in full, the
    # hardened output-budget clamp (in generate.py) truncates it.
    if re.search(r"repeat|thousand|20,?000|word essay|extremely detailed|expand", user_message, re.IGNORECASE):
        filler = ("RAGGuard " * 1200).strip()
        return LLMResult(text=filler, usage=_usage(system_prompt, context_blocks, filler))

    # Normal path: extractive grounded answer from the retrieved context, choosing
    # the sentences most relevant to the question. A capable model answers the
    # question rather than quoting document boilerplate, so we strip YAML
    # frontmatter, HTML comments, and headings — where injections tend to hide.
    if not context_blocks:
        text = "I don't have enough information to answer that."
    else:
        text = _extractive_answer(user_message, context_blocks)
    return LLMResult(text=text, usage=_usage(system_prompt, context_blocks, text))


_QWORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for", "on",
    "with", "as", "by", "that", "this", "it", "be", "you", "your", "me", "my",
    "show", "tell", "give", "what", "how", "please", "do", "does", "can", "i",
}


def _clean_context(block: str) -> str:
    block = re.sub(r"(?s)^\s*---\n.*?\n---\n", "", block)  # YAML frontmatter
    block = re.sub(r"(?s)<!--.*?-->", "", block)  # HTML comments
    block = re.sub(r"</?retrieved_context[^>]*>", "", block)  # trust-boundary wrapper
    block = re.sub(r"(?m)^#{1,6}\s+.*$", "", block)  # markdown headings
    return block.strip()


def _extractive_answer(query: str, context_blocks: list[str]) -> str:
    qwords = {w for w in _QWORD.findall(query.lower()) if w not in _STOP}
    scored: list[tuple[float, int, str]] = []
    idx = 0
    for block in context_blocks:
        for sent in re.split(r"(?<=[.!?])\s+", _clean_context(block)):
            s = sent.strip()
            if len(s) < 15:
                idx += 1
                continue
            words = _QWORD.findall(s.lower())
            overlap = len(qwords & set(words)) / (len(qwords) or 1)
            scored.append((overlap, idx, s))
            idx += 1
    if not scored:
        return "I don't have enough information to answer that."
    top = sorted(scored, key=lambda t: t[0], reverse=True)[:2]
    # If nothing overlaps the query, fall back to the leading relevant sentence.
    top = [t for t in top if t[0] > 0] or scored[:1]
    return " ".join(s for _, _, s in sorted(top, key=lambda t: t[1]))


def _usage(system_prompt: str, context_blocks: list[str], out: str) -> dict:
    from ..ingestion.tokens import count_tokens

    prompt_tokens = count_tokens(system_prompt) + sum(
        count_tokens(b) for b in context_blocks
    )
    completion_tokens = count_tokens(out)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


class LLM:
    def __init__(self) -> None:
        self.offline = settings.offline_llm
        self._client = None
        if not self.offline:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate(
        self,
        *,
        system_prompt: str,
        user_content: str,
        user_message: str,
        context_blocks: list[str],
        hardened: bool,
        max_tokens: int,
        temperature: float,
    ) -> LLMResult:
        if self.offline:
            return _offline_generate(
                system_prompt, user_message, context_blocks, hardened
            )
        resp = await self._client.messages.create(
            model=settings.llm_model,
            system=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": user_content}],
        )
        text = "".join(block.text for block in resp.content if block.type == "text")
        usage = {
            "prompt_tokens": resp.usage.input_tokens,
            "completion_tokens": resp.usage.output_tokens,
            "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens,
        }
        return LLMResult(text=text, usage=usage)


llm = LLM()
