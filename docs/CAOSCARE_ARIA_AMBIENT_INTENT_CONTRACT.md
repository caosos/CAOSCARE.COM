# CAOSCare ARIA Ambient Intent Contract v1

## Status

Active architecture contract.

This document defines ARIA: the CAOSCare ambient personal intent layer. ARIA maps natural language spoken from anywhere into trusted, permission-checked, receipt-logged actions across CAOSCare, Home Assistant, and future adapters.

It is an architecture/governance contract only. It does not redefine product scope, care workflows, or safety posture, and it does not claim any described integration is deployed or runtime-verified. Capability status follows the verification standard in `docs/REPO_MAP.md`. Every integration named here is `planned/concept` until source-verified.

CAOSCare remains assistive, advisory, human-supervised, receipt-backed. Nothing in ARIA grants clinical authority, autonomous medical judgment, or autonomous emergency dispatch.

## Related contracts

ARIA composes over existing CAOSCare contracts rather than replacing them:

```text
docs/CAOSCARE_LOCAL_FIRST_ROOM_NODE_CONTRACT.md ..... where ARIA runs; offline/degraded behavior ARIA inherits
docs/CAOSCARE_CONNECTIVITY_RESPONSE_RELAY_CONTRACT.md  capability registry + receipts ARIA reuses
docs/CAOSCARE_MEMORY_AUTOMATION_CONTRACT.md ......... subject model + source modes for identity/context
docs/CAOSCARE_PRIVACY_SAFETY_SECURITY_NORTH_STAR.md . consent, least-identifying-info, sensor posture
```

Note: the local-first room-node contract currently lives on the `local-ai-room-node` branch and may not yet be present on every branch. The cross-reference is intentional and resolves once that branch merges.

## Core position

ARIA is an intent layer, not a device, not a single endpoint, and not a replacement for any system it calls.

```text
ARIA sits ABOVE CAOSCare, Home Assistant, wearable endpoints, phone, laptop, and future room nodes.
A person speaks naturally from anywhere.
ARIA maps that language to a trusted action, checks permission, calls the correct system, and logs a receipt.
```

ARIA never holds authority of its own. Identity, permission, tasks, audit, and receipts remain CAOSCare responsibilities. ARIA orchestrates; CAOSCare governs.

## Layering

```text
input endpoints   wearable / Bee / phone / laptop / room mic / future room nodes
        |
      ARIA         ASR -> intent -> identity resolution -> permission check -> route -> receipt
        |
   adapters        Home Assistant (first), future vehicle class, future Google/GitHub
        |
    systems        houses/devices, vehicles (future), external tools (future)
```

CAOSCare is the cross-cutting governance plane for every layer:

```text
identity        who is speaking, resolved to an authorized principal
permission      role/consent/allowlist checks before any action
tasks           work items created or updated by an action
audit           every action attempt and outcome
receipts        a durable record per action, written with the action
```

## Home Assistant is the first actuator adapter

Home Assistant (HA) is the first and lowest-risk actuator adapter behind ARIA's action router.

```text
ARIA does not bypass Home Assistant's own device/entity model.
ARIA maps an utterance to a canonical intent, checks permission, then calls an HA service through the HA adapter.
Home Assistant keeps owning the devices; ARIA owns the intent and the receipt.
```

Because HA can run locally on the LAN, house/device control fits the local-first posture: it should keep working without internet, consistent with the room-node contract's "works fully local" list. When HA is unreachable, ARIA must say so plainly and must never claim control it could not exercise.

## First proof-of-concept command

The first PoC exercises the entire loop with the lowest possible risk.

```text
Spoken:   "Aria, turn on the living-room AC"
   or:    "Aria, cool the house down."

Pipeline: ambient input (room mic / laptop)
       -> ARIA maps to canonical intent (e.g. climate.set / climate.on)
       -> identity resolved to an authorized principal
       -> permission + allowlist check
       -> Home Assistant adapter calls the HA service
       -> device acts
       -> receipt logged and read back ("Done — living-room AC on, logged.")
```

Why this command first:

```text
exercises the full loop: ambient input -> intent -> permission -> adapter -> action -> receipt
reuses the room-node contract's already-chosen first controllable device (Wi-Fi A/C), aligning the branches
reversible, non-safety-critical, no external/cloud dependency
not a vehicle command; not an unlock or any security-critical action
```

## CAOSCare remains the governance layer

ARIA must route identity, permission, task, audit, and receipt responsibilities to CAOSCare. ARIA does not maintain a parallel authority store.

```text
identity     reuse CAOSCare identity and the memory contract's subject_type + subject_id model
permission   reuse CAOSCare role/consent scoping; ARIA adds per-target allowlists and limits
tasks        actions may create/update CAOSCare task records where appropriate
audit        reuse the existing audit domain; every action attempt is auditable
receipts     a receipt is written with the action, never after the fact as an afterthought
```

If CAOSCare cannot confirm identity or permission, ARIA must refuse the action and say why in plain language.

## Input endpoints

Endpoints supply language and context. They do not hold action authority.

```text
room mic        far-field voice input in a room/node
laptop          voice or typed input
phone           mobile voice/text input and context
wearable / Bee  future mobile microphone / context endpoint (planned/concept)
future room nodes  additional ARIA-aware endpoints across a facility or home
```

Each endpoint is a registered ARIA endpoint carrying:

```text
endpoint_id
endpoint_type
capability flags (e.g. voice_input_available, network_status) per the relay contract
location hint (where permitted)
identity hint (resolved to a principal by CAOSCare, never trusted blindly)
```

Endpoint posture follows the north-star sensor rule: event-triggered, permission-scoped, visible when active, minimal retention. Always-listening behavior, wake-word vs. always-on, and retention are explicit design decisions, not defaults.

## Wearables / Bee are input/context only

Wearables, including a Bee/wrist device, are future input/context endpoints, not sources of authority.

```text
they may capture an utterance and supply context (endpoint, location hint, identity hint)
they may NOT themselves authorize or execute an action
they are subject to the capability registry and the north-star sensor/consent rules
Bee specifically is a future mobile microphone/context endpoint, marked planned/concept
```

## Vehicle adapter class (future, planned/concept)

Vehicle control is a separate, high-risk adapter class behind a common adapter interface. It is `planned/concept` and is not part of the first PoC.

```text
a common VehicleAdapter interface defines climate / remote-start intents
Ford / Chevy / Hyundai / Toyota are EXAMPLE concrete adapters only
no public or private vehicle API may be assumed available, or assumed permitted by its terms,
   until separately verified per the docs/REPO_MAP.md verification standard
```

### Vehicle guardrails (mandatory adapter preconditions)

These are preconditions, not afterthoughts. A vehicle action that cannot satisfy all applicable guardrails must be refused.

```text
owner / authorized-user only
    the speaker must resolve to an authorized vehicle principal; ambient "anyone can speak" is not sufficient.

no garage / enclosed-space start
    remote start is forbidden without a reliable not-enclosed signal; if enclosure state is unknown, refuse.

climate / remote-start only at first
    the only initial vehicle intents are climate and remote-start.

no unlock / security-critical actions initially
    unlock, security, and access-critical actions are out of scope until explicitly authorized later.

runtime / rate limits
    bounded run duration and bounded command frequency per vehicle.

explicit consent and per-vehicle allowlist
    each controllable vehicle must be explicitly consented and on a per-vehicle allowlist.

receipt / audit log for every action
    every vehicle action attempt and outcome is logged with a receipt, written with the action.
```

High-risk and vehicle actions also require an explicit confirmation step before execution.

## External tool adapters (future, planned/concept)

Google / Gmail / Calendar / GitHub are allowed tool targets only when permissioned, and only through dedicated adapters. They are `planned/concept` and out of scope for the first PoC. They follow the same router, permission, allowlist, and receipt rules as every other adapter.

## Required components

The contract is realized by these components (each `planned/concept` until source-verified):

```text
endpoint registry          wearable/phone/laptop/room-mic/Bee, with capability flags
ASR + intent mapper        utterance -> canonical intent + slots; local tier preferred (see guardrails)
canonical intent schema    a small, versioned vocabulary of trusted intents
identity resolution        CAOSCare identity + subject_type + subject_id; resolves the speaking principal
permission/consent engine  role scope, per-target allowlists, consent records, runtime/rate limits
adapter interface + registry  HA adapter (first), VehicleAdapter (future), tool adapters (future)
action router/dispatcher   selects the correct system and adapter for the intent
capability registry        reuse the relay contract's registry; replies shaped by real capability state
receipt/audit log          reuse the audit domain; one receipt per action, written with the action
confirmation/clarification flow  mandatory confirm for high-risk/irreversible actions
```

## Fail-graceful behavior

ARIA inherits the room-node degraded modes. It must never claim a success that did not happen.

```text
adapter/system unreachable   refuse plainly; mark the capability unavailable; do not fake success
internet/cloud outage        local adapters (e.g. local HA) continue; cloud-only intents are marked unavailable
queued actions               cloud-bound actions queue locally and flush on reconnect (per relay contract)
identity/permission unknown  refuse and explain; never act on an unresolved principal
```

## Implementation guardrails

```text
ARIA holds no authority of its own
    identity, permission, tasks, audit, and receipts are CAOSCare responsibilities; ARIA orchestrates.

receipts precede trust, not actions in hindsight
    a receipt is written with the action; no action is "trusted" without an auditable record.

no resident-care-critical dependency on cloud AI
    consistent with the room-node contract; ASR/intent should have a local tier or degrade deterministically.

least-identifying-info and consent
    follow the north star; capture and route only the context an action requires.

no vendor lock-in
    prefer open, swappable adapters for ASR, intent, HA, vehicles, and tools.

stay in the care-safety boundary
    ARIA is assistive/advisory; no clinical authority, no autonomous emergency dispatch.
```

## Acceptance direction

This contract is satisfied in spirit when ARIA can demonstrate the HA-only first loop:

```text
Given a registered room mic / laptop endpoint and a reachable local Home Assistant
When a person says "Aria, turn on the living-room AC" (or "Aria, cool the house down")
Then ARIA resolves the speaking principal through CAOSCare, checks permission and the device allowlist,
     calls the Home Assistant service through the HA adapter, the device acts, and a receipt is logged and read back;
And when Home Assistant is unreachable, ARIA refuses plainly, marks the capability unavailable, and claims no success.
```

Concrete intent schemas, endpoint authentication, vehicle adapters, tool adapters, and always-listening/privacy controls are follow-on work and must be marked planned/concept until implemented and verified per the `docs/REPO_MAP.md` verification standard.

## Non-negotiable

ARIA is the ambient personal intent layer above CAOSCare and the systems it controls.

It maps natural language to trusted actions, but it never owns authority: CAOSCare governs identity, permission, tasks, audit, and receipts. Home Assistant is the first actuator adapter. Wearables and Bee are input/context endpoints only. Vehicle control is a future, high-risk adapter class bound by owner-only authorization, no enclosed-space start, climate/remote-start only, no security-critical actions initially, runtime/rate limits, explicit consent and per-vehicle allowlist, and a receipt for every action — with no assumed vehicle API until separately verified.
