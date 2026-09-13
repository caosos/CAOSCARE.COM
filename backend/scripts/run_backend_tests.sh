#!/usr/bin/env bash
# Canonical backend test gate for CAOSCare. See docs/BACKEND_TEST_GATE.md for
# the full explanation of what this does and why - this script is the single
# reproducible command that doc describes; keep them in sync.
#
# What this guarantees, that an ad-hoc `pytest tests/` does not:
#   - a fresh test database for every run (no state bleeding from a prior run)
#   - a freshly-started backend process (no stale in-memory admin-login
#     throttle state from a previous invocation)
#   - CAOSCARE_TEST_HOOKS=1 on that backend, so the one test that needs the
#     documented simulated-failure hook (test_ai_escalation.py) actually
#     exercises it instead of silently taking the real-acceptance branch
#   - MONGO_URL / DB_NAME / JWT_SECRET set identically on both the backend
#     process and the pytest process itself (conftest.py fails fast with a
#     clear message if these are missing from the pytest side)
#   - real_hardware-marked tests (test_light_control.py, test_climate_control.py)
#     excluded by default (backend/pytest.ini) - opt in explicitly with
#     `-m real_hardware` only when you intend to command physical devices
#
# What this does NOT do: set OPENAI_API_KEY. Tests that need a real key
# (chat/tts/haiku/memory-extraction/realtime-session) skip cleanly with a
# documented reason when it's absent - see conftest.py's
# skip_if_openai_unavailable fixture. Export OPENAI_API_KEY before running
# this script to also exercise those.
#
# Usage:
#   ./scripts/run_backend_tests.sh                # everything except real_hardware
#   ./scripts/run_backend_tests.sh -k rf_semantics # pass args straight to pytest
#   OPENAI_API_KEY=sk-... ./scripts/run_backend_tests.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."   # backend/

PORT="${CAOSCARE_TEST_PORT:-8070}"
DB_NAME="${CAOSCARE_TEST_DB:-caoscare_backend_test_gate}"
MONGO_URL="${MONGO_URL:-mongodb://localhost:27017}"
JWT_SECRET="${JWT_SECRET:-canonical-backend-test-gate-secret}"
VENV_PY="${CAOSCARE_TEST_VENV_PY:-/home/caoscare-1/CAOSCARE.COM/backend/.venv/bin/python3}"

if ! command -v mongosh >/dev/null 2>&1; then
  echo "mongosh not found - required to drop the test database before each run" >&2
  exit 1
fi

echo "==> Dropping test database '$DB_NAME' for a fresh run"
mongosh --quiet --eval "db.getSiblingDB('$DB_NAME').dropDatabase()" >/dev/null

echo "==> Starting backend on 127.0.0.1:$PORT (CAOSCARE_TEST_HOOKS=1, demo seed on)"
MONGO_URL="$MONGO_URL" DB_NAME="$DB_NAME" JWT_SECRET="$JWT_SECRET" \
  CAOSCARE_ENABLE_DEMO_SEED=true CAOSCARE_TEST_HOOKS=1 \
  CORS_ORIGINS="http://localhost:3000" \
  "$VENV_PY" -m uvicorn server:app --host 127.0.0.1 --port "$PORT" \
  > /tmp/caoscare_backend_test_gate.log 2>&1 &
SERVER_PID=$!

cleanup() {
  kill "$SERVER_PID" >/dev/null 2>&1 || true
  wait "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "==> Waiting for /api/health"
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
  echo "Backend never became healthy - see /tmp/caoscare_backend_test_gate.log" >&2
  tail -50 /tmp/caoscare_backend_test_gate.log >&2
  exit 1
fi
echo "==> Backend healthy"

echo "==> Running pytest"
MONGO_URL="$MONGO_URL" DB_NAME="$DB_NAME" JWT_SECRET="$JWT_SECRET" \
  REACT_APP_BACKEND_URL="http://127.0.0.1:$PORT" \
  "$VENV_PY" -m pytest tests/ -q "$@"
