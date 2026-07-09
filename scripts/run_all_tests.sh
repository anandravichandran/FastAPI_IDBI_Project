#!/usr/bin/env bash
# =============================================================================
# run_all_tests.sh — one-command test pipeline for the Financial Suite
# =============================================================================
#
# This script:
#   1. Runs pytest (unit + integration tests)
#   2. Starts the FastAPI server (if not already running)
#   3. Waits for the server to become healthy
#   4. Executes the curl integration / smoke-test suite
#   5. Prints a coloured summary
#   6. Shuts down the server if this script started it
#
# Usage:
#   ./scripts/run_all_tests.sh              # uses .venv, starts server
#   SERVER_ALREADY_RUNNING=1 ./scripts/run_all_tests.sh   # skip server mgmt
#
# Environment variables:
#   SERVER_ALREADY_RUNNING  Set to 1 to skip server start/stop (CI use case)
#   BASE_URL                Target for curl tests (default http://localhost:8000)
#   API_KEY                 X-API-Key for protected endpoints
#   COVERAGE                Set to 1 to include --cov flag in pytest
#   VERBOSE                 Set to 1 for verbose pytest output
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

BASE_URL="${BASE_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-}"
COVERAGE="${COVERAGE:-0}"
VERBOSE="${VERBOSE:-0}"
SERVER_ALREADY_RUNNING="${SERVER_ALREADY_RUNNING:-0}"

# ---- colour helpers ---------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[1;34m'; BOLD='\033[1m'; NC='\033[0m'
pass() { echo -e "  ${GREEN}PASS${NC} $1"; }
fail() { echo -e "  ${RED}FAIL${NC} $1"; }
info() { echo -e "  ${BLUE}INFO${NC} $1"; }
warn() { echo -e "  ${YELLOW}WARN${NC} $1"; }

section() { printf "\n${BOLD}━━━ %s ━━━${NC}\n" "$1"; }

cleanup() {
  if [[ "$SERVER_ALREADY_RUNNING" -eq 0 && -n "${SERVER_PID:-}" ]]; then
    info "Stopping server (PID $SERVER_PID) …"
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    pass "Server stopped."
  fi
}
trap cleanup EXIT

# ==============================================================================
section "PHASE 1 — Python environment sanity"
# ------------------------------------------------------------------------------
if command -v python3 &>/dev/null; then
  PY=python3
elif command -v python &>/dev/null; then
  PY=python
else
  fail "No Python interpreter found."
  exit 1
fi

# Prefer .venv if it exists.
if [[ -f ".venv/bin/python" ]]; then
  PY=".venv/bin/python"
elif [[ -f ".venv/Scripts/python" ]]; then
  PY=".venv/Scripts/python"
fi

info "Python: $($PY --version 2>&1)"
info "Pip:    $($PY -m pip --version 2>&1 | head -1)"

# Install dev dependencies if missing.  (Idempotent — already-installed
# packages are skipped by pip.)
if [[ ! -d ".venv" ]]; then
  warn "No .venv found — creating one."
  python3 -m venv .venv
fi
$PY -m pip install -q -r requirements-dev.txt 2>/dev/null && pass "Dev dependencies ready" || warn "pip install had warnings"

# ==============================================================================
section "PHASE 2 — pytest (unit + integration)"
# ------------------------------------------------------------------------------
PYTEST_ARGS=()
if [[ "$COVERAGE" -eq 1 ]]; then PYTEST_ARGS+=(--cov=. --cov-report=term-missing); fi
if [[ "$VERBOSE" -eq 1 ]]; then PYTEST_ARGS+=(-v); fi

set +e
$PY -m pytest "${PYTEST_ARGS[@]}" tests/
PYTEST_EXIT=$?
set -e

if [[ $PYTEST_EXIT -eq 0 ]]; then
  pass "pytest — all tests passed"
else
  fail "pytest — exit code $PYTEST_EXIT (see above for details)"
  # Continue to integration tests even if pytest fails, to gather full picture.
fi

# ==============================================================================
section "PHASE 3 — Start server (if not already running)"
# ------------------------------------------------------------------------------
if [[ "$SERVER_ALREADY_RUNNING" -eq 1 ]]; then
  info "SERVER_ALREADY_RUNNING=1 — skipping server start."
else
  # Check whether something is already listening on the target port.
  PORT="${BASE_URL##*:}"
  PORT="${PORT:-8000}"
  if curl -sf -o /dev/null "$BASE_URL/health"; then
    info "Server already responding on $BASE_URL — reusing it."
    SERVER_ALREADY_RUNNING=1
  else
    info "Starting uvicorn on $PORT …"
    $PY -m uvicorn server:app --host 0.0.0.0 --port "$PORT" --log-level warning &
    SERVER_PID=$!
    info "Server PID $SERVER_PID"
  fi
fi

# ==============================================================================
section "PHASE 4 — Wait for healthy server"
# ------------------------------------------------------------------------------
MAX_RETRIES=30
RETRY_DELAY=2
HEALTHY=false

for i in $(seq 1 $MAX_RETRIES); do
  if curl -sf -o /dev/null "$BASE_URL/health"; then
    HEALTHY=true
    pass "Server is healthy (attempt $i)"
    break
  fi
  info "Waiting for server … attempt $i/$MAX_RETRIES"
  sleep "$RETRY_DELAY"
done

if ! $HEALTHY; then
  fail "Server did not become healthy within $((MAX_RETRIES * RETRY_DELAY))s"
  exit 1
fi

# ==============================================================================
section "PHASE 5 — curl integration / smoke tests"
# ------------------------------------------------------------------------------
info "Running: BASE_URL=$BASE_URL scripts/curl_tests.sh"
export BASE_URL API_KEY

set +e
bash "$SCRIPT_DIR/curl_tests.sh"
CURL_EXIT=$?
set -e

if [[ $CURL_EXIT -eq 0 ]]; then
  pass "curl_tests.sh — all integration tests passed"
else
  fail "curl_tests.sh — $CURL_EXIT test(s) failed"
fi

# ==============================================================================
section "FINAL SUMMARY"
# ------------------------------------------------------------------------------
if [[ $PYTEST_EXIT -eq 0 && $CURL_EXIT -eq 0 ]]; then
  echo -e "\n${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
  echo -e "${GREEN}${BOLD}  ALL TESTS PASSED  —  ready for deployment${NC}"
  echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}\n"
  exit 0
else
  echo -e "\n${RED}${BOLD}═══════════════════════════════════════════════════${NC}"
  echo -e "${RED}${BOLD}  SOME TESTS FAILED  —  review output above${NC}"
  echo -e "${RED}${BOLD}═══════════════════════════════════════════════════${NC}\n"
  exit 1
fi
