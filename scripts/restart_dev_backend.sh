#!/usr/bin/env bash
# Restart the EliteDesk DEVELOPMENT backend (:8092). Local host only; never Linode.
# Usage: scripts/restart_dev_backend.sh [--check]   (--check = preflight only; any other argument is rejected)
#
# Order: validate -> identify the running process -> prove the NEW code starts on a spare port
# (the healthy service is untouched until this passes) -> stop old (verified gone) -> start new
# (verified: new pid owns the port, healthy). There is NO automatic rollback: on failure after the
# stop it exits non-zero and prints the exact manual recovery (prior log/sha are recorded).
set -u
PORT=8092                                   # fixed on purpose: nothing can redirect the restart
EXPECT_ROOT="/home/caoscare-1/CAOSCARE-INTEGRATION"
PY="/home/caoscare-1/CAOSCARE.COM/backend/.venv/bin/python3"
fail() { echo "PREFLIGHT FAILED: $*" >&2; exit 2; }

[ "$#" -eq 0 ] || { [ "$#" -eq 1 ] && [ "$1" = "--check" ]; } || fail "unsupported argument(s): $* (only --check)"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ "$ROOT" = "$EXPECT_ROOT" ] || fail "run from the integration repo ($EXPECT_ROOT), not $ROOT"
BACKEND="$ROOT/backend"
SHA="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo nogit)"
LOG="/tmp/room214_backend_${SHA}.log"
STATE="/tmp/restart_dev_backend.last"
CAND=$((PORT + 1))
LAUNCH=("$PY" -m uvicorn server:app --host 0.0.0.0 --port)

[ -x "$PY" ] || fail "interpreter missing: $PY"
[ -f "$BACKEND/server.py" ] || fail "no server.py in $BACKEND"
[ -f "$BACKEND/.env" ] || fail "no $BACKEND/.env (server.py loads it; recovery would lack configuration)"
(cd "$BACKEND" && "$PY" -c "import server" >/dev/null 2>&1) || fail "import server failed with $PY"
guard() {
  local L R
  L=$(mongosh --quiet --eval 'print(db.getSiblingDB("caoscare").resident_aria_leases.countDocuments({}))' 2>/dev/null) \
    || fail "$1: cannot read leases (uncertain: not restarting)"
  [ "$L" = "0" ] || fail "$1: live lease(s): $L"
  R=$(mongosh --quiet --eval 'const n=new Date(Date.now()-60000).toISOString();const d=db.getSiblingDB("caoscare");print(d.resident_aria_lease_events.countDocuments({created_at:{$gte:n}})+d.realtime_diagnostics.countDocuments({created_at:{$gte:n}}))' 2>/dev/null) \
    || fail "$1: cannot read recent activity (uncertain: not restarting)"
  [ "$R" = "0" ] || fail "$1: call activity in the last 60 s: $R"
}
guard preflight

listener_pid() { ss -ltnp 2>/dev/null | grep -E "[:.]$1 " | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2; }
OLD_PID="$(listener_pid "$PORT")"
if [ -n "$OLD_PID" ]; then
  OLD_CMD="$(tr '\0' ' ' < /proc/$OLD_PID/cmdline 2>/dev/null)"
  OLD_CWD="$(readlink /proc/$OLD_PID/cwd 2>/dev/null)"
  OLD_LOG="$(readlink /proc/$OLD_PID/fd/1 2>/dev/null)"
  case "$OLD_CMD" in *"uvicorn server:app"*"--port $PORT"*) ;; *) fail "pid $OLD_PID on :$PORT is not the dev backend (cmd: $OLD_CMD)";; esac
  [ "$OLD_CWD" = "$BACKEND" ] || fail "pid $OLD_PID cwd is $OLD_CWD, expected $BACKEND"
  PRIOR_SHA="$(basename "$OLD_LOG" .log | sed -n 's/^room214_backend_//p')"
  [ -n "$PRIOR_SHA" ] && git -C "$ROOT" cat-file -e "${PRIOR_SHA}^{commit}" 2>/dev/null \
    || fail "cannot identify a known-good prior commit from the running process log ($OLD_LOG); refusing to stop it"
fi
git -C "$ROOT" diff --quiet HEAD -- backend || fail "backend working tree has uncommitted changes; runtime would not match $SHA"
[ -z "$(listener_pid "$CAND")" ] || fail "spare port $CAND is in use (bind conflict); not restarting"
[ -d /tmp ] && [ -w /tmp ] || fail "/tmp not writable (no log/state)"

# Prove the new code starts and answers, on the spare port, before touching the healthy service.
CLOG="/tmp/restart_dev_backend.candidate.log"
( cd "$BACKEND" && exec setsid nohup "${LAUNCH[@]}" "$CAND" ) >"$CLOG" 2>&1 </dev/null &
CPID=$!; CK=0
for _ in $(seq 1 40); do curl -sf "localhost:$CAND/api/health" >/dev/null && { CK=1; break; }; sleep 1; done
kill "$CPID" 2>/dev/null; for _ in $(seq 1 20); do kill -0 "$CPID" 2>/dev/null || break; sleep 0.5; done
[ "$CK" = 1 ] || { tail -5 "$CLOG" >&2; fail "new code did not start healthy on spare port $CAND; running service untouched"; }
kill -0 "$CPID" 2>/dev/null && fail "spare process $CPID would not stop; running service untouched"

echo "preflight ok: sha=$SHA leases=0 recent=0 old_pid=${OLD_PID:-none} old_log=${OLD_LOG:-none} candidate_started_ok=1"
[ "${1:-}" = "--check" ] && exit 0
printf 'time=%s sha=%s old_pid=%s old_cmd=%s old_cwd=%s old_log=%s\n' "$(date -u +%FT%TZ)" "$SHA" "${OLD_PID:-none}" "${OLD_CMD:-}" "${OLD_CWD:-}" "${OLD_LOG:-}" >"$STATE"

RB="/tmp/rollback_${PRIOR_SHA:-prior}"
RECOVER="MANUAL recovery (no automatic rollback; .env is symlinked, never copied): git -C $ROOT worktree add $RB ${PRIOR_SHA:-<prior-sha>} && ln -s $BACKEND/.env $RB/backend/.env && cd $RB/backend && ${LAUNCH[*]} $PORT  (prior log ${OLD_LOG:-none}; state $STATE)"
guard "pre-stop refresh"
if [ -n "$OLD_PID" ]; then
  kill "$OLD_PID"; for _ in $(seq 1 30); do kill -0 "$OLD_PID" 2>/dev/null || break; sleep 0.5; done
  kill -0 "$OLD_PID" 2>/dev/null && { echo "STOP FAILED: old pid $OLD_PID still alive; nothing started. Service left as is." >&2; exit 4; }
  for _ in $(seq 1 20); do [ -z "$(listener_pid "$PORT")" ] && break; sleep 0.5; done
  [ -z "$(listener_pid "$PORT")" ] || { echo "STOP FAILED: :$PORT still listening after old pid exited. $RECOVER" >&2; exit 4; }
fi
( cd "$BACKEND" && exec env CAOSCARE_RUNTIME_SHA="$SHA" setsid nohup "${LAUNCH[@]}" "$PORT" ) >"$LOG" 2>&1 </dev/null &
NEWSTART=$!
for _ in $(seq 1 40); do
  if curl -sf "localhost:$PORT/api/health" >/dev/null; then
    NP="$(listener_pid "$PORT")"
    NC="$(tr '\0' ' ' < /proc/$NP/cmdline 2>/dev/null)"
    NW="$(readlink /proc/$NP/cwd 2>/dev/null)"
    NE="$(tr '\0' '\n' < /proc/$NP/environ 2>/dev/null | sed -n 's/^CAOSCARE_RUNTIME_SHA=//p')"
    if [ -n "$NP" ] && [ "$NP" = "$NEWSTART" ] && [ "$NE" = "$SHA" ] && [ "$NP" != "${OLD_PID:-x}" ] && [ "$NW" = "$BACKEND" ] && case "$NC" in *"uvicorn server:app"*"--port $PORT"*) true;; *) false;; esac; then
      echo "RESTART OK pid=$NP (launched $NEWSTART) runtime_sha_env=$NE (backend tree clean at $SHA) cwd=$NW log=$LOG"; exit 0
    fi
    echo "RESTART UNVERIFIED: healthy but listener pid=$NP is not the launched process / runtime sha mismatch (pid=$NP launched=$NEWSTART env_sha=$NE cmd: $NC). $RECOVER" >&2; exit 5
  fi
  sleep 1
done
echo "RESTART FAILED: new backend not healthy on :$PORT; the old process was stopped. $RECOVER" >&2
tail -5 "$LOG" >&2
exit 3
