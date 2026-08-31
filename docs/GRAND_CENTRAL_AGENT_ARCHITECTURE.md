# CAOSCare Grand Central Agent Architecture

_Status: implementation contract_

_Branch: `feature/runtime-agent-lanes-20260830`_

## Product direction

CAOSCare should operate like **Grand Central Station**: many specialized operational agents work in parallel on separate tracks, while one central orchestration layer keeps the building state coherent.

Aria is the resident/staff conversational surface and high-level orchestrator. Aria should not become one giant sequential worker that owns every workflow.

The architecture must support separate build lanes and separate runtime ownership for:

1. Calendar / Schedule Agent
2. Transportation Agent
3. Nursing Calls Agent
4. Care Aid Calls Agent
5. Maintenance Calls Agent
6. Resident Day / Room Profile Agent
7. Communications / Front Desk Agent
8. Grand Central Orchestrator
9. QA / Integration Agent

## Non-negotiable architecture rule

**Separate agents do not mean separate truths.**

Each domain agent owns workflow logic for its track, but all tracks read/write the same authoritative facility records. Do not create duplicate shadow databases for an agent.

Existing authoritative domains should be reused where sound:

- residents / kiosks / rooms
- `StaffTask` resident-request bus
- schedule records
- transportation requests/runs/resources
- alerts/escalations
- operational receipts/provenance
- devices

The Grand Central layer routes facts and workflow changes between domains; it does not fabricate facts.

## Grand Central event contract

All cross-agent handoffs should use a common event envelope. The initial contract is:

```text
event_id
schema_version
event_type
facility_id
resident_id        optional
room               optional
source_agent
target_agents[]
entity_type
entity_id
occurred_at
correlation_id
causation_id        optional
payload{}
provenance{}
```

Every event must point back to an authoritative record through `entity_type + entity_id`.

The event bus is a coordination layer, not a second database of record.

## Agent tracks

### 1. Calendar / Schedule Agent

Owns:

- community calendar
- resident appointments
- resident commitments
- activity/event dates and times
- resident sign-ups / participation commitments
- schedule conflict detection
- calendar-facing query APIs

Emits examples:

```text
calendar.item.created
calendar.item.updated
resident.appointment.created
resident.appointment.changed
resident.activity.signup.created
resident.activity.signup.cancelled
```

Consumes examples:

```text
transportation.booked
transportation.changed
transportation.cancelled
```

### 2. Transportation Agent

Owns:

- transportation requests
- requested time vs confirmed time
- driver assignment
- vehicle assignment
- runs / shared rides
- departure timing
- pending / unslotted work
- confirmation / completion

Emits examples:

```text
transportation.requested
transportation.booked
transportation.changed
transportation.cancelled
transportation.departed
transportation.completed
```

When an appointment requires transportation, Calendar may create a transportation-needed event. Transportation independently owns whether a ride is actually confirmed.

### 3. Nursing Calls Agent

Owns the nursing call queue as a first-class track.

It receives resident nursing requests, tracks acknowledgement / assignment / progress / completion, and provides a nursing-specific work surface.

It must not be collapsed into a generic staff queue merely because the underlying authoritative record may remain `StaffTask`.

Emits examples:

```text
nursing.call.created
nursing.call.acknowledged
nursing.call.started
nursing.call.completed
nursing.call.updated
```

### 4. Care Aid Calls Agent

Owns resident requests for day-to-day personal assistance that belong to care aid staff rather than the Nursing Calls or Maintenance Calls tracks.

Examples include assistance workflows routed by facility policy to care aid staff.

Emits examples:

```text
care_aid.call.created
care_aid.call.acknowledged
care_aid.call.started
care_aid.call.completed
care_aid.call.updated
```

This must be a distinct operational queue and agent, even when it reuses the shared request/task record underneath.

### 5. Maintenance Calls Agent

Owns:

- resident maintenance calls
- work-order intake
- room/building assignment
- blocked / parts-needed / vendor-needed status
- acknowledgement / assignment / completion
- resident-visible status

Emits examples:

```text
maintenance.call.created
maintenance.call.acknowledged
maintenance.call.started
maintenance.call.blocked
maintenance.call.completed
maintenance.call.updated
```

### 6. Resident Day / Room Profile Agent

Every room profile must display and verbalize resident-specific commitments from authoritative records.

The resident-facing `My Day / Upcoming` view must include at least:

- appointments
- confirmed transportation associated with appointments
- activities the resident signed up to participate in
- community events or programs the resident personally committed to
- other resident-specific scheduled commitments added later

It must distinguish:

```text
appointment scheduled
transportation requested
transportation confirmed
activity available to everyone
resident signed up for activity
```

Those are different facts and must never be blurred together.

The visual room profile and Aria's spoken answer must read the **same resident-day endpoint/source of truth**.

Required voice behavior:

```text
"Aria, what do I have today?"
"What time is my appointment?"
"What did I sign up for?"
"Do I have a ride?"
"What's coming up tomorrow?"
```

Aria answers only from resident-day records and linked authoritative domain state.

### 7. Communications / Front Desk Agent

Owns cross-department operational communication and the Front Desk's coordination view.

Responsibilities include:

- pending transportation coordination
- resident/staff messages
- department handoffs
- room-to-room / staff routing where supported
- unresolved cross-domain items
- acknowledgement receipts

### 8. Grand Central Orchestrator

The Grand Central Orchestrator owns **routing and synchronization**, not the business rules of every domain.

Responsibilities:

- receive domain events
- validate event schema
- attach correlation/causation IDs
- route to interested agents
- prevent duplicate delivery where possible
- maintain event receipts
- surface failed handoffs
- support replay/debugging
- provide a facility-level timeline

Example flow:

```text
Calendar Agent
  -> resident.appointment.created
      -> Resident Day Agent updates My Day
      -> Transportation Agent evaluates transportation need
      -> Communications Agent can surface coordination work

Transportation Agent
  -> transportation.booked
      -> Calendar reflects confirmed ride metadata
      -> Resident Day Agent shows the confirmed ride
      -> Aria can truthfully verbalize the confirmed departure
```

Another flow:

```text
Resident says: "I need maintenance for my bathroom light."
  -> Maintenance Calls Agent creates/owns the call
  -> Grand Central emits maintenance.call.created
  -> Maintenance workspace receives it
  -> Resident Day/Room Profile can show request status if appropriate
  -> Aria can answer status questions from the same record
```

## Build lanes / file ownership

Agents should be built simultaneously only with non-overlapping ownership.

### Lane GC — Grand Central integration

Owns new event-contract / event-router files only until integration windows.

### Lane CAL — Calendar / resident commitments

Owns schedule/calendar domain files and resident sign-up domain files.

### Lane TRN — Transportation

Owns transportation domain files.

### Lane NUR — Nursing Calls

Owns nursing-call service / queue / UI files. Reuse shared task records without taking ownership of unrelated task UI.

### Lane AID — Care Aid Calls

Owns care-aid call service / queue / UI files.

### Lane MNT — Maintenance Calls

Owns maintenance-call service / queue / UI files.

### Lane DAY — Resident Day / Room Profile

Owns resident-day aggregation endpoint/service and resident-facing My Day UI/tool wiring.

### Lane COM — Communications / Front Desk

Owns communication/handoff/front-desk coordination files.

### Lane QA — Integration / acceptance

Read-mostly while implementation lanes work. Owns cross-domain tests and integration reports.

## Collision rule

No two implementation agents edit the same production file simultaneously.

Central files such as these require explicit integration windows:

```text
backend/models.py
backend/server.py
frontend/src/pages/Kiosk.jsx
frontend/src/pages/Admin.jsx
frontend/src/lib/useRealtimeVoice.js
```

A lane needing a central-file change should supply the change requirement to Grand Central/integration rather than racing another lane.

## First integration milestone

The first vertical slice is complete when all of this works together:

1. Staff adds a resident appointment.
2. The appointment appears on that resident's room profile.
3. Aria can answer the resident's appointment question from the same data.
4. If transportation is required, Transportation receives the handoff.
5. A transportation request is visibly different from a confirmed ride.
6. When a ride is confirmed, the room profile updates without duplicating the appointment.
7. Staff can create Nursing Calls, Care Aid Calls, and Maintenance Calls into three distinct operational queues.
8. Each queue supports create -> acknowledge -> start -> complete.
9. Grand Central records the cross-agent event receipts.
10. Cross-domain acceptance tests prove one resident's records never bleed into another resident/room.

## Resident-facing acceptance examples

A resident with:

```text
10:30 AM — cardiology appointment
9:45 AM — confirmed transportation departure
2:00 PM — signed up for bingo
```

should see those facts on the room profile and be able to ask Aria for them verbally.

A community-wide 4:00 PM movie that the resident did **not** sign up for may still appear under community activities, but it must not be stated as something the resident personally signed up to participate in.

## Definition of Grand Central working

Grand Central is working when independent domain agents can change their own authoritative records, emit a shared event, and every relevant surface converges on the same truth without manual copying, duplicate records, or contradictory spoken/UI state.
