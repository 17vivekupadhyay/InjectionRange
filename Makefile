.PHONY: up down logs test case-study suites eval fmt

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f backend

# Offline security-logic unit tests (no DB / no keys).
test:
	python backend/tests/test_offline_core.py

# Regenerate the naive-vs-hardened case study via the offline harness.
case-study:
	python tools/offline_case_study.py

# Live suites vs both modes (requires the stack running).
suites:
	python tools/run_all.py

# Retrieval-quality eval against a running backend.
eval:
	curl -s -X POST localhost:8000/api/eval/run | python -m json.tool
