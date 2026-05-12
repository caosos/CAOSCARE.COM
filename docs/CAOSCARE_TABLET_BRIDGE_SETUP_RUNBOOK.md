# CAOSCare Tablet Bridge Setup Runbook v1

## Status

Active field-setup runbook.

This document defines the practical first setup path for CAOSCare tablet connectivity, RF bridge reliability, and registered-device reconnect behavior.

## Immediate objective

Connection reliability comes before response workflow expansion.

The immediate build objective is:

```text
known RF frequency -> registered pendant -> tablet bridge receives event -> backend matches device -> alert/page created -> staff can respond
```

## Current known foundation

The hard RF discovery step has already been largely solved: target pendant frequencies have been isolated.

The Android bridge path is already part of the CAOSCare repo. It is designed to run on a wall-mounted Android tablet with a USB RF receiver or USB-serial device that outputs one JSON object per line.

Expected receiver line protocol:

```json
{"frequency_mhz": 916.1250, "signal_strength": 82, "battery_percent": 87, "event_type": "press"}
```

The tablet bridge adds its configured zone and posts the event to:

```text
POST /api/pendants/event
```

## Google account / registration position

Google account registration should not be a blocker for pilot connectivity.

For early field testing, CAOSCare tablets should be treated as dedicated bridge/kiosk devices. The bridge APK can be installed directly where allowed by device policy.

Google Play / Google account registration may be useful later for managed deployment, but it should not be required for the first connectivity proof.

## Preferred pilot setup path

Preferred early setup:

```text
1. Prepare Android tablet
2. Enable Wi-Fi
3. Install CAOS Bridge APK directly
4. Grant USB permission for receiver
5. Configure backend URL
6. Configure tablet zone
7. Enter device token if available
8. Start bridge foreground service
9. Press known pendant
10. Verify backend alert and staff dashboard event
```

## Tablet setup checklist

```text
Tablet charged / powered
Wi-Fi connected
Screen timeout adjusted for kiosk/bridge role
USB-OTG adapter available if needed
RF receiver connected
Bridge app installed
USB permission granted
Backend URL configured
Zone configured
Device token configured if using auth
Bridge service running
Persistent notification visible
```

## APK installation options

Allowed setup options for pilot devices:

```text
ADB install from development machine
Direct APK download from trusted internal link
USB transfer + install from Files app
MDM / managed Play later when production-ready
```

If Google account setup blocks progress, use direct APK install or ADB for pilot testing.

Do not let Google account enrollment become the critical path for proving RF/device connectivity.

## Android settings to check

Depending on tablet model and Android version, field setup may require:

```text
Install unknown apps permission for browser/files app
Developer options enabled for ADB install
USB permission accepted when receiver is plugged in
Battery optimization disabled for CAOS Bridge
Foreground service notification allowed
Wi-Fi sleep disabled or minimized
Auto-start/background restrictions disabled where vendor UI requires it
Screen pinning or kiosk mode later for production
```

## Device registration model

Each field tablet/receiver should become a registered CAOSCare device.

Minimum registration fields:

```text
device_id
device_label
facility_id
zone
room_or_area optional
device_type = rf_bridge_tablet
backend_url
device_token_id optional
last_seen_at
status
notes
```

The system should recognize a previously registered tablet/receiver when it comes back online.

## Pendant registration model

Each pendant/frequency should be registered before live use.

Minimum registration fields:

```text
pendant_device_id
pendant_id
frequency_mhz
resident_id optional
room_slot optional
battery_percent optional
signal_strength optional
status
last_seen_at
notes
```

If privacy-preserving operation is required, room/slot can be used before resident name display.

## Connection test procedure

For each known frequency:

```text
1. Confirm pendant/frequency exists in Admin -> Pendants
2. Confirm tablet bridge zone is correct
3. Start bridge
4. Press pendant once
5. Confirm receiver emits JSON
6. Confirm tablet posts event
7. Confirm backend updates last_seen_at
8. Confirm alert appears in staff dashboard
9. Confirm room/zone is correct
10. Resolve test alert with note: connectivity test
```

## Unknown signal behavior

If a signal is detected but no pendant is registered at that frequency, CAOSCare should log it as unknown instead of losing it.

Expected behavior:

```text
unknown frequency detected
store frequency/signal/event/zone/timestamp
surface in admin unknown pings view
allow staff/admin to register it later
```

## Reconnect behavior target

When a registered tablet or pendant comes back online, CAOSCare should:

```text
match known device or frequency
update last_seen_at
update battery/signal telemetry
restore active/online status
create reconnect/sync receipt
avoid manual re-registration
```

Manual setup should be required only for:

```text
new device
unknown frequency
identifier conflict
revoked token
failed auth
missing zone/room assignment
```

## Device token / HMAC position

Current backend supports device-token/HMAC direction.

Pilot mode may allow soft enforcement while testing hardware.

Production mode should require signed requests.

Target progression:

```text
Pilot: DEVICE_AUTH_REQUIRED=false allowed for setup speed
Hardened pilot: tokens issued and used, soft fallback still visible
Production: DEVICE_AUTH_REQUIRED=true, unsigned requests rejected
```

## Staff dashboard acceptance proof

Connectivity is not proven merely because the tablet receives RF.

Connectivity is proven only when:

```text
pendant press creates backend alert
staff dashboard receives it
staff can acknowledge it
alert has correct room/zone/source
alert can be resolved
receipt remains visible
```

## Do not overbuild before this works

Do not prioritize server migration, advanced memory automation, or full response-layer polish before the bridge path is reliable.

The first live proof is simple:

```text
press pendant -> tablet sees it -> backend matches it -> staff sees it
```

## Next implementation targets

```text
RegisteredDevice table/model if not already complete
DeviceReconnectReceipt
Bridge heartbeat endpoint
Bridge status dashboard
Unknown signal registration flow
Tablet zone verification
Soft/hard device-auth mode indicator
```

## Non-negotiable

CAOSCare field connectivity must be simple enough for real staff and real tablets.

Known devices should reconnect automatically, known frequencies should map cleanly, and Google account setup must not block pilot proof unless the tablet's ownership policy makes it unavoidable.
