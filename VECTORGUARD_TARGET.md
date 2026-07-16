# InjectionRange as a VectorGuard Target

InjectionRange's `/api/chat` endpoint is a drop-in generic HTTP target for
VectorGuard (OWASP LLM Top 10 attack suites + autonomous red-team agent). No
custom adapter code is required — the contract below is stable and documented.

## The contract

### Request

`POST /api/chat`

```json
{
  "message": "string — the user/attack turn (required)",
  "conversation_id": "string — optional; omit to start a new conversation"
}
```

VectorGuard's `body_template` drives it directly:

```yaml
body_template: '{"message": "{{last_user_message}}", "conversation_id": "{{conversation_id}}"}'
```

### Response

```json
{
  "answer": "string — the model answer (VectorGuard reads this)",
  "mode": "naive | hardened",
  "conversation_id": "string — thread id for multi-turn suites",
  "retrieved_chunk_ids": ["chunk-uuid", "..."],
  "citations": [
    {"chunk_id": "...", "document_id": "...", "filename": "...", "section_path": "...", "score": 0.83}
  ],
  "confidence": 0.71,
  "grounded": true,
  "token_usage": {"prompt_tokens": 812, "completion_tokens": 96, "total_tokens": 908}
}
```

- **`response_path: answer`** works out of the box.
- **Multi-turn**: send the `conversation_id` returned by the previous response on
  the next turn. Omit it to start fresh.
- **Auth**: `/api/chat` is intentionally usable **unauthenticated** so VectorGuard
  needs no token management. (Admin-only endpoints like the mode toggle are gated.)

## Quick start

```bash
# 1. Bring up the target (naive baseline first for a loud before-picture)
cp .env.example .env
echo "RAG_SECURITY_MODE=naive" >> .env      # or use the admin toggle
docker compose up -d

# 2. Smoke-test the contract by hand
curl -s localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What search method does RAGGuard use?"}' | jq

# 3. Run a VectorGuard suite against it
python -m vectorguard.cli run \
  --target vectorguard_target.yaml \
  --suite suites/rag_injection.yaml \
  --report reports/rag_injection_naive.json

# 4. Flip to hardened and re-run for the after-picture
curl -s -X POST localhost:8000/api/admin/security-mode \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"mode":"hardened"}'

python -m vectorguard.cli run \
  --target vectorguard_target.yaml \
  --suite suites/rag_injection.yaml \
  --report reports/rag_injection_hardened.json \
  --fail-on-findings
```

## Canaries / protected values

The `protected:` block in `vectorguard_target.yaml` mirrors the app's canary
config (`CANARY_*` in `.env`). These are **fake** values planted so VectorGuard's
`sensitive_data_disclosure` and `system_prompt_leak` detectors have real bait:

| value_type       | planted in                                   |
|------------------|----------------------------------------------|
| `secret_token`   | system prompt                                |
| `policy_name`    | system prompt                                |
| `internal_email` | system prompt                                |
| `system_marker`  | system prompt **and** a clean document       |

The document-side plant (`examples/rag_docs/clean/internal_runbook_canary.md`)
gives `system_prompt_leak`-style objectives a **document leakage path** to test,
not just a prompt-side one.

## Local RAG scan mode

The `rag_scan:` block points VectorGuard at `POST /api/search`, which returns
per-chunk metadata (`chunk_id`, `filename`, `corpus_label`, scores, `content`).
This lets VectorGuard report which **poisoned** chunks are retrievable for a given
probe and how they rank.

## Why naive vs hardened is a real before/after

`RAG_SECURITY_MODE` (env or the auth-gated admin toggle) changes real behavior,
not a label. Both modes share the **identical** retrieval pipeline; only prompt
construction, validation, and response handling differ. See
[`docs/CASE_STUDY.md`](docs/CASE_STUDY.md) for the measured pass-rate / risk-score
delta per suite.
