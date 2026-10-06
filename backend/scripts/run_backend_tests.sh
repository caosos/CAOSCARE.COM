#!/usr/bin/env bash
# Canonical backend test gate for CAOSCare. See docs/BACKEND_TEST_GATE.md for
# the full explanation of what this does and why - this script is the single
# reproducible command that doc describes; keep them in sync.
#
# What this guarantees, that an ad-hoc `pytest tests/` does not:
#   - a fresh test database for every run (no state bleeding from a prior run)
#   - a freshly-started backend process (no stale in-memory admin-login
#     throttle state from a previous invocation)
#   - the tests talk to THAT backend: the run refuses a port something else
#     already listens on, and /api/health must echo this run's id before
#     pytest starts (and again after it finishes)
#   - one backend log file per run (never shared with another gate run)
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
#   CAOSCARE_TEST_PORT=8071 CAOSCARE_TEST_DB=my_gate_db ./scripts/run_backend_tests.sh
#   CAOSCARE_TEST_LOG=/path/to/backend.log ./scripts/run_backend_tests.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."   # backend/

PORT="${CAOSCARE_TEST_PORT:-8070}"
DB_NAME="${CAOSCARE_TEST_DB:-caoscare_backend_test_gate}"
MONGO_URL="${MONGO_URL:-mongodb://localhost:27017}"
JWT_SECRET="${JWT_SECRET:-canonical-backend-test-gate-secret}"
VENV_PY="${CAOSCARE_TEST_VENV_PY:-/home/caoscare-1/CAOSCARE.COM/backend/.venv/bin/python3}"
GATE_RUN_ID="$(cat /proc/sys/kernel/random/uuid 2>/dev/null || echo "$(date +%s%N)-$$-$RANDOM$RANDOM")"
LOG_FILE="${CAOSCARE_TEST_LOG:-$(mktemp "${TMPDIR:-/tmp}/caoscare_backend_test_gate.XXXXXX.log")}"

echo "==> Gate run $GATE_RUN_ID (port $PORT, database '$DB_NAME')"
echo "==> Backend log: $LOG_FILE"

# Nothing may already be listening on the port: if it were, our backend could
# not bind and the health check below would be answered by someone else's
# server. Checked before any side effect (database drop, backend start).
if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then
  echo "Port $PORT on 127.0.0.1 is already in use by another process - refusing to run." >&2
  echo "Pick a free port with CAOSCARE_TEST_PORT=<port> (and a separate CAOSCARE_TEST_DB)." >&2
  exit 1
fi

if ! command -v mongosh >/dev/null 2>&1; then
  echo "mongosh not found - required to drop the test database before each run" >&2
  exit 1
fi

echo "==> Dropping test database '$DB_NAME' for a fresh run"
mongosh --quiet --eval "db.getSiblingDB('$DB_NAME').dropDatabase()" >/dev/null

echo "==> Starting backend on 127.0.0.1:$PORT (CAOSCARE_TEST_HOOKS=1, demo seed on)"
MONGO_URL="$MONGO_URL" DB_NAME="$DB_NAME" JWT_SECRET="$JWT_SECRET" \
  CAOSCARE_ENABLE_DEMO_SEED=true CAOSCARE_TEST_HOOKS=1 \
  CAOSCARE_TEST_GATE_RUN_ID="$GATE_RUN_ID" \
  CORS_ORIGINS="http://localhost:3000" \
  "$VENV_PY" -m uvicorn server:app --host 127.0.0.1 --port "$PORT" \
  > "$LOG_FILE" 2>&1 &
SERVER_PID=$!

cleanup() {
  kill "$SERVER_PID" >/dev/null 2>&1 || true
  wait "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT

# Healthy = our process is alive AND /api/health echoes this run's id.
wait_for_our_backend() {
  "$VENV_PY" scripts/gate_wait_healthy.py \
    --port "$PORT" --run-id "$GATE_RUN_ID" --pid "$SERVER_PID" --timeout "$1"
}

echo "==> Waiting for /api/health from this run's backend"
if ! wait_for_our_backend 30; then
  echo "Backend for gate run $GATE_RUN_ID never became healthy - see $LOG_FILE" >&2
  tail -50 "$LOG_FILE" >&2
  exit 1
fi
echo "==> Backend healthy (pid $SERVER_PID, gate run $GATE_RUN_ID)"

echo "==> Running pytest"
set +e
MONGO_URL="$MONGO_URL" DB_NAME="$DB_NAME" JWT_SECRET="$JWT_SECRET" \
  REACT_APP_BACKEND_URL="http://127.0.0.1:$PORT" \
  CAOSCARE_TEST_GATE_RUN_ID="$GATE_RUN_ID" \
  "$VENV_PY" -m pytest tests/ -q "$@"
PYTEST_STATUS=$?
set -e

# The result only counts if the same backend served the whole run.
if ! wait_for_our_backend 5; then
  echo "This run's backend (pid $SERVER_PID) was gone or replaced by the end of pytest -" \
       "results are not trustworthy. See $LOG_FILE" >&2
  tail -50 "$LOG_FILE" >&2
  exit 1
fi
exit "$PYTEST_STATUS"
