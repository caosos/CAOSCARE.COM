# CAOSCare Connectivity, Response, and Staff Relay Contract v1

## Status

Active build-target contract.

This document captures the immediate CAOSCare build objective: reliable device reconnectability, consistent resident response behavior, and staff relay workflows that show who received a page, who is responding, where they are, and how long service may take.

## Current priority

Server migration is not the current priority while the deployed CAOSCare build is working.

The current priority is:

```text
1. Connectability
2. Response layer consistency
3. Staff login / staff relay workflow
4. Memory system continuation using existing foundations
5. Accessibility and low-friction operation
```

## Connectability principle

CAOSCare devices should reconnect automatically whenever possible.

A registered device should not require repeated manual setup when it returns online, changes network state, restarts, or re-enters range.

The system should recognize known devices and resume their role safely.

## Registered device recognition

When a device signal is detected, CAOSCare should attempt to identify it by available stable identifiers.

Examples:

```text
device token
kiosk id
pendant id
RF fingerprint
wearable id
MAC address where appropriate
room assignment
facility id
previous pairing receipt
hardware receipt
```

Expected behavior:

```text
known device detected
match against registered device record
verify token/signature where applicable
restore device role
sync latest state
log reconnect receipt
surface device as online/active
```

## Reconnect receipt

Every automatic reconnect should create a receipt.

Receipt fields should include:

```text
device_id
facility_id
room_or_zone
subject/resident link if applicable
matched_identifier
match_confidence
auth_status
previous_status
new_status
last_seen_at
reconnected_at
source
notes
```

## Manual setup fallback

Manual setup should exist, but it should be the fallback path, not the normal path.

Manual flow should be needed only when:

```text
new device never registered
identifier conflict
security validation fails
device token revoked
room assignment missing
hardware receipt missing where required
unknown RF fingerprint
```

## Sync behavior

When a device reconnects, CAOSCare should sync:

```text
assigned room/zone
resident/subject link if permitted
latest configuration
pending commands
active alert state
battery/status information
last known location
firmware/app version if available
```

The sync must not blindly trust stale device state over server state.

Server-side assignment and permissions remain authoritative.

## Field-device authentication

CAOSCare already includes a device-token/HMAC direction. This should become a practical production rule.

Target behavior:

```text
field hardware signs requests
backend verifies token/signature
auth failures are logged
soft-enforced mode allowed during pilot
hard-enforced mode required before production deployment
```

## Response layer principle

The resident-facing response layer must be consistent, calming, capability-aware, and memory-aware.

The system should not contradict its own capabilities across sessions or surfaces.

Examples of capability consistency:

```text
If voice is available, say/use voice.
If sung audio is unavailable, do not claim impossible playback.
If text-only mode is active, explain the limitation plainly.
If staff has been paged, state that staff has been paged.
If staff has acknowledged, state that someone is on the way when true.
```

## Resident reassurance loop

When a resident requests help, CAOSCare should:

```text
acknowledge immediately
page staff
start or continue calm voice interaction when available
avoid medical overclaiming
ask simple clarifying questions only when useful
keep the resident oriented
update resident when staff acknowledges or is on the way
log the interaction
```

The system should not go silent after paging staff unless the resident chooses silence or the device/session fails.

## Capability registry requirement

Each runtime surface should expose a small capability registry to the response layer.

Examples:

```text
voice_input_available
voice_output_available
realtime_voice_available
tts_available
staff_page_available
location_available
device_control_available
memory_available
network_status
fallback_mode
```

Responses should be shaped by actual capability state, not model guessing.

## Staff login / staff relay workflow

Staff login must become more than an admin screen.

Staff should receive and respond to pages through CAOSCare.

Required staff relay states:

```text
page_created
page_sent
page_received
acknowledged
accepted_by_staff
en_route
arrived
resolved
cancelled
escalated
```

## Staff response visibility

When a staff member accepts or acknowledges a page, CAOSCare should record:

```text
staff_id
staff_name or role display where permitted
page_id / alert_id
acknowledged_at
accepted_at
en_route_at
arrived_at
resolved_at
current_location/zone if permitted
estimated_time_to_service if available
notes
```

## Resident-facing staff update

When safe and appropriate, the resident-facing kiosk should be able to say:

```text
A staff member has been notified.
Someone has acknowledged your call.
A staff member is on the way.
They should be there shortly.
I will stay with you while you wait.
```

The system must not claim a staff member is on the way unless the staff workflow or location signal supports that claim.

## Behind-the-scenes relay

CAOSCare should relay operational information without increasing radio chatter.

Examples:

```text
staff accepted page
staff ETA estimate
staff current zone where permitted
resident location/room
alert severity
reason if known
whether escalation timer is active
whether supervisor/on-call needs notification
```

## Location-aware response

If staff location is available and permitted, CAOSCare may use it for operational relay.

Examples:

```text
nearest available staff
staff already in same wing
staff en route from another floor
no staff acknowledgment after threshold
```

Location data must be role-scoped and used for operations, not surveillance abuse.

## Escalation connection

The staff relay workflow must connect to escalation rules.

Examples:

```text
no acknowledgment within threshold -> escalate
acknowledged but not arrived within threshold -> escalate or remind
emergency severity -> shorter thresholds
comfort request -> longer thresholds
repeated unresolved page -> supervisor visibility
```

## Memory system relationship

The existing CAOSCare memory system should be built on, not restarted unnecessarily.

Immediate goal:

```text
use existing resident memory foundation
add source-backed operational memory candidates only where useful
preserve resident continuity
avoid manual resident memory management
```

Connectivity, page response, and staff relay events are operational records first. They may generate memory candidates only when patterns or preferences are meaningful and policy permits.

## Accessibility requirement

All connectivity and staff relay flows must work under real facility pressure.

Requirements:

```text
large buttons
clear statuses
few taps
fast acknowledgment
minimal typing
visible offline/reconnect state
plain language
resident-safe reassurance
staff-safe operational detail
```

## Immediate build targets

First implementation targets:

```text
DeviceReconnectReceipt
RegisteredDeviceAutoSync
StaffPageRelayState
StaffPageAcknowledgement
StaffEnRouteStatus
ResidentReassuranceStatusUpdate
CapabilityRegistry
ResponseLayerConsistencyRules
```

## Acceptance tests

A registered device reconnects:

```text
Given a known kiosk/pendant/wearable returns online
When CAOSCare receives a valid signal/request
Then the device is matched, authenticated if possible, synced, marked online, and a reconnect receipt is created
```

A resident presses help:

```text
Given a resident presses help
When the page is created
Then staff are notified, the resident receives immediate reassurance, and the event is logged
```

A staff member acknowledges:

```text
Given a staff member receives the page
When they acknowledge or accept it
Then CAOSCare records who accepted, when, and updates the resident-facing response if appropriate
```

A staff member is on the way:

```text
Given staff marks en route or location confirms movement toward the resident
When the resident asks for status
Then CAOSCare may say someone is on the way with no unsupported claim
```

An alert is not answered:

```text
Given no one acknowledges within the configured threshold
When the threshold expires
Then escalation logic runs and the event remains visible on staff/admin dashboards
```

## Non-negotiable

CAOSCare must make connection and response behavior simple for staff and residents.

The system should automatically reconnect known devices, preserve operational receipts, keep residents informed, and show staff response state without requiring excessive manual setup or radio chatter.
