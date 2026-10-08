#!/usr/bin/env bash
# Control script for the EliteDesk home wake endpoint (systemd --user).
#   ctl.sh test-audio-access   can this user see the eMeet? (prints the fix if not)
#   ctl.sh install             venv + units + env file, enable and start both services
#   ctl.sh status | logs [-f] | restart | uninstall
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
  mkdir -p "$UNITS" "$CONF"
  [ -f "$CONF/aria-wake.env" ] || cp "$DIR/systemd/aria-wake.env.example" "$CONF/aria-wake.env"
  sed "s#@DIR@#$DIR#g" "$DIR/systemd/aria-wake.service.in" > "$UNITS/aria-wake.service"
  sed "s#@CHROME@#$CHROME#g" "$DIR/systemd/aria-wake-kiosk.service.in" > "$UNITS/aria-wake-kiosk.service"
  systemctl --user daemon-reload
  systemctl --user enable --now aria-wake.service aria-wake-kiosk.service
  echo "installed. Edit $CONF/aria-wake.env (PULSE_SOURCE/PULSE_SINK/ARIA_WAKE_SOURCE) and 'ctl.sh restart'."
  echo "To start at boot without a login:  loginctl enable-linger $(id -un)"
}

case "${1:-}" in
  test-audio-access) audio_access ;;
  install) install_all ;;
  status) systemctl --user --no-pager status aria-wake.service aria-wake-kiosk.service || true ;;
  logs) shift; journalctl --user -u aria-wake.service -u aria-wake-kiosk.service -o cat "${@:--n 100}" ;;
  restart) systemctl --user restart aria-wake.service aria-wake-kiosk.service ;;
  uninstall)
    systemctl --user disable --now aria-wake-kiosk.service aria-wake.service 2>/dev/null || true
    rm -f "$UNITS/aria-wake.service" "$UNITS/aria-wake-kiosk.service"; systemctl --user daemon-reload
    echo "uninstalled (left $CONF and $DIR/.venv in place)" ;;
  *) sed -n 2,6p "$0"; exit 2 ;;
esac
