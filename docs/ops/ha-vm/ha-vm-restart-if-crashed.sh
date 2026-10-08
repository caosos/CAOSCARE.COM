#!/bin/bash
# PROPOSAL - not installed. Install path: /usr/local/sbin/ha-vm-restart-if-crashed.sh (root, 0755).
# Run once a minute by ha-vm-restart-if-crashed.timer.
# Starts the Home Assistant VM ONLY when libvirt reports "shut off (crashed)".
# A deliberate shutdown ("shut off (shutdown)" / "(destroyed)") and any other
# state are left alone. Guards: not before 5 minutes since the last attempt,
# not while the host is short of memory (a restart into the same pressure would
# just be killed again), and never concurrent runs.
set -u
DOMAIN="caoscare-homeassistant"
URI="qemu:///system"
STATE_FILE="/var/lib/ha-vm-restart/last_attempt"
MIN_INTERVAL=300                # seconds between start attempts
MIN_AVAILABLE_KB=$((5 * 1024 * 1024))   # 5 GiB MemAvailable (VM has 4 GiB)

log() { logger -t ha-vm-restart "$*"; }

mkdir -p "$(dirname "$STATE_FILE")"
exec 9>"$(dirname "$STATE_FILE")/lock"
flock -n 9 || exit 0

state="$(virsh -c "$URI" domstate --reason "$DOMAIN" 2>/dev/null)" || { log "cannot read state of $DOMAIN"; exit 0; }
[ "$state" = "shut off (crashed)" ] || exit 0

now="$(date +%s)"
last="$(cat "$STATE_FILE" 2>/dev/null || echo 0)"
if [ $((now - last)) -lt "$MIN_INTERVAL" ]; then
    exit 0
fi

avail="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
if [ "${avail:-0}" -lt "$MIN_AVAILABLE_KB" ]; then
    log "$DOMAIN crashed but MemAvailable=${avail}kB < ${MIN_AVAILABLE_KB}kB; not starting yet"
    exit 0
fi

echo "$now" > "$STATE_FILE"
if virsh -c "$URI" start "$DOMAIN" >/dev/null 2>&1; then
    log "$DOMAIN was 'shut off (crashed)'; started it"
else
    log "$DOMAIN was 'shut off (crashed)'; virsh start FAILED"
fi
exit 0
