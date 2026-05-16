# CAOSCare Tablet Bridge Setup Runbook v1

## Status

Active field-setup runbook.

This document defines the practical first setup path for CAOSCare tablet connectivity, RF bridge reliability, and registered-device reconnect behavior.

## Immediate objective

Connection reliability comes before response workflow expansion.

The immediate build objective is:

```text
known Lifeline 319.5 MHz pendant signal -> receiver/decoder -> tablet bridge receives decoded event with unique pendant/device ID -> backend matches registered pendant -> resolves assigned resident/room-slot -> alert/page created -> staff can respond
```

## Current known foundation

The hard RF discovery step has already been largely solved.

Known target context:

```text
installed system family: Philips/Lifeline CarePoint-style infrastructure
known pendant class: older Lifeline pendants
known RF target: 319.5 MHz
known behavior: each button press decodes with its own device ID
known FCC ID observed: XO8-319HALO-1
prior building hardware context: Central Alarm Receiver / hallway repeaters / Lifeline head-end infrastructure
```

Do not treat the current pilot as a generic 900 MHz pendant project.

Do not treat frequency alone as the identity key when decoded pendant ID is available.

The Android bridge path is already part of the CAOSCare repo. It is designed to run on a wall-mounted Android tablet with a USB RF receiver/decoder or USB-serial device that outputs one JSON object per line.

Expected receiver line protocol for this pilot:

```json
{"frequency_mhz": 319.5, "decoded_device_id": "DEVICE_ID_FROM_DECODER", "signal_strength": 82, "battery_percent": 87, "event_type": "press"}
```

Minimum acceptable receiver line protocol:

```json
{"frequency_mhz": 319.5, "device_id": "DEVICE_ID_FROM_DECODER", "event_type": "press"}
```

The tablet bridge adds its configured zone and posts the event to:

```text
POST /api/pendants/event
```

## Identity resolution rule

When a resident presses a registered device, CAOSCare should know who the event belongs to because the device is already assigned.

The event itself identifies the hardware. The backend resolves the person or room-slot through registration.

Required resolution chain:

```text
raw activation
-> decoded_device_id / device_id
-> registered pendant/wearable/device record
-> assigned resident_id and/or room_slot
-> room/zone/facility context
-> alert/page/voice workflow
```

For resident-linked devices, the backend must treat the registered device assignment as the source of identity.

The bridge should not need to manually send the resident name. The bridge sends device identity and event context. The backend resolves the assigned resident or room-slot.

## Device assignment model

A registered device may be assigned to:

```text
resident_id
room_slot
room
zone
facility_id
```

Preferred production posture:

```text
resident_id where role/permission requires identity
room_slot where privacy-preserving operations are enough
```

Examples:

```text
decoded_device_id LIFELINE_12345 -> resident_id res_abc / room_slot 214-A
decoded_device_id LIFELINE_99210 -> room_slot 108-B while resident identity remains hidden from kitchen/maintenance views
```

## Hardware position

Android tablets do not normally contain native 319.5 MHz RF receivers.

The tablet is the UI / bridge / network node, not the raw RF receiver unless paired with receiver hardware.

Pilot hardware path:

```text
Lifeline pendant -> 319.5 MHz receiver/decoder -> Android tablet bridge -> CAOSCare backend
```

Current practical hardware expectation:

```text
receiver/decoder already recognizes the button press and outputs a unique device ID
Android tablet receives decoded serial/USB data
USB-C hub / OTG / pass-through power keeps tablet and receiver powered
CAOS Bridge app forwards decoded events to backend
```

Known practical receiver approaches include:

```text
Nooelec / RTL-SDR style receiver with decoder pipeline
purpose-built 319.5 MHz receiver module
security-panel/receiver integration capable of 319.5 MHz
existing Lifeline/CarePoint infrastructure output if accessible
```

The cleanest pilot path is whichever receiver can reliably produce decoded JSON events for known Lifeline pendant presses.

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
4. Connect USB-C hub / OTG / pass-through power as needed
5. Connect 319.5 MHz receiver/decoder
6. Grant USB permission for receiver if Android prompts
7. Configure backend URL
8. Configure tablet zone
9. Enter device token if available
10. Start bridge foreground service
11. Press known Lifeline pendant
12. Verify decoded device ID appears
13. Verify backend resolves assigned resident/room-slot
14. Verify backend alert and staff dashboard event
```

## Tablet setup checklist

```text
Tablet charged / powered
Wi-Fi connected
USB-C hub with pass-through power if needed
USB-OTG/host support working
319.5 MHz receiver/decoder connected
Bridge app installed
USB permission granted
Backend URL configured
Zone configured
Device token configured if using auth
Bridge service running
Persistent notification visible
Decoded device ID visible in bridge logs or event payload
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
device_type = rf_bridge_tablet_319_5
backend_url
device_token_id optional
last_seen_at
status
notes
```

The system should recognize a previously registered tablet/receiver when it comes back online.

## Pendant registration model

Each pendant should be registered before live use.

Minimum registration fields:

```text
pendant_device_id
pendant_id
frequency_mhz = 319.5
decoded_device_id
resident_id optional
room_slot optional
battery_percent optional
signal_strength optional
status
last_seen_at
notes
```

Primary match key for this pilot:

```text
decoded_device_id
```

Secondary/supporting context:

```text
frequency_mhz = 319.5
signal_strength
zone
receiver/tablet device_id
```

If privacy-preserving operation is required, room/slot can be used before resident name display.

## Connection test procedure

For each known Lifeline pendant:

```text
1. Confirm decoded_device_id exists in Admin -> Pendants
2. Confirm decoded_device_id is assigned to correct resident_id and/or room_slot
3. Confirm frequency_mhz is 319.5
4. Confirm tablet bridge zone is correct
5. Start bridge
6. Press pendant once
7. Confirm receiver emits JSON with decoded_device_id/device_id
8. Confirm tablet posts event
9. Confirm backend matches pendant by decoded_device_id
10. Confirm backend resolves correct resident/room-slot
11. Confirm backend updates last_seen_at
12. Confirm alert appears in staff dashboard
13. Confirm room/zone/source are correct
14. Resolve test alert with note: connectivity test
```

## Unknown signal behavior

If a signal is detected but no pendant/device match exists, CAOSCare should log it as unknown instead of losing it.

Expected behavior:

```text
unknown 319.5 MHz signal detected
store frequency/signal/event/zone/timestamp/raw decoded device ID
surface in admin unknown pings view
allow staff/admin to register it later
```

## Reconnect behavior target

When a registered tablet, receiver, or pendant comes back online, CAOSCare should:

```text
match known decoded_device_id
confirm supporting 319.5 MHz context
resolve assigned resident/room-slot
update last_seen_at
update battery/signal telemetry
restore active/online status
create reconnect/sync receipt
avoid manual re-registration
```

Manual setup should be required only for:

```text
new device
unknown decoded_device_id
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

Connectivity is not proven merely because the receiver detects 319.5 MHz RF.

Connectivity is proven only when:

```text
pendant press creates backend alert
staff dashboard receives it
staff can acknowledge it
alert has correct resident/room-slot/zone/source according to permission level
alert can be resolved
receipt remains visible
```

## Do not overbuild before this works

Do not prioritize server migration, advanced memory automation, or full response-layer polish before the bridge path is reliable.

The first live proof is simple:

```text
press Lifeline pendant -> receiver decodes 319.5 MHz event + device ID -> tablet posts it -> backend resolves registered resident/room-slot -> staff sees it
```

## Next implementation targets

```text
Add decoded_device_id/device_id support to PendantEventInput
Add decoded_device_id to Pendant model/registration
Match pendant events by decoded_device_id first
Resolve resident_id/room_slot from registered device assignment
Keep frequency_mhz as supporting context
RegisteredDevice table/model if not already complete
DeviceReconnectReceipt
Bridge heartbeat endpoint
Bridge status dashboard
Unknown decoded_device_id registration flow
Tablet zone verification
Soft/hard device-auth mode indicator
```

## Non-negotiable

CAOSCare field connectivity must be simple enough for real staff and real tablets.

Known devices should reconnect automatically, known Lifeline 319.5 MHz decoded device IDs should map cleanly to the assigned resident or room-slot, and Google account setup must not block pilot proof unless the tablet's ownership policy makes it unavoidable.
