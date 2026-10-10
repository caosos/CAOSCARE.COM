# CAOSCARE Current Priority

**Status:** Active execution priority  
**Set by Michael:** 2026-09-26  
**Target:** **CAOSCare Pilot 1 operational by 2026-10-10**

**Recovery / continuity:** [`docs/PILOT1_RECOVERY_CHECKPOINT.md`](PILOT1_RECOVERY_CHECKPOINT.md) records the pipeline, lane tips, shared-core status, Michael's decisions and the next integration order (2026-09-28). Parallel lanes are mapped in [`docs/PILOT1_ACTIVE_WORK.md`](PILOT1_ACTIVE_WORK.md). These Pilot 1 files live on `integration/2026-09-27`.

**Execution tracker:** [`docs/PILOT1_EXECUTION_CHECKLIST.md`](PILOT1_EXECUTION_CHECKLIST.md) is the authoritative, living checklist for the 2026-10-10 Pilot 1 target: phases, task status, acceptance evidence, the current phase and the current active task. This file sets priority; the checklist tracks execution. Update the checklist after every meaningful work block.

This file is intentionally short-lived/current-state guidance. It does not replace the Product Baseline, AGENTS.md, lane contracts, or PROJECT_STATE. When this target is completed or Michael changes direction, update this file rather than leaving stale priority instructions in onboarding.

## Direction update (owner, 2026-10-10): voice PARKED; transportation -> email -> calling

Michael is happy with voice for now. **PARKED, do not work or rebuild for:** RQ-052/RQ-051/RQ-053 voice timing and claim-interrupter measurement, voice audits and tuning, audible-goodbye/voice acceptance, and the `cfc8020` end-intent page rebuild (code is on integration, **not live**; the Room 214 page runs bundle `main.18cb3cf4.js`). Active order: (1) transportation logs (ride log built, `cc00b46`), (2) email connectivity (RQ-005, blocked on provider key/domain/addresses), (3) calling (Asterisk/ATA/trunk, hardware/accounts). Owner/hardware-gated items are unchanged: `docs/MICHAEL_ACTION_RUNBOOK.md`. Dev backend restarts on the EliteDesk are routine and use `scripts/restart_dev_backend.sh` (allow-rule `Bash(scripts/restart_dev_backend.sh)` set by Michael); Linode and resident production remain gated.

## Aria room voice decision (Michael, 2026-10-03)

**Correction (Michael, 2026-10-03, supersedes the eMeet/EliteDesk wording in the paragraph below):** the HP EliteDesk is the central community server running Home Assistant and CAOSCare; apartments get no EliteDesk. The Voice PE is the room voice endpoint over Wi-Fi; central HA + CAOSCare handle speech, conversation, memory, workflows, devices and receipts. The standard room has no eMeet. Test the Voice PE's own microphones in a real apartment first; if coverage is short, investigate another room audio endpoint without a per-apartment EliteDesk. SIP/front-desk calling stays a separate handset/telephony function. See `docs/ROOM_AUDIO_ARCHITECTURE.md`.

The resident-facing assistant remains **Aria**. Primary wake phrase **"Hey Aria"** (secondary test candidate "Aria"; pronunciation AR-ee-uh) on the Home Assistant Voice Preview Edition with custom firmware (`firmware/voice-pe-aria`, firmware architect). Do **not** use "Hey Naboo", "Naboo", "Hey Nabu" or "Okay Nabu" as product identity or production wake phrase; `firmware/voice-pe-naboo` @ `9dff64b` is preserved proof only, never merged into the product path. The CAOSCare ↔ Home Assistant bridge is `spike/voice-bridge` @ `aa3d2f1` (spike, not merged). CAOSCare stays the conversation/memory/workflow/receipt authority; the eMeet stays on the EliteDesk for calls. Detail: `docs/ROOM_AUDIO_ARCHITECTURE.md`, `docs/ARIA_WAKE_WORD_ARCHITECTURE.md`.

## Immediate execution accelerator — observable operations simulator

Michael approved building an **observable CAOSCare Operations Simulator** as a
first-class development/acceptance tool. It is not a side demo and must not
create a second data universe.

The simulator must:

- use the same canonical workflows as real residents/staff/admin;
- support multiple bounded simulated agents with explicit roles/departments;
- allow real people (including Michael) to be scheduled into a role and take
  over work through the normal CAOSCare UI;
- provide Start / Pause / Resume / Step / Stop controls and a visible event
  stream;
- make real-vs-simulated identity unmistakable;
- preserve the hard rule **No action without a receipt. No receipt without
  provenance.**;
- make every action traceable from origin → actor → authority → execution →
  resulting state → evidence;
- never accept an agent's own "done" claim as proof.

Canonical requirements: [`docs/CAOSCARE_OPERATIONS_SIMULATOR.md`](CAOSCARE_OPERATIONS_SIMULATOR.md).

This work is intended to **accelerate** the real product by continuously
exercising its actual workflows. It must not displace Room 1, voice, real
communications, hardware or operator usability with a disconnected simulator.

## Pilot 1 finish line

By 2026-10-10, CAOSCare should be usable as a real pilot in **one or two resident rooms** at a community, using the community's normal network, with the minimum dependable hardware and software required to operate.

The target is not "finish every future CAOSCare idea." The target is a real, usable product slice.

Pilot 1 should prove these two chains:

```text
Resident speaks / presses
→ Aria understands
→ CAOS routes
→ correct department is notified
→ staff sees and acts
→ lifecycle / receipt changes
→ Aria can truthfully report current status
```

and:

```text
Resident asks for a room action
→ CAOS issues the device command
→ actual hardware executes / verifies
→ Aria reports the observed result truthfully
```

## Non-negotiable demo rule

**Do not publicly demonstrate a capability as working before the real resident/staff/admin workflow is actually usable and acceptance-tested.**

Marketing/demo surfaces are downstream of the working product.

For each capability:

1. build the real operational workflow;
2. make the resident/staff/admin pages usable in normal work;
3. run a real end-to-end acceptance test;
4. only then expose a public demonstration of that capability;
5. if unfinished, hide it or label it honestly as in development / planned.

The public website must never outrun the real product.

## Priority order

### P0 — Keep the development/deployment topology disciplined

Normal completion path:

```text
Laptop (control/gateway)
→ SSH EliteDesk
→ build / integrate / test
→ commit
→ push GitHub
→ Michael reviews exact release
→ deploy exact approved GitHub SHA to Linode
→ verify production
```

EliteDesk is the current integrated development environment. GitHub is canonical committed source/history. Linode is approved production. Feature branches/worktrees are temporary lanes, not permanent alternate CAOSCare versions.

### P1 — Finish and stabilize the real software people will use

Close and acceptance-test the actual operational workflows and their UI surfaces, including the highest-value pilot paths:

- resident Aria request creation/status;
- nursing/care requests;
- maintenance requests;
- transportation;
- dining/menu;
- activities/programs;
- housekeeping;
- front desk / administration requests;
- department workspaces and staff lifecycle;
- admin/leadership visibility;
- receipts/history/status truth.

The standard is not "backend code exists." The intended resident, staff member, or administrator must be able to use the workflow without developer knowledge or SSH.

### P2 — Make real email/notification exchange operational

Configure and live-test the existing inbound/outbound communication plumbing.

Minimum pilot proof:

- a real inbound menu email reaches CAOSCare, is safely ingested, reviewed/approved, and updates the real menu;
- a real inbound activities/program email reaches the system and updates the relevant workflow;
- a real resident/staff request routes to the correct department and produces an actual notification/email;
- notification status and receipts are inspectable;
- no "logged only" behavior is presented as actual delivery.

Add department addresses/allowlists as needed using the existing architecture rather than inventing parallel email systems.

### P3 — Close Resident Aria's real-life operational loops

#### Resident calling is a Pilot 1 requirement

Residents must be able to use Aria to initiate real calls without operating a complicated device.

Minimum Pilot 1 calling paths:

- **Front desk:** "Aria, call the front desk." Aria initiates a real two-way call to the community front desk using the room audio/handset path and reports call state truthfully.
- **Family:** a resident may ask Aria to call an approved family contact. Use the resident's structured contact list/permissions; do not guess numbers or call arbitrary contacts.
- Preserve a simple call lifecycle: requested → dialing → connected / unanswered / failed → ended, with a receipt/log suitable for troubleshooting and operational review.
- Aria must never claim a person answered or that a call connected unless the telephony provider/runtime proves it.
- Calling must be usable from the resident room without requiring a tablet UI.

Current repository evidence says Twilio SMS/email plumbing exists, but live-line Twilio **voice** is not yet operational in the current audited state. Treat real voice calling as unfinished until a live front-desk call and a live approved-family call are acceptance-tested.

Test natural requests such as:

- "My sink is leaking."
- "There is a smell in my bathroom."
- "There is something on the floor."
- "I need help going to the bathroom."
- "I need a nurse."
- "I want to speak with the executive director."
- "I need transportation for my appointment at 9:30 on the fifth."

Aria should understand intent, ask only for genuinely missing information, create/use the correct real workflow, route it, preserve resident wording/context, avoid false claims, and answer later status questions from the real system state.

CAOSCare must be more than another Alexa: relationship/context + governed action + receipts + truthful follow-through.

### P4 — Build the minimum dependable room hardware stack

For one room first, then reproduce it in a second room.

Michael already has pilot hardware available including:
- a wireless thermostat;
- wireless light bulbs;
- wireless smart plugs.

Inventory their exact makes/models/protocols before buying duplicates. Integrate them only through verified adapters and read-back where available.

Minimum practical stack may include:

- central EliteDesk server running Home Assistant + CAOSCare (no per-apartment computer — correction, Michael, 2026-10-03; replaces "hidden EliteDesk-class room node");
- reliable Wi-Fi/Ethernet on the community network;
- Home Assistant Voice PE as the Aria room voice endpoint ("Hey Aria"; see `docs/ROOM_AUDIO_ARCHITECTURE.md`, 2026-10-03);
- no eMeet in the standard room; SIP/front-desk calling via a separate handset/telephony function (correction, Michael, 2026-10-03; replaces the eMeet line recorded in `444e297`);
- dependable wake/voice path for the actual room;
- IR control for the actual TV (procure the minimum compatible IR hardware needed for the pilot room);
- RF/pendant receiving as a **secondary / additive** CAOSCare feature; CAOSCare must not interfere with or replace the resident's existing community call-button workflow during Pilot 1;
- the minimum real light/HVAC/device control needed for the chosen pilot rooms;
- other protocols only when they close an actual pilot requirement.

Michael has indicated budget is available for required RF/IR/device hardware. Do not buy broad speculative hardware before identifying the exact pilot-room need.

Pendant priority for Pilot 1: preserve the facility's existing button behavior first. CAOSCare may listen/ingest the pendant signal in parallel for context, receipts, Aria follow-up, or staff workflow integration, but the existing resident safety/call path remains authoritative unless a later validated deployment intentionally changes it. A common pendant use case is toileting/bathroom assistance; CAOSCare should be able to interpret that context through the resident/staff workflow without falsely treating every button press as the same intent.

### P5 — Make one room boringly reliable, then clone to room two

Acceptance includes:

- auto-start after reboot/power loss;
- service recovery after normal network interruptions;
- correct resident/room identity;
- no duplicate voice sessions;
- real pendant/event routing;
- truthful hardware command success/failure;
- normal operation without SSH babysitting.

Document the provision/setup so the second room is a reproduction, not a second science experiment.

### P6 — Public resident/family experience

This is the first public story people should understand.

Show what living with CAOSCare feels like using only proven capabilities:

- resident experience videos;
- interactive capability cards;
- room/apartment experience;
- accessibility/low-vision support;
- voice/help/maintenance/status flows;
- proven room controls;
- family/resident communication where actually usable.

Capability cards should be clickable and open an on-page demonstration rather than dead marketing copy.

### P7 — Public "For Communities" / community experience

Separate community/operator marketing from real staff sign-in.

- **Staff dashboard demo** = public sample/demo experience.
- **Staff sign in** = real authenticated operational product.

Community/operator demonstrations should show the real workflow behind nursing, maintenance, transportation, dining, activities, housekeeping, front desk/administration, reporting/receipts, and other completed domains.

Community profiles should eventually support verified community-specific information such as photos, floor plans, dining, amenities, and reusable CAOSCare experience modules. Build this as data-driven exchangeable community information, not one hardcoded page per facility.

### P8 — End-to-end pilot acceptance

Before calling Pilot 1 ready, deliberately exercise the system from resident request through staff action and follow-up, including browser/mobile use, emails, restart/recovery, actual room hardware, and production-facing website claims.

Every failure becomes a bounded punch-list item. Avoid unrelated feature expansion until the pilot chain passes.

## Scope discipline through 2026-10-10

New ideas go to the backlog unless they are required to close a Pilot 1 loop.

Do not let these displace the deadline unless Michael explicitly changes priority:

- broad old-branch cleanup;
- speculative future device protocols;
- polishing features not needed for Pilot 1;
- large unrelated refactors;
- demos of unimplemented capabilities;
- expansion to many rooms before one/two-room reliability is proven.

## Current decision rule

When choosing what to work on next, ask:

**Does this materially help make one or two real rooms + real staff workflows operational by 2026-10-10?**

If yes, prioritize it.

If no, backlog it unless Michael explicitly overrides this priority.
