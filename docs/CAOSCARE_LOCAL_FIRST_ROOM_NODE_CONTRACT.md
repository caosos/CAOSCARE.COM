# CAOSCare Local-First Room-Node Architecture Contract v1

## Status

Active architecture contract.

This document defines the local-first CAOSCare room-node architecture: a self-sufficient care endpoint that keeps working when power, internet, the router, the cloud, or a controlled device is degraded or unavailable.

It is an architecture contract only. It does not redefine product scope, care workflows, or safety posture, and it does not claim any of the described topology is deployed or runtime-verified. Capability status follows the verification standard in `docs/REPO_MAP.md`.

CAOSCare remains assistive, advisory, human-supervised, receipt-backed. Nothing in this architecture grants clinical authority, autonomous medical judgment, or autonomous emergency dispatch.

## Core architecture principle

```text
The CAOSCare room node must remain useful to residents and staff without internet.
Internet is an enhancement, not a dependency.
```

A room node is a single physical location's CAOSCare endpoint (for example, a resident room or a common area). It runs the local response layer, stores its own state, and continues operating during outages. Cloud services extend the node; they do not gate its core care function.

## Laptop-first room node

The first room-node prototype runs on a standard x86 laptop.

```text
room node = laptop + local services + local store + attached devices
```

The laptop hosts:

```text
the CAOSCare backend (FastAPI)
the room-node state store (local MongoDB)
the response layer / capability registry
attached device bridges (mic/speaker, SDR/pendant receiver, controllable devices)
local logs and a queued-event buffer
an optional local AI tier when hardware permits
```

### Why an x86 laptop is the first prototype target

```text
already on hand: the Lenovo Ubuntu 24.04 laptop is the current confirmed prototype host
built-in battery: provides power-outage ride-through with no extra hardware
built-in display/keyboard: simplifies field setup and debugging
strong CPU/RAM/storage: comfortably runs FastAPI + MongoDB + optional local AI
broad USB/peripheral support: mic/speaker, SDR receiver, and serial bridges attach easily
fast iteration: standard Linux toolchain, no cross-compilation or constrained-device friction
zero new procurement: lets the local-first architecture be proven before hardware spend
```

The laptop is a proving vehicle for the architecture, not the final shipped form factor.

### Raspberry Pi remains supported but secondary

Raspberry Pi (and similar small-board hosts) stay a supported target, but they are secondary to the laptop for first prototyping.

```text
Pi is attractive later for cost, size, fleet density, and wall-mount/in-room form factor.
Pi is harder first: ARM builds, constrained RAM/CPU for local AI, eMMC/SD wear, more device-driver friction.
Decision: prove the architecture on the laptop first; port to Pi once it is stable.
```

Because the software is platform-neutral (see guardrails), the laptop-to-Pi move must not require a redesign — only a re-host.

## Battery-backed node and peripherals

Power resilience is built in, not bolted on.

```text
laptop: internal battery rides through short power outages by default
peripherals (mic/speaker, SDR/pendant receiver, sensors): should sit on battery/UPS-backed power where practical
controllable devices (e.g. Wi-Fi A/C): may lose power in an outage and must fail safe, not fail loud
```

The node should detect and surface its own power state (on-mains vs on-battery, approximate remaining runtime where available) and feed that into the capability registry and fail-graceful modes.

## Local MongoDB as the room-node state store

The room node stores its own state locally in MongoDB.

```text
target: mongodb://localhost:27017 on the room-node host
role: authoritative local store for room-node operation during normal and degraded conditions
```

Rationale:

```text
keeps the node functional with no internet and no cloud database
matches the existing backend's MongoDB-style data access
local-first chosen over a cloud-hosted database (e.g. Atlas) for the first prototype path
```

Cloud or cross-node synchronization, when added, is an enhancement layered on top of the local store. The local store remains authoritative for local care operation; sync must reconcile, not replace, local state, and must respect server-side assignment/permission authority as already described in `docs/CAOSCARE_CONNECTIVITY_RESPONSE_RELAY_CONTRACT.md`.

## Optional local AI tier

The room node may run a local AI tier when host hardware permits.

```text
purpose: local voice/response assistance that survives internet and cloud outages
posture: optional and capability-gated, never assumed present
when absent: the node degrades to deterministic, non-AI response behavior, not silence
```

The local AI tier and the cloud advanced-AI tier are distinct. The response layer must shape replies from actual capability state (see the capability registry in `docs/CAOSCARE_CONNECTIVITY_RESPONSE_RELAY_CONTRACT.md`), not from assumed model availability.

Hard rule: no resident-care-critical behavior may depend on cloud AI. See implementation guardrails.

## Internet as enhancement, not dependency

The node's core care function must not require internet.

Works fully local (must keep working offline):

```text
resident help request acknowledgment
local staff paging/relay within the node's reach
pendant/RF event capture and matching against local records
local response/reassurance loop (deterministic, plus local AI tier if present)
local logging and event queuing
controllable-device actions reachable on the local network
```

Cloud is used only for genuine wide-area or external capabilities:

```text
phone calls
family messaging
news / current web information
remote dashboard / remote visibility
advanced AI (beyond the local AI tier)
```

When cloud-only capabilities are unavailable, the node must say so plainly and continue its local duties. It must never claim a cloud-only capability succeeded when it did not.

## Local mesh / room-node network concept

Room nodes are designed to cooperate as a local network, not only as isolated endpoints.

```text
each room node is self-sufficient on its own
multiple nodes may form a local mesh / room-node network across a facility
the mesh enables local-to-local relay (e.g. staff paging, presence, ETA) without internet
the mesh is an enhancement to local self-sufficiency, not a new single point of failure
```

Mesh design intent:

```text
a node that loses mesh peers still functions locally
the mesh prefers local transport (LAN / local radio) over cloud round-trips
operational relay over the mesh should not increase radio chatter (consistent with the relay contract)
inter-node state exchange must respect role-scoping and permissions; mesh is for operations, not surveillance
```

This is an architectural direction; concrete mesh transport, discovery, and security are future work and must be marked planned/concept until implemented and verified.

## Fail-gracefully modes

The node must define explicit degraded modes. In every mode, resident safety acknowledgment and local logging are preserved as far as the remaining hardware allows.

### Power outage

```text
laptop continues on internal battery; peripherals continue on UPS/battery where present
node surfaces on-battery state and (where available) remaining runtime
non-essential/high-draw activity (e.g. local AI tier) may be shed to extend runtime
controllable devices that lost mains power are treated as offline and fail safe
on battery-critical: log state, notify staff if any path remains, prepare for clean shutdown
```

### Internet outage

```text
local care function continues unchanged
cloud-only capabilities (phone calls, family messaging, news, remote dashboard, advanced AI) are marked unavailable
events destined for cloud are queued locally and flushed on reconnect
the node states the limitation plainly rather than failing silently or overclaiming
```

### Router / access-point outage

```text
the node continues all on-host local function (backend, local store, response layer, logging)
LAN-dependent device control and mesh relay degrade to whatever direct/local transport remains
the node surfaces "local network degraded" and continues serving the room it is in
recovery is automatic when the router/AP returns; queued events flush
```

### Cloud outage

```text
distinct from internet outage: internet may be up while a specific cloud service is down
the affected cloud capability is marked unavailable; local capabilities are unaffected
cloud-bound events queue locally and retry
no resident-care-critical behavior is blocked by the cloud being down
```

### Controlled-device outage

```text
a controllable device (e.g. Wi-Fi A/C) going offline must not crash or block the node
the device is marked offline in the capability registry
the response layer must not claim control it cannot exercise
the node logs the device outage and continues all other duties
```

## First prototype hardware

The first concrete room-node prototype is built from:

```text
Lenovo laptop (Ubuntu 24.04) ........ room-node host: backend, local MongoDB, response layer, logs/queue
eMeet mic/speaker ................... local far-field voice input and output
Nooelec SDR / pendant receiver ..... RF capture for pendant events (e.g. Lifeline 319.5 MHz class)
Wi-Fi A/C .......................... first controllable device / actuation proof
```

This set proves the full local-first loop: capture (pendant/voice) -> local processing/response -> local logging -> local actuation -> graceful degradation. It is the prototype hardware, not a hardware requirement for production.

## Implementation guardrails

These guardrails bound how the architecture is built.

```text
platform-neutral software
    code must run on x86 laptop first and Raspberry Pi later with re-host, not redesign;
    avoid laptop-only or distro-only assumptions in the room-node software.

no vendor lock-in
    prefer open, swappable components for store, AI tier, mic/speaker, RF receiver, and device control;
    no single proprietary cloud, model, or device family may become a hard dependency of the local node.

local logs and queued events
    the node logs locally and queues cloud-bound events locally;
    queued events flush on reconnect; logs/receipts survive outages (consistent with the receipt direction
    in docs/CAOSCARE_CONNECTIVITY_RESPONSE_RELAY_CONTRACT.md).

no resident-care-critical dependency on cloud AI
    safety acknowledgment, paging, pendant matching, and the local reassurance loop must not require cloud AI;
    cloud AI is enhancement only; the node degrades to local AI tier or deterministic behavior.

privacy / mute / physical controls (later)
    physical privacy, mute, and status indicators are planned and must be designable into the node;
    they are future work for this prototype but must not be architected out.
```

## Acceptance direction

This contract is satisfied in spirit when a room node can demonstrate:

```text
Given the Lenovo prototype node running backend + local MongoDB + attached eMeet, SDR, and Wi-Fi A/C
When internet, router, or cloud is removed one at a time
Then local help acknowledgment, pendant capture, local response, local logging, and reachable device control
     continue, cloud-only capabilities are clearly marked unavailable, and cloud-bound events queue and later flush
```

Concrete acceptance tests, mesh transport details, local AI tier selection, and physical privacy controls are follow-on work and must be marked planned/concept until implemented and verified per the `docs/REPO_MAP.md` verification standard.

## Non-negotiable

The CAOSCare room node is local-first.

It must keep residents acknowledged, staff informed, events logged, and reachable devices controllable without internet, without the cloud, and through power, router, and device disruptions. Cloud and mesh extend the node; they must never become the single point of failure that silences it.
