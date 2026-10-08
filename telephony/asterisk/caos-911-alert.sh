#!/bin/sh
# Rings the front desk to announce a 911 call from a room (Kari's Law
# notification). Run backgrounded from the dialplan; writes an Asterisk call
# file so it never delays or depends on the emergency call.
ROOM="$1"
FRONT_DESK_EXT="$2"
[ -n "$FRONT_DESK_EXT" ] || exit 0
mkdir -p /var/spool/asterisk/tmp
F=$(mktemp /var/spool/asterisk/tmp/caos911.XXXXXX) || exit 0
cat > "$F" <<CALL
Channel: PJSIP/${FRONT_DESK_EXT}
CallerID: "911 ROOM ${ROOM}" <911>
MaxRetries: 3
RetryTime: 15
WaitTime: 40
Context: caos-911-alert
Extension: s
Priority: 1
Setvar: ALERT_ROOM=${ROOM}
CALL
mv "$F" /var/spool/asterisk/outgoing/
