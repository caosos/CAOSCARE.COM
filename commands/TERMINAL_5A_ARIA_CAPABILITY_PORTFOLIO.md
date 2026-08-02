# Terminal 5A — Aria Capability Portfolio

## Imperative

Voice is the first product milestone, but Aria must not become a voice-only demo. Every device, service, workflow, tool, and future integration that Aria may control must be represented in a durable capability portfolio so it is not forgotten.

The capability portfolio is a required part of the CAOSCare architecture.

## Required model

Create and maintain a machine-readable capability registry backed by clear documentation. Each capability must include at least:

- stable capability ID;
- human-readable name;
- category;
- target device, service, workflow, or system;
- discovery source;
- current status;
- control path;
- required credentials or permissions by variable/name only, never values;
- supported actions;
- read-only observations;
- verification state;
- last successful test time;
- current blocker;
- next step;
- human confirmation policy;
- receipt/log location.

Use explicit lifecycle states:

- `planned`
- `discovered`
- `configured`
- `verified_read`
- `verified_control`
- `blocked`
- `offline`
- `retired`

Aria must never claim she can control a capability unless its status is `verified_control` and the requested action is explicitly registered.

## Initial required portfolio entries

Create entries for at least:

1. CAOSCare conversational voice and memory;
2. Home Assistant status and control API;
3. Midea MAP14AS1TWT-C portable air conditioner through Matter;
4. eMeet Luna Plus microphone/speaker endpoint;
5. MQTT broker and messaging path;
6. EliteDesk service health and restart/status operations;
7. future lights, thermostat, resident-room devices, RF pendant, tablet/kiosk, family calling, and staff escalation capabilities already documented in the repository.

The Midea/Matter entry must remain recorded as blocked or pending while the Home Assistant VM remains behind NAT and until Matter networking and pairing are verified. Do not erase or silently deprioritize it.

## Voice integration rule

At the start of every Aria voice session, load a concise summary of the current capability portfolio along with relevant CAOSCare memory.

When Michael asks Aria to do something:

1. resolve the request to a registered capability and action;
2. verify its current status;
3. execute only through the registered control path;
4. return an accurate spoken result;
5. create a receipt with success, failure, or blocker;
6. update the capability status when testing changes what is known.

When a capability is planned but not available, Aria must say exactly what is missing rather than pretending or forgetting it.

## Priority relationship

Continue Terminal 5 voice-first work now. Do not delay the first working conversation loop to finish every appliance integration.

However, implement the capability registry early enough that the first voice gateway is built around it, not retrofitted after the fact.

The order is:

1. prove audio and conversation;
2. establish the capability registry contract;
3. connect Aria's tool routing to that registry;
4. add and verify capabilities incrementally;
5. return to the Midea Matter network/pairing task after the voice foundation is working or when Ethernet/LAN changes are available.

## Persistence

Store the registry in a durable CAOSCare-owned location and document its schema and API. Home Assistant entity state may populate the registry, but Home Assistant must not be the only durable record of planned, blocked, or non-home-automation CAOSCare capabilities.

Append meaningful progress to `docs/PROJECT_STATE.md`. Do not erase blocked items when priorities change.

## Immediate instruction

Read this directive together with `commands/TERMINAL_5_ARIA_VOICE_FIRST.md`. Continue voice-first implementation while creating the initial capability portfolio and preserving the Midea Matter/LAN work as a tracked blocked capability.