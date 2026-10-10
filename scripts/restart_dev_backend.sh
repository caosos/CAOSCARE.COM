#!/usr/bin/env bash
# Restart the EliteDesk DEVELOPMENT backend (:8092) safely. Never touches Linode.
# Preflight runs BEFORE the old process is stopped; any failed check leaves it running.
# Usage: scripts/restart_dev_backend.sh [--check]  (only option; --check = preflight only). Local host only, port 8092 only.
set -u
PORT=8092   # fixed on purpose: no env/arg can redirect the restart
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
PY="/home/caoscare-1/CAOSCARE.COM/backend/.venv/bin/python3"   # fixed
LOG="/tmp/room214_backend_$(git -C "$ROOT" rev-parse --short HEAD).log"
fail() { echo "PREFLIGHT FAILED: $*" >&2; exit 2; }

[ -x "$PY" ] || fail "interpreter missing: $PY"
[ -f "$BACKEND/server.py" ] || fail "no server.py in $BACKEND"
(cd "$BACKEND" && "$PY" -c "import server" >/dev/null 2>&1) || fail "import server failed with $PY"
LEASES=$(mongosh --quiet --eval 'print(db.getSiblingDB("caoscare").resident_aria_leases.countDocuments({}))' 2>/dev/null) \
  || fail "cannot read leases (uncertain: not restarting)"
[ "$LEASES" = "0" ] || fail "live lease(s): $LEASES"
RECENT=$(mongosh --quiet --eval 'const n=new Date(Date.now()-60000).toISOString();const d=db.getSiblingDB("caoscare");print(d.resident_aria_lease_events.countDocuments({created_at:{$gte:n}})+d.realtime_diagnostics.countDocuments({created_at:{$gte:n}}))' 2>/dev/null) \
  || fail "cannot read recent activity"
[ "$RECENT" = "0" ] || fail "call activity in the last 60 s: $RECENT"
OLD_PID=$(ss -ltnp 2>/dev/null | grep ":$PORT " | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2)
echo "preflight ok: python=$PY leases=0 recent=0 old_pid=${OLD_PID:-none} sha=$(git -C "$ROOT" rev-parse --short HEAD)"
[ "${1:-}" = "--check" ] && exit 0

[ -n "$OLD_PID" ] && { kill "$OLD_PID"; for _ in $(seq 1 20); do kill -0 "$OLD_PID" 2>/dev/null || break; sleep 0.5; done; }
(cd "$BACKEND" && setsid nohup "$PY" -m uvicorn server:app --host 0.0.0.0 --port "$PORT" >"$LOG" 2>&1 &)
for _ in $(seq 1 40); do
  curl -sf "localhost:$PORT/api/health" >/dev/null && { echo "RESTART OK pid=$(ss -ltnp | grep ":$PORT " | grep -o 'pid=[0-9]*' | head -1) log=$LOG"; exit 0; }
  sleep 1
done
echo "RESTART FAILED: backend not healthy on :$PORT; the old process was stopped. Log: $LOG. Relaunch the previous commit with the same command." >&2
tail -5 "$LOG" >&2
exit 3
