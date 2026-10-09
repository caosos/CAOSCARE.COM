#!/usr/bin/env bash
# Control script for the EliteDesk home wake endpoint (systemd --user).
#   ctl.sh test-audio-access   can this user see the eMeet? (prints the fix if not)
#   ctl.sh install             venv + units + env file, enable and start the services
#   ctl.sh rebuild [--force]   build the frontend into ~/.cache/aria-wake/build and swap it in
#   ctl.sh restart-page [--force]   restart the static server + headless page
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
  (cd "$REPO/frontend" && BUILD_PATH="$new" REACT_APP_BACKEND_URL="http://localhost:$PAGE_PORT" yarn build)
  [ -f "$new/index.html" ] || { echo "build failed: no index.html" >&2; exit 1; }
  rm -rf "$CACHE/build.prev"; [ -d "$out" ] && mv "$out" "$CACHE/build.prev"
  mv "$new" "$out"   # server reads files per request: no restart needed
  echo "built $(git -C "$REPO" rev-parse --short HEAD) -> $out"
}

need() { command -v "$1" >/dev/null || { echo "missing: $1 ($2)" >&2; exit 1; }; }

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
  systemctl --user daemon-reload
  systemctl --user enable --now aria-wake.service aria-wake-page.service aria-wake-kiosk.service
  echo "installed. Edit $CONF/aria-wake.env (PULSE_SOURCE/PULSE_SINK/ARIA_WAKE_SOURCE) and 'ctl.sh restart'."
  echo "To start at boot without a login:  loginctl enable-linger $(id -un)"
}

case "${1:-}" in
  test-audio-access) audio_access ;;
  install) install_all ;;
  status) systemctl --user --no-pager status aria-wake.service aria-wake-page.service aria-wake-kiosk.service || true ;;
  logs) shift; journalctl --user -u aria-wake.service -u aria-wake-page.service -u aria-wake-kiosk.service -o cat "${@:--n 100}" ;;
  restart) shift; live_call_guard "${1:-}" && systemctl --user restart aria-wake.service aria-wake-page.service aria-wake-kiosk.service ;;
  rebuild) shift; live_call_guard "${1:-}" && build_page ;;
  restart-page) shift; live_call_guard "${1:-}" && systemctl --user restart aria-wake-page.service aria-wake-kiosk.service ;;
  uninstall)
    systemctl --user disable --now aria-wake-kiosk.service aria-wake-page.service aria-wake.service 2>/dev/null || true
    rm -f "$UNITS/aria-wake.service" "$UNITS/aria-wake-page.service" "$UNITS/aria-wake-kiosk.service"; systemctl --user daemon-reload
    echo "uninstalled (left $CONF and $DIR/.venv in place)" ;;
  *) sed -n 2,6p "$0"; exit 2 ;;
esac
