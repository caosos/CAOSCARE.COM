# CAOSCare Edge + Facility Hardware Standard

_Status: implementation / deployment contract_

_Branch: `feature/runtime-agent-lanes-20260830`_

## Purpose

This document defines the hardware and remote-testing architecture for a CAOSCare facility. It is not a shopping note. Coding agents, deployment work, voice testing, simulation, and commissioning must treat these rules as part of the product architecture.

The goal is a repeatable building deployment in which every room has a known-good local edge computer, the facility has a stronger local server, remote administration is safe, and audio is always tested on the machine physically connected to the room hardware.

## Core deployment model

CAOSCare is a **local-facility server + intelligent room edge nodes** architecture.

```text
Cloud AI/services (when needed)
        ^
        |
Facility network
        |
Grand Central facility server
        |
-------------------------------------------------
| Room 101 Edge | Room 102 Edge | ... | Room 180 Edge |
| eMeet/audio   | eMeet/audio   |     | eMeet/audio   |
| local devices | local devices |     | local devices |
-------------------------------------------------
```

The room node is an edge appliance. It is not expected to run the entire facility backend, Grand Central database, full simulation engine, or every operational agent.

The facility server is the shared building-side brain for APIs, shared state, Grand Central orchestration, database/event processing, schedules, transportation, calls, communications, logs, device coordination, and other facility-wide services.

## Hardware standardization principle

**Once a hardware family proves reliable, standardize on it.**

Current preferred platform: **HP EliteDesk Mini-class systems or a directly comparable enterprise mini PC.**

The exact SKU does not have to be identical forever, but the fleet should stay inside a narrow, proven hardware family whenever practical.

Reasons:

- same Linux image and deployment procedure
- same BIOS/firmware practices
- predictable USB/audio behavior
- predictable network behavior
- common power supplies and replacement parts where possible
- repeatable mounting/cabling
- consistent remote-management procedures
- easier spares inventory
- fewer one-off driver and hardware failures
- known thermals and known failure modes
- simpler support across an 80-apartment facility

Do not save a small amount per room by creating a mixed fleet that costs more in debugging, support, imaging, and replacement labor.

## Room edge node target

Each apartment should have a dedicated CAOSCare edge computer in the EliteDesk Mini / comparable class.

### Baseline

```text
RAM:       8 GB minimum
Preferred: 16 GB when the price difference is reasonable
Storage:   256 GB minimum; 512 GB preferred
Network:   reliable wired Ethernet preferred; Wi-Fi available as secondary where appropriate
OS:        standardized Linux deployment
Form:      enterprise mini PC / small-form-factor edge appliance
```

### Room node responsibilities

The room node should handle the things that must be close to the resident and the physical hardware:

- resident Care app UI / kiosk display
- browser or local client runtime
- microphone capture
- speaker playback
- WebRTC audio session
- acoustic echo cancellation path
- VAD / local browser audio constraints
- eMeet microphone/speaker integration
- local room-device interface(s)
- local Edge Agent / commissioning service
- local health reporting
- local fail-safe behavior that should survive a temporary facility-server outage where practical
- future local speech/sensor/vision capability when justified

The room node should **not** become a duplicate facility server.

## Facility server target

For an approximately 80-apartment building, the starting CAOSCare facility-server target is:

```text
RAM:       32 GB baseline
Storage:   1 TB NVMe baseline
CPU:       modern enterprise mini-PC CPU with adequate multi-core headroom
Network:   wired Ethernet
Platform:  EliteDesk-class or comparable proven enterprise hardware
Upgrade:   64 GB capability preferred where economically practical
```

A 16 GB / 500 GB EliteDesk is excellent for development, a pilot, or smaller deployments, but **must not be assumed sufficient for an 80-apartment production facility without measured load testing**.

The 32 GB / 1 TB target is a deployment baseline, not a mathematical guarantee. Before final production sizing, test real concurrent workloads for:

- resident sessions
- API traffic
- Grand Central events
- database load
- schedules/appointments
- transportation
- Nursing Calls
- Care Aid Calls
- Maintenance Calls
- Front Desk communications
- room/device health telemetry
- Home Assistant / device coordination if hosted here
- logs and receipts
- admin/staff browser usage
- background simulation/test workloads when enabled

### Redundancy direction

A second comparable facility server is preferred as the system matures so one hardware failure does not take the whole building-side brain offline.

Possible use:

- warm standby / failover
- backup and recovery target
- secondary services
- Home Assistant / device-service separation
- simulation/test workloads
- staged upgrades

Do not make HA/failover claims until the actual failover path is implemented and tested.

## Storage rule

500 GB can be enough for structured records and normal text logs, but storage requirements change dramatically if CAOSCare retains large amounts of:

- audio recordings
- video
- screenshots
- diagnostic captures
- high-frequency telemetry
- long-term traces

Large media retention must have an explicit retention and storage policy. Do not silently let room audio/video turn the facility server into an unbounded archive.

## Audio architecture rule — test at the edge

**Audio is tested on the machine physically connected to the room microphone and speaker.**

SSH is a management path. It is not the resident audio path.

Remote administration can start a test, retrieve results, restart services, inspect logs, or deploy code, but the actual microphone capture, speaker playback, WebRTC processing, and acoustic echo cancellation test must execute on the room node using the real room hardware.

### Why this matters

Acoustic echo cancellation and full-duplex voice depend on the real local signal path:

```text
room microphone
    -> local browser/client
    -> WebRTC/audio processing
    -> local speaker
    -> room acoustics
    -> microphone
```

If the microphone lives on one computer while playback or the active session is effectively being forwarded/virtualized through another machine, the topology is different. That can change:

- latency
- buffering
- device clocks
- browser audio constraints
- microphone/speaker pairing
- echo-reference quality
- AEC behavior
- VAD behavior
- interruption/barge-in behavior
- perceived conversational timing

Therefore:

> **Audio is tested at the edge. Servers are tested remotely. Never confuse the two.**

A voice result obtained through a different physical/audio topology is not accepted as proof of room performance.

## eMeet rule

For the current prototype/deployment direction, the eMeet speakerphone is the known room audio reference hardware.

When testing a room:

- the intended eMeet input should be the active microphone
- the intended eMeet output should be the active playback device
- the local client should verify both endpoints
- room audio diagnostics should record the actual device identifiers in use
- switching to another microphone or speaker must be visible in diagnostics

Do not claim an echo-cancellation regression or improvement without first proving the physical/local audio path is the same between tests.

## Remote Room Commissioning + Test Protocol

Every room must be remotely manageable while still testing its hardware locally.

The room machine should run a lightweight **CAOSCare Edge Agent** responsible for provisioning, diagnostics, health reporting, and controlled remote actions.

### 1. Provision

Install the standard CAOSCare room image:

- standardized Linux
- required browser/client runtime
- Edge Agent
- CAOSCare auto-start
- approved remote-management credentials/keys
- expected audio/device packages
- logging and health service

### 2. Enroll

Enroll the node with the facility server using a controlled one-time process.

Required binding:

```text
facility_id
room
kiosk / room-node identity
resident assignment when applicable
hardware/node identity
```

Room identity must never be inferred loosely from whatever machine happens to connect.

### 3. Inventory local hardware

The Edge Agent reports the real hardware visible on that room node:

- microphone devices
- speaker/output devices
- eMeet presence
- USB interfaces
- display
- Ethernet/Wi-Fi state
- room-control interfaces
- smart-device adapters
- other supported hardware

### 4. Run local audio-path diagnostics

The facility server may request the test, but the room node executes it.

At minimum verify:

- selected microphone
- selected speaker/output
- sample/device state where available
- microphone capture works
- speaker playback works
- round-trip/local latency observations where practical
- network latency/jitter/packet-loss observations relevant to Realtime/WebRTC
- local WebRTC session establishment
- echo/AEC diagnostic evidence available from the chosen stack
- VAD/turn registration
- reconnect behavior

### 5. Real conversation acceptance

Put the room into commissioning mode and talk through the actual room eMeet and Care client.

Capture enough evidence to compare sessions:

- session start/end
- input/output device identity
- network observations
- transcription timing
- model-response timing
- playback timing
- interruption/barge-in behavior
- missed user turns
- echo-like turns
- reconnects/errors

This is the authoritative voice acceptance environment.

### 6. Test local room controls

Verify only the capabilities that actually exist in the room, for example:

- light power/brightness
- TV power/input/volume
- thermostat/AC controls
- smart plugs
- blinds
- other supported devices

A configured device is not automatically a verified device. Record the distinction.

### 7. Resident/room isolation test

Before commissioning, prove that the room node can only retrieve/control the intended room/resident context.

At minimum test:

- resident identity/profile
- My Day / appointments/sign-ups
- requests/calls
- room devices
- transportation status
- voice context

Room A must not see or control Room B state.

### 8. Commission

Only after the required tests pass should the node be marked:

```text
COMMISSIONED
```

Commissioning should create a durable receipt with hardware identity, room binding, software version, tests performed, results, and timestamp.

## Remote Edge Agent operations

The Grand Central/facility administration layer should eventually be able to request controlled operations such as:

```text
run room health check
run audio diagnostics
list microphone devices
list playback devices
verify eMeet input/output
measure network health
restart Care client
restart Edge Agent
pull relevant logs
verify room-device connectivity
run room isolation test
apply approved software update
reboot room endpoint
```

The command travels remotely; the hardware interaction executes locally.

All remote mutations/actions should create receipts.

## Room cost target

Current rough target for a basic room deployment:

```text
EliteDesk/comparable room node:  about $100-$150
Known eMeet audio hardware:       about $100
Room interface/control hardware:  roughly ~$50 class, exact model/price to verify
------------------------------------------------------
Basic room compute/audio/control: roughly $250-$300 target
```

This is a planning target, not a fixed BOM quote.

Smart lights, thermostat interfaces, TV/IR bridges, specialty sensors, displays, mounting, cabling, networking, and other room-specific devices are additional where required.

The exact currently discussed USB/radio interface (referred to verbally as the Nooelec/"Nolec" device) must be verified by exact model before it becomes a locked BOM item.

## Spares policy

Keep several pre-imaged room nodes from the same approved hardware family available as spares.

The desired replacement flow is:

```text
failed room node
-> replace with pre-imaged spare
-> enroll/bind spare to room
-> restore room configuration
-> run commissioning subset
-> return resident service quickly
```

Do not make apartment service depend on repairing a motherboard in place.

Where practical, keep spare:

- mini PCs
- power supplies
- eMeet units
- USB/interface hardware
- network cables/adapters
- display adapters used by the standard deployment

## Fleet-management principle

The economic advantage is not merely buying inexpensive used computers. It is **repeatability**.

An 80-room deployment should become progressively easier to operate because every room follows the same image, same Edge Agent contract, same diagnostics, same commissioning checklist, and same known hardware family.

The standard should change only when evidence justifies the change.

## Relationship to Grand Central

Grand Central should know the health and commissioning state of every room node, but it does not own the physical audio loop.

Expected relationship:

```text
Grand Central
  -> asks Room 219 Edge Agent to run audio diagnostics
Room 219
  -> executes locally using Room 219 hardware
  -> returns structured result + receipt
Grand Central
  -> records result / surfaces status
```

The same pattern applies to local device diagnostics and room health.

## Build implications for parallel agents

Any coding agent working on room voice, resident UI, room hardware, remote diagnostics, or device control must read this document before implementation.

Agents must not:

- assume SSH-forwarded/remote audio proves room audio behavior
- create a second room identity system
- create hardware state disconnected from the authoritative room/kiosk/device records
- report configured hardware as verified without a real test
- hard-code one-off hardware assumptions that prevent fleet standardization
- bypass commissioning/isolation receipts

## Deployment acceptance gate

A room deployment is not accepted because the webpage loads.

A room is accepted when:

1. approved hardware is installed
2. room/node identity is correct
3. eMeet/local audio endpoints are verified
4. real local voice conversation passes acceptance
5. network health is acceptable
6. installed room controls are verified
7. resident/room isolation passes
8. health reporting reaches the facility server
9. remote-management commands execute locally and return receipts
10. the node is marked COMMISSIONED

A facility is not accepted for 80-room production merely because one development EliteDesk works. Facility-server capacity, concurrency, recovery, and failure behavior must be measured under representative load.

## Non-negotiable summary

```text
Use proven EliteDesk-class hardware repeatedly.
Room nodes are intelligent edge appliances.
8 GB is the room minimum; 16 GB is preferred when practical.
32 GB RAM + 1 TB NVMe is the current 80-room facility-server baseline target.
Keep the fleet standardized.
Keep spares pre-imaged.
SSH manages machines; it does not define the resident audio path.
Audio testing runs locally on the room node with the real microphone and speaker.
Remote commands trigger local hardware tests and return receipts.
Commission every room before calling it ready.
Load-test the facility server before calling it sufficient for 80 apartments.
```
