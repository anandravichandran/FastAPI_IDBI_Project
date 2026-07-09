.PHONY: install install-dev run run-advisor run-coach run-budget run-savings run-rag run-market test test-advisor test-coach test-budget test-savings test-rag test-market test-integration test-all lint format docker

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

# Run the whole suite (advisor + coach + budget + savings + rag + market) behind one gateway.
run:
	uvicorn server:app --reload --host 0.0.0.0 --port 8000

# Optionally run a single sub-app standalone.
run-advisor:
	uvicorn advisor.main:app --reload --port 8001

run-coach:
	uvicorn coach.main:app --reload --port 8002

run-budget:
	uvicorn budget.main:app --reload --port 8003

run-savings:
	uvicorn savings.main:app --reload --port 8004

run-rag:
	uvicorn rag.main:app --reload --port 8005

run-market:
	uvicorn market.main:app --reload --port 8006

test:
	pytest

test-advisor:
	pytest tests/advisor

test-coach:
	pytest tests/coach

test-budget:
	pytest tests/budget

test-savings:
	pytest tests/savings

test-rag:
	pytest tests/rag

test-market:
	pytest tests/market

# Run curl-based integration / smoke tests against a running server (start one first).
test-integration:
	bash scripts/curl_tests.sh

# Full pipeline: unit tests (pytest) → integration tests (curl).
test-all:
	bash scripts/run_all_tests.sh

lint:
	ruff check advisor coach budget savings rag market app common server.py tests

format:
	ruff check --fix advisor coach budget savings rag market server.py tests

docker:
	docker compose up --build
