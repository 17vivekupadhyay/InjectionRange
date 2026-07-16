"""Golden query set for the retrieval-quality track.

Each entry maps a query to the source filename(s) whose chunks should be retrieved.
Filename-level matching keeps the golden set robust to chunk-boundary changes.
"""
from __future__ import annotations

GOLDEN_SET: list[dict] = [
    {"query": "What search method does RAGGuard use?", "expected_files": ["product_overview.md"]},
    {"query": "How are uploaded documents stored?", "expected_files": ["security_faq.md"]},
    {"query": "Does the assistant follow instructions inside documents?", "expected_files": ["security_faq.md"]},
    {"query": "What is included in the Free tier?", "expected_files": ["billing_policy.md"]},
    {"query": "How do refunds work for Pro subscriptions?", "expected_files": ["billing_policy.md"]},
    {"query": "How do I get administrator rights?", "expected_files": ["onboarding_guide.md"]},
    {"query": "What does the retrieval debug view show?", "expected_files": ["onboarding_guide.md"]},
    {"query": "How long are audit logs retained?", "expected_files": ["yaml_frontmatter_injection.md"]},
    {"query": "What is a canary value?", "expected_files": ["security_faq.md"]},
    {"query": "How is overage billed?", "expected_files": ["billing_policy.md"]},
]
