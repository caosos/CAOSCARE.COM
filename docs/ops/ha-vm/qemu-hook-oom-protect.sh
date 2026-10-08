#!/bin/bash
# PROPOSAL - not installed. Install path: /etc/libvirt/hooks/qemu (root:root, 0755).
# libvirt calls this as: qemu <guest> <operation> <sub-operation> <extra>
# After the guest's qemu process has started ("started begin"), make the OOM
# killer prefer almost anything else over the Home Assistant VM.
# Touches only the domain named below; every other guest and event is ignored.
# If /etc/libvirt/hooks/qemu already exists, merge this block into it instead
# of replacing it.
GUEST_NAME="caoscare-homeassistant"
OOM_SCORE_ADJ="-800"            # -1000 would exempt it entirely; -800 is strong but not absolute

guest="$1"; op="$2"; sub="$3"
[ "$guest" = "$GUEST_NAME" ] || exit 0
[ "$op" = "started" ] && [ "$sub" = "begin" ] || exit 0

pidfile="/run/libvirt/qemu/${guest}.pid"
for _ in 1 2 3 4 5; do
    [ -s "$pidfile" ] && break
    sleep 1
done
[ -s "$pidfile" ] || { logger -t ha-vm-oom-hook "no pidfile $pidfile; oom_score_adj not set"; exit 0; }
pid="$(cat "$pidfile")"
if echo "$OOM_SCORE_ADJ" > "/proc/${pid}/oom_score_adj" 2>/dev/null; then
    logger -t ha-vm-oom-hook "set oom_score_adj=${OOM_SCORE_ADJ} on ${guest} (pid ${pid})"
else
    logger -t ha-vm-oom-hook "could not write /proc/${pid}/oom_score_adj"
fi
exit 0   # never block or fail a guest start because of this hook
