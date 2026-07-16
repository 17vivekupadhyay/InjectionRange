#!/usr/bin/env python3
"""Local VectorGuard-compatible suite runner.

Drives the same `vectorguard_target.yaml` + `suites/*.yaml` files the real
VectorGuard CLI consumes, so the security-regression track is runnable in CI and
locally even when the external VectorGuard package isn't installed. Produces the
JSON/Markdown reports used for the naive-vs-hardened case study.

Usage:
    python tools/run_suites.py --target vectorguard_target.yaml \
        --suite suites/rag_injection.yaml --report reports/rag_injection.json \
        [--fail-on-findings]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx
import yaml

APPROX_TOKENS = lambda s: max(1, round(len(s.split()) * 1.3))  # noqa: E731


def load_yaml(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text())


def protected_map(target: dict) -> dict[str, str]:
    return {p["id"]: p["value"] for p in target.get("protected", [])}


def render_body(template: str, message: str, conversation_id: str) -> dict:
    body = template.replace("{{last_user_message}}", json_escape(message))
    body = body.replace("{{conversation_id}}", conversation_id or "")
    # Empty conversation_id -> null so the server starts a fresh conversation.
    body = body.replace('"conversation_id": ""', '"conversation_id": null')
    return json.loads(body)


def json_escape(s: str) -> str:
    return json.dumps(s)[1:-1]


def read_path(obj: dict, path: str):
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def evaluate(fail_if: dict, answer: str, protected: dict, status_codes: list[int]) -> list[str]:
    """Return a list of finding reasons; empty means the case passed."""
    findings = []
    ans_lower = answer.lower()

    for pid in fail_if.get("leaks_protected", []):
        val = protected.get(pid)
        if val and val.lower() in ans_lower:
            findings.append(f"leaked protected value '{pid}'")

    for needle in fail_if.get("response_matches", []):
        if needle.lower() in ans_lower:
            findings.append(f"response contained forbidden text '{needle}'")

    limit = fail_if.get("response_token_count_gt")
    if limit is not None and APPROX_TOKENS(answer) > limit:
        findings.append(f"response exceeded token budget ({APPROX_TOKENS(answer)} > {limit})")

    after = fail_if.get("no_429_after")
    if after is not None:
        # Fail if we never saw a 429 despite flooding past the threshold.
        if 429 not in status_codes:
            findings.append(f"no 429 after {after} requests (rate limiting absent)")

    return findings


def run_case(client: httpx.Client, target: dict, case: dict, protected: dict) -> dict:
    url = target["target"]["url"]
    template = target["target"]["body_template"]
    response_path = target["target"].get("response_path", "answer")
    conversation_id = ""
    last_answer = ""
    status_codes: list[int] = []
    transcript = []

    repeat = case.get("repeat", 1)
    turns = case.get("turns", [])

    for _ in range(repeat):
        for message in turns:
            body = render_body(template, message, conversation_id)
            try:
                resp = client.post(url, json=body, timeout=30)
                status_codes.append(resp.status_code)
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            except Exception as exc:  # network/parse errors are surfaced, not swallowed
                transcript.append({"attack": message, "error": str(exc)})
                continue
            answer = read_path(data, response_path) or ""
            conversation_id = data.get("conversation_id", conversation_id)
            last_answer = answer
            transcript.append(
                {"attack": message, "answer": answer, "mode": data.get("mode"), "status": resp.status_code}
            )

    findings = evaluate(case.get("fail_if", {}), last_answer, protected, status_codes)
    return {
        "id": case["id"],
        "technique": case.get("technique"),
        "passed": not findings,
        "findings": findings,
        "transcript": transcript,
    }


def risk_score(case_result: dict) -> float:
    # Simple severity model: each finding is worth 3 risk points.
    return 3.0 * len(case_result["findings"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--suite", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--fail-on-findings", action="store_true")
    args = ap.parse_args()

    target = load_yaml(args.target)
    suite = load_yaml(args.suite)
    protected = protected_map(target)

    results = []
    with httpx.Client() as client:
        # Discover current mode for the report header.
        try:
            mode = client.get(target["target"]["url"].replace("/api/chat", "/health"), timeout=10).json().get("mode")
        except Exception:
            mode = "unknown"
        for case in suite.get("cases", []):
            results.append(run_case(client, target, case, protected))

    pass_count = sum(1 for r in results if r["passed"])
    fail_count = len(results) - pass_count
    total_risk = sum(risk_score(r) for r in results)

    report = {
        "suite": suite.get("suite"),
        "owasp": suite.get("owasp"),
        "mode": mode,
        "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "risk_score_total": total_risk,
        "pass_rate": round(pass_count / len(results), 4) if results else 1.0,
        "cases": results,
    }

    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    write_markdown(out.with_suffix(".md"), report)

    print(
        f"[{report['suite']}] mode={mode} pass={pass_count} fail={fail_count} "
        f"risk={total_risk} -> {out}"
    )
    for r in results:
        if not r["passed"]:
            print(f"  FAIL {r['id']}: {'; '.join(r['findings'])}")

    if args.fail_on_findings and fail_count:
        return 1
    return 0


def write_markdown(path: Path, report: dict) -> None:
    lines = [
        f"# VectorGuard report: {report['suite']} ({report['mode']} mode)",
        "",
        f"- OWASP: {report['owasp']}",
        f"- Pass: **{report['pass_count']}** / {report['pass_count'] + report['fail_count']} "
        f"(pass rate {report['pass_rate']:.0%})",
        f"- Risk score: **{report['risk_score_total']}**",
        f"- Ran at: {report['ran_at']}",
        "",
        "| Case | Technique | Result | Findings |",
        "|------|-----------|--------|----------|",
    ]
    for r in report["cases"]:
        result = "✅ pass" if r["passed"] else "❌ FAIL"
        findings = "; ".join(r["findings"]) or "—"
        lines.append(f"| {r['id']} | {r['technique']} | {result} | {findings} |")
    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
