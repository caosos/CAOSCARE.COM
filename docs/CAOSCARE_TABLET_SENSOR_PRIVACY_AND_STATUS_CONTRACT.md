# CAOSCare Tablet Sensor Privacy and Resident Status Contract v1

## Status

Active product-scope contract.

This document defines how CAOSCare may use tablet cameras, microphones, and other onboard sensors for resident status confirmation, staff support, and operational safety.

## Core capability

CAOSCare tablets may provide more than touch input and RF bridge connectivity.

Wall-mounted or room tablets often include:

```text
camera
microphone
speaker
touchscreen
network connection
local storage
motion/ambient sensors where available
```

These sensors can support resident status awareness, staff response, voice interaction, and visual confirmation.

## Core boundary

Camera and microphone access must be treated as sensitive.

CAOSCare must never become uncontrolled surveillance.

Allowed posture:

```text
resident safety support
status confirmation
human-supervised response aid
permission-scoped sensor use
receipt-backed access
minimal necessary capture
```

Disallowed posture:

```text
always-on voyeuristic monitoring
hidden recording
unrestricted staff viewing
clinical diagnosis by camera
punitive staff surveillance
unlogged camera/microphone access
unbounded retention of private audio/video
```

## Visual status confirmation

CAOSCare may use tablet camera input to help confirm a resident's immediate visible status during a help request or safety event.

Examples of allowed uses:

```text
resident is visible / not visible
resident appears seated / standing / lying down
resident appears to be on the floor
resident is waving / signaling
room appears dark or obstructed
camera is covered or unavailable
staff can visually confirm before entering when permitted
```

The system must not overstate visual interpretation.

Allowed language:

```text
Camera view suggests the resident may be on the floor. Staff review required.
```

Disallowed language:

```text
The resident has definitely fallen and has a hip fracture.
```

## Audio status confirmation

Microphones may support:

```text
voice conversation
help request capture
resident response confirmation
sound-level/keyword cue where permitted
hands-free interaction after pendant press
```

Microphone use must be visible, permission-scoped, and logged where required.

## Event-triggered sensor activation

Preferred early implementation is event-triggered, not continuous surveillance.

Allowed triggers:

```text
resident presses help button
pendant press / fall event
wearable emergency event
staff opens room status check with permission
scheduled wellness check where authorized
resident initiates voice session
```

Default pilot rule:

```text
activate camera/mic only during active help/session/check events
```

## Resident-facing transparency

When camera or microphone is active, the tablet should provide clear indication.

Examples:

```text
camera active indicator
microphone active indicator
spoken or visible notice where appropriate
large stop / privacy control where appropriate
```

## Staff-facing visual confirmation

Staff views should show only what is needed for the active workflow.

Examples:

```text
live snapshot/status during active alert
camera unavailable / blocked status
last verified visual status timestamp
staff-confirmed status note
```

Staff should not receive unrestricted browsing access to resident cameras.

## Metrics and derived signals

Tablet sensors may support non-diagnostic operational metrics.

Possible metrics:

```text
response confirmation
resident present / not visible
motion/activity cue where available
voice interaction duration
call duration
camera blocked/unavailable frequency
room check completion evidence
staff arrival confirmation where permitted
```

Care-sensitive derived signals must be labeled as observations or candidates, not facts, unless verified by authorized humans.

## Privacy and retention

Default retention should minimize raw audio/video storage.

Preferred pattern:

```text
process live signal
store structured receipt/status
store snapshot only when needed for incident review and permitted
avoid long-term raw video/audio retention by default
```

If raw media is stored, records must include:

```text
why it was captured
who accessed it
retention period
permission/legal basis
associated alert/event id
```

## Integration with alerts

Sensor confirmation should attach to alert/event records.

Possible fields:

```text
visual_status
visual_status_confidence
visual_checked_at
visual_checked_by
camera_available
mic_available
sensor_receipt_id
media_ref optional
human_verified_status
```

## Integration with response layer

Resident-facing AI may use sensor state only in bounded ways.

Allowed:

```text
I can hear you.
I can see that the camera view is blocked, but staff has been notified.
I am keeping the call open while help is on the way.
```

Restricted:

```text
unsupported medical conclusions
unsupported certainty about injury
pretending to see/hear if the sensor is unavailable
```

## Integration with memory

Sensor events are operational records first.

They may produce memory candidates only when appropriate and policy permits.

Examples:

```text
resident prefers audio-only calls -> low-risk preference memory
repeated camera-blocked during alerts -> device/room operations issue
repeated visible distress cue -> staff-review candidate, not automatic fact
```

All memory extraction must follow the CAOSCare Memory Automation Contract.

## Required future components

```text
TabletSensorCapability
SensorActivationReceipt
VisualStatusCheck
AudioStatusCheck
CameraAvailabilityState
MicAvailabilityState
MediaRetentionPolicy
SensorAccessAudit
ResidentPrivacyPreference
```

## Non-negotiable

Camera and microphone capability is valuable, but only if CAOSCare remains privacy-preserving, permission-scoped, receipt-backed, and human-supervised.

Visual confirmation may support safety. It must not become unbounded surveillance or unsupported clinical judgment.
