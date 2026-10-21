#!/usr/bin/env bash
# Control script for the EliteDesk home wake endpoint (systemd --user).
#   ctl.sh start               start whatever is down, in order, and prove readiness (safe to re-run)
#   ctl.sh test-audio-access   can this user see the eMeet? (prints the fix if not)
#   ctl.sh install             venv + units + env file, enable and start the services
#   ctl.sh rebuild [--force]   build the frontend into ~/.cache/aria-wake/build and swap it in
#   ctl.sh restart-page [--force]   restart the static server + headless page
#   ctl.sh install-voice       install/start only the low-cost voice turn detector (aria-voice.service)
#   ctl.sh status | logs [-f] | restart | uninstall
# The Room page is a PRODUCTION BUILD served on ARIA_WAKE_PAGE_PORT (default 3002), not the
# CRA dev server, so frontend merges do not touch a live call until 'rebuild'.
# Nothing here uses sudo. Not run by the engineer who wrote it - see the runbook:
# docs/reports/2026-10-08-room214-wake-physical-runbook.md
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
UNITS="$HOME/.config/systemd/user"
CONF="$HOME/.config/aria-wake"
MATCH="${ARIA_WAKE_DEVICE_MATCH:-eMeet|EMEET|Luna|OfficeCore}"
CHROME="$(command -v google-chrome || command -v chromium || true)"

audio_access() {
  local ok=0
  echo "user: $(id -un)   groups: $(id -nG)"
  id -nG | tr ' ' '\n' | grep -qx audio && echo "  in group audio: yes" || echo "  in group audio: NO"
  echo "PulseAudio sources:"; pactl list short sources 2>&1 | sed 's/^/  /'
  echo "PulseAudio sinks:";   pactl list short sinks   2>&1 | sed 's/^/  /'
  if pactl list short sources 2>/dev/null | grep -Eiq "$MATCH" && pactl list short sinks 2>/dev/null | grep -Eiq "$MATCH"; then
    echo "RESULT: eMeet source AND sink are visible to this user."; ok=1
  elif pactl list short sources 2>/dev/null | grep -Eiq "$MATCH"; then
    echo "RESULT: eMeet source visible but no matching sink."
  else
    echo "RESULT: the eMeet is NOT visible to this user."
    echo "  /dev/snd access is granted to the logged-in seat user or group audio. Run once (needs sudo):"
    echo "      sudo usermod -aG audio $(id -un)"
    echo "  then log out and back in (or reboot) so the new group applies, and run this again."
    echo "  ALSA view: $(arecord -l 2>&1 | head -3 | tr '\n' ' ')"
  fi
  return $((1 - ok))
}

REPO="$(cd "$DIR/../.." && pwd)"
CACHE="${ARIA_WAKE_CACHE:-$HOME/.cache/aria-wake}"
PAGE_PORT="${ARIA_WAKE_PAGE_PORT:-3002}"

# Refuse while a live Aria session holds a room lease (a live lease = status
# activating/active with last_seen_at within 45 s). No HTTP read endpoint exists, so
# this asks MongoDB directly; if it cannot be asked, require --force.
live_call_guard() {
  [ "${1:-}" = "--force" ] && { echo "warning: --force, skipping live-call check" >&2; return 0; }
  local since n
  since="$(date -u -d '-45 seconds' +%Y-%m-%dT%H:%M:%S)"
  if ! command -v mongosh >/dev/null; then
    echo "cannot check for a live call (mongosh missing). Check Admin > Live, then re-run with --force." >&2; return 1
  fi
  n="$(mongosh --quiet "${ARIA_WAKE_MONGO_URL:-mongodb://localhost:27017}/${ARIA_WAKE_DB:-caoscare}" --eval \
    "db.resident_aria_leases.countDocuments({status:{\$in:['activating','active']}, last_seen_at:{\$gte:'$since'}})" 2>/dev/null | tail -1)" || n=""
  case "$n" in
    0) return 0 ;;
    ''|*[!0-9]*) echo "could not read leases from MongoDB; verify no call is live, then re-run with --force." >&2; return 1 ;;
    *) echo "REFUSED: $n live Aria session(s). Wait for the call to end, or use --force." >&2; return 1 ;;
  esac
}

build_page() {
  need yarn "yarn (corepack enable)"
  local out="$CACHE/build" new="$CACHE/build.new"
  mkdir -p "$CACHE"; rm -rf "$new"
  # REACT_APP_BUILD_SHA: the page reports its own build revision to the backend's
  # self-code inspection (Room 214 only) so "is this the page you are running" is truthful.
  # RQ-056 transcription hint ON for the room page (owner, 2026-10-15): biases English/Spanish vocabulary without
  # pinning a language. Room 214 short English turns were transcribed as Finnish/Japanese/Persian/French.
  # Mic/detector measurement (owner-approved for Room 214, 2026-10-17): numbers-only diagnostics, only for the
  # kiosks named by ARIA_WAKE_DIAG_KIOSKS in aria-wake.env (micLevelTelemetry.js). Unset or empty = off.
  local diag; diag="$(sed -n 's/^ARIA_WAKE_DIAG_KIOSKS=//p' "$CONF/aria-wake.env" 2>/dev/null | tail -1)"
  (cd "$REPO/frontend" && BUILD_PATH="$new" REACT_APP_BACKEND_URL="http://localhost:$PAGE_PORT" \
    REACT_APP_BUILD_SHA="$(git -C "$REPO" rev-parse HEAD)" REACT_APP_TRANSCRIPTION_HINT=1 \
    REACT_APP_MIC_LEVEL_TELEMETRY="${diag:+1}" REACT_APP_MIC_LEVEL_TELEMETRY_KIOSKS="$diag" yarn build)
  [ -f "$new/index.html" ] || { echo "build failed: no index.html" >&2; exit 1; }
  rm -rf "$CACHE/build.prev"; [ -d "$out" ] && mv "$out" "$CACHE/build.prev"
  mv "$new" "$out"   # server reads files per request: no restart needed
  echo "built $(git -C "$REPO" rev-parse --short HEAD) -> $out"
}

need() { command -v "$1" >/dev/null || { echo "missing: $1 ($2)" >&2; exit 1; }; }

# Low-cost Aria voice: local turn detection (room-node/aria_voice), same venv packages as the wake listener.
VOICE_DIR="$(cd "$DIR/../aria_voice" && pwd)"
install_voice() {
  if [ ! -f "$VOICE_DIR/model/silero_vad.onnx" ]; then
    if [ -n "${ARIA_VOICE_MODEL_SRC:-}" ] && [ -f "$ARIA_VOICE_MODEL_SRC/silero_vad.onnx" ]; then
      mkdir -p "$VOICE_DIR/model"; cp "$ARIA_VOICE_MODEL_SRC/silero_vad.onnx" "$VOICE_DIR/model/"
    else
      echo "VAD model missing: set ARIA_VOICE_MODEL_SRC=<dir with silero_vad.onnx>" >&2; exit 1
    fi
  fi
  mkdir -p "$UNITS"
  sed -e "s#@DIR@#$DIR#g" -e "s#@VOICE_DIR@#$VOICE_DIR#g" "$VOICE_DIR/systemd/aria-voice.service.in" > "$UNITS/aria-voice.service"
}

install_all() {
  need systemctl "systemd"; need pactl "pulseaudio-utils"; need curl "curl"
  [ -n "$CHROME" ] || { echo "missing: google-chrome or chromium" >&2; exit 1; }
  if [ ! -f "$DIR/model/tokens.txt" ]; then
    if [ -n "${ARIA_WAKE_MODEL_SRC:-}" ] && [ -f "$ARIA_WAKE_MODEL_SRC/tokens.txt" ]; then
      mkdir -p "$DIR/model"; cp "$ARIA_WAKE_MODEL_SRC"/{tokens.txt,*.int8.onnx} "$DIR/model/"
    else
      echo "model missing in $DIR/model - see README.md Setup, or set ARIA_WAKE_MODEL_SRC=<dir with tokens.txt and *.int8.onnx>" >&2; exit 1
    fi
  fi
  if [ ! -x "$DIR/.venv/bin/python" ]; then
    python3 -m venv "$DIR/.venv"; "$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt"
  fi
  need node "node"
  [ -f "$CACHE/build/index.html" ] || build_page
  mkdir -p "$UNITS" "$CONF"
  [ -f "$CONF/aria-wake.env" ] || cp "$DIR/systemd/aria-wake.env.example" "$CONF/aria-wake.env"
  sed "s#@DIR@#$DIR#g" "$DIR/systemd/aria-wake.service.in" > "$UNITS/aria-wake.service"
  sed -e "s#@DIR@#$DIR#g" -e "s#@NODE@#$(command -v node)#g" "$DIR/systemd/aria-wake-page.service.in" > "$UNITS/aria-wake-page.service"
  sed "s#@CHROME@#$CHROME#g" "$DIR/systemd/aria-wake-kiosk.service.in" > "$UNITS/aria-wake-kiosk.service"
  install_voice
  systemctl --user daemon-reload
  systemctl --user enable --now aria-wake.service aria-wake-page.service aria-wake-kiosk.service aria-voice.service
  echo "installed. Edit $CONF/aria-wake.env (PULSE_SOURCE/PULSE_SINK/ARIA_WAKE_SOURCE) and 'ctl.sh restart'."
  echo "To start at boot without a login:  loginctl enable-linger $(id -un)"
}

# One idempotent start for this EliteDesk's Room endpoint, as the account that owns the units (caoscare-1).
# Order: MongoDB -> backend :8092 -> page :3002 -> eMeet in this user's audio -> listener :8765 -> kiosk.
# Starts only what is down; restarts nothing that is up. A live call is never touched. Sends no TV/device
# command and starts no paid call. Every run writes a receipt; a failure names the exact blocker.
start_all() {
  local ts state rcpt port_owner since n src snk url clients cfg transport model
  ts="$(date +%Y%m%dT%H%M%S%z)"; state="$HOME/.local/state/caoscare-room-start"; mkdir -p "$state"
  rcpt="$state/$ts.json"; local -a done_steps=()
  finish() {   # finish RESULT DETAIL
    python3 - "$rcpt" "$1" "$2" "$(git -C "$REPO" rev-parse --short HEAD)" "${done_steps[@]}" <<'PY'
import datetime, json, os, sys
p, result, detail, sha, *steps = sys.argv[1:]
json.dump({"at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "action": "ctl.sh start",
           "account": os.environ.get("USER"), "checkout_sha": sha, "result": result, "detail": detail,
           "steps": steps, "paid_call_started": False, "tv_command_sent": False}, open(p, "w"), indent=2)
os.chmod(p, 0o600)
PY
    echo "$1: $2"; echo "PAID_CALL_STARTED=false"; echo "RECEIPT=$rcpt"
    [ "$1" = READY ] || [ "$1" = IN_CALL ]
  }
  set -a; . "$CONF/aria-wake.env"; set +a
  src="$ARIA_WAKE_SOURCE"; snk="$PULSE_SINK"; url="$ARIA_WAKE_PAGE_URL"
  since="$(date -u -d '-45 seconds' +%Y-%m-%dT%H:%M:%S)"
  n="$(mongosh --quiet "mongodb://localhost:27017/caoscare" --eval \
    "db.resident_aria_leases.countDocuments({status:{\$in:['activating','active']}, last_seen_at:{\$gte:'$since'}})" 2>/dev/null | tail -1)" || n=""
  case "$n" in
    0) done_steps+=("no live call") ;;
    ''|*[!0-9]*) finish NOT_READY "MongoDB not answering (mongod is a system service; check: systemctl status mongod)"; return ;;
    *) finish IN_CALL "$n live Aria call(s); nothing changed"; return ;;
  esac
  if ! curl -fsS -m 3 http://127.0.0.1:8092/api/health >/dev/null; then
    ss -ltn '( sport = :8092 )' | grep -q 8092 && { finish NOT_READY "something listens on :8092 but /api/health fails; not killing it"; return; }
    "$REPO/scripts/restart_dev_backend.sh" || { finish NOT_READY "backend :8092 would not start (see scripts/restart_dev_backend.sh output)"; return; }
    done_steps+=("backend started")
  else done_steps+=("backend healthy"); fi
  systemctl --user start aria-wake-page.service || { finish NOT_READY "aria-wake-page.service would not start"; return; }
  for _ in $(seq 1 20); do curl -fsS -m 2 "http://localhost:$PAGE_PORT/" >/dev/null && break; sleep 0.5; done
  curl -fsS -m 2 "http://localhost:$PAGE_PORT/" >/dev/null || { finish NOT_READY "room page :$PAGE_PORT not answering"; return; }
  done_steps+=("page :$PAGE_PORT up")
  if ! { pactl list short sources | grep -Fq "$src" && pactl list short sinks | grep -Fq "$snk"; }; then
    # No call can be using a device this user cannot see, so reloading this user's audio is safe here.
    systemctl --user restart pulseaudio; sleep 3; done_steps+=("pulseaudio restarted to pick up the eMeet")
    pactl list short sources | grep -Fq "$src" && pactl list short sinks | grep -Fq "$snk" || {
      finish NOT_READY "eMeet not available to $(id -un); another account's audio may hold it (check: sudo fuser -v /dev/snd/*)"; return; }
  fi
  done_steps+=("eMeet source+sink present")
  port_owner="$(ss -ltnp '( sport = :8765 )' | tail -n +2)"
  if [ -n "$port_owner" ] && ! grep -q 'pid=' <<<"$port_owner"; then
    finish NOT_READY ":8765 is held by another account's process (e.g. a second wake listener); stop it first"; return
  fi
  systemctl --user start aria-wake.service || { finish NOT_READY "aria-wake.service would not start"; return; }
  for _ in $(seq 1 30); do ss -ltn '( sport = :8765 )' | grep -q 8765 && break; sleep 0.5; done
  ss -ltn '( sport = :8765 )' | grep -q 8765 || { finish NOT_READY "wake listener did not bind :8765 (ctl.sh logs)"; return; }
  done_steps+=("listener on :8765")
  case "$url" in *wake=1*) ;; *) finish NOT_READY "ARIA_WAKE_PAGE_URL in $CONF/aria-wake.env lacks ?wake=1"; return ;; esac
  systemctl --user start aria-wake-kiosk.service || { finish NOT_READY "aria-wake-kiosk.service would not start"; return; }
  for _ in $(seq 1 60); do clients="$(ss -Htnp state established '( dport = :8765 )' | grep -c chrome || true)"; [ "$clients" -ge 1 ] && break; sleep 0.5; done
  clients="$(ss -Htn state established '( sport = :8765 )' | wc -l)"
  [ "$clients" -eq 1 ] && [ "$(ss -Htnp state established '( dport = :8765 )' | grep -c chrome || true)" -eq 1 ] || {
    finish NOT_READY "expected exactly one wake consumer (this user's kiosk); found $clients"; return; }
  done_steps+=("one wake consumer: kiosk")
  cfg="$(curl -fsS -m 3 "http://localhost:$PAGE_PORT/api/aria-voice/config?kiosk_id=$ARIA_WAKE_KIOSK_ID")" || cfg="{}"
  transport="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("transport") or "unknown")' <<<"$cfg")"
  model="$(sed -n 's/^OPENAI_REALTIME_MODEL=//p' "$REPO/backend/.env" | tail -1)"; model="${model:-gpt-realtime-2.1-mini (code default)}"
  done_steps+=("transport=$transport" "realtime_model=$model")
  [ "$transport" = realtime ] || { finish NOT_READY "room voice transport is $transport, expected realtime"; return; }
  finish READY "Room endpoint ready (transport realtime, model $model)"
}

case "${1:-}" in
  start) start_all ;;
  test-audio-access) audio_access ;;
  install) install_all ;;
  install-voice) install_voice && systemctl --user daemon-reload && systemctl --user enable --now aria-voice.service ;;
  status) systemctl --user --no-pager status aria-wake.service aria-wake-page.service aria-wake-kiosk.service aria-voice.service || true ;;
  logs) shift; journalctl --user -u aria-wake.service -u aria-wake-page.service -u aria-wake-kiosk.service -u aria-voice.service -o cat "${@:--n 100}" ;;
  restart) shift; live_call_guard "${1:-}" && systemctl --user restart aria-wake.service aria-wake-page.service aria-wake-kiosk.service aria-voice.service ;;
  rebuild) shift; live_call_guard "${1:-}" && build_page ;;
  restart-page) shift; live_call_guard "${1:-}" && systemctl --user restart aria-wake-page.service aria-wake-kiosk.service ;;
  uninstall)
    systemctl --user disable --now aria-wake-kiosk.service aria-wake-page.service aria-wake.service aria-voice.service 2>/dev/null || true
    rm -f "$UNITS/aria-wake.service" "$UNITS/aria-wake-page.service" "$UNITS/aria-wake-kiosk.service" "$UNITS/aria-voice.service"
    systemctl --user daemon-reload
    echo "uninstalled (left $CONF and $DIR/.venv in place)" ;;
  *) sed -n 2,9p "$0"; exit 2 ;;
esac
