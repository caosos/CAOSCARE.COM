# CAOSCare Grand Central Testing + Live Building Contract

_Status: required acceptance contract_

_Companion to: `docs/GRAND_CENTRAL_AGENT_ARCHITECTURE.md`_

## Core rule

No Grand Central lane is considered complete because its screen renders or its endpoint returns 200.

A lane is complete only when it is tested in isolation, tested against duplicate/retry conditions, tested across linked agents, and exercised inside the running-facility simulation.

The target is a **living building**, not a collection of populated tabs.

## Required test layers for every agent lane

Every implementation lane must ship with all applicable layers below.

### 1. Domain/unit tests

Test the lane's own state transitions and invariants.

Examples:

```text
pending -> acknowledged -> in_progress -> completed
requested transportation != confirmed transportation
community activity != resident signup
appointment != transportation request
nursing call != care aid call != maintenance call
```

### 2. API/service tests

Test create/read/update/cancel/complete behavior through the same service boundary used by production surfaces.

### 3. Idempotency and duplicate tests

Every create/handoff/event path must prove that retries do not create duplicate authoritative records.

Required cases:

```text
same event_id delivered twice -> one effect
same command retried after timeout -> one authoritative record
same appointment event replayed -> one appointment
same transportation booking event replayed -> one booking
same resident activity signup repeated -> one signup
same completion event replayed -> one completion receipt
```

### 4. False-deduplication tests

Duplicate prevention must not merge two different real requests merely because they share a department/category.

Required cases:

```text
Room 401: lamp request + temperature request -> two distinct issues
same resident: bathroom light + broken closet door -> two maintenance issues
same resident: nursing call about pain + nursing call about medication question -> distinct when issue identity differs
same resident: repeated wording for the SAME still-open issue -> no duplicate record; increment re-request/attention metadata
```

Duplicate identity must use concrete entity/request semantics, not category-only matching.

### 5. Resident/room isolation tests

Every resident-facing and staff-facing lane must prove:

```text
Resident A records never appear for Resident B
Room A requests never resolve Room B requests
one resident's appointment never appears in another room's My Day
one resident's activity signup never becomes another resident's commitment
transportation linkage is resident-specific
voice tool context cannot cross resident/session boundaries
```

### 6. Cross-agent integration tests

Each lane must test its handoffs to every linked lane.

Minimum first-pass matrix:

```text
Calendar -> Resident Day
Calendar -> Transportation
Transportation -> Calendar
Transportation -> Resident Day
Nursing Calls -> Front Desk / staff queue visibility
Care Aid Calls -> Front Desk / staff queue visibility
Maintenance Calls -> resident request status
all operational agents -> Grand Central receipts
Grand Central -> facility timeline
```

### 7. UI + voice parity tests

If a resident can see a fact and ask Aria about that fact, the screen and voice must resolve from the same authoritative source.

Required examples:

```text
room profile says 10:30 cardiology -> Aria says 10:30 cardiology
transportation only requested -> neither UI nor Aria may say confirmed
transportation confirmed for 9:45 -> both may say confirmed 9:45 departure
resident signed up for bingo -> My Day + Aria both say resident is participating
community movie only -> UI may show available activity, but Aria must not say resident signed up
```

### 8. Regression tests

Every production bug that reaches a resident/staff workflow gets a permanent regression test before the fix is considered closed.

## Event idempotency contract

Grand Central must treat event delivery as **at-least-once capable**. Consumers therefore must be idempotent.

Minimum mechanics:

```text
event_id is globally unique
consumer stores/recognizes processed event_id
entity_id points to the authoritative record
correlation_id joins one multi-agent workflow
causation_id links downstream events to the event that caused them
```

A consumer receiving an already-processed `event_id` must return success/no-op rather than repeat the mutation.

For human-originated create actions, use a request/idempotency identity when practical so browser retries or voice-tool retries cannot double-create.

## Duplicate semantics

There are three different situations and tests must keep them separate:

### True duplicate

The exact same command/event/request was delivered again.

Action: no new authoritative record.

### Re-request of the same open issue

The resident asks again about the same unresolved issue.

Action: preserve the existing request, update attention/re-request metadata, and create a new receipt/event if needed.

### Different issue in the same department

The resident has another legitimate request for the same department.

Action: create/track a distinct issue. Never collapse solely by department/category.

## Running facility / "building alive" requirement

Grand Central must connect to a deterministic running-facility testbed that continuously exercises the real workflows.

The testbed must use real domain services/endpoints wherever practical. It must not direct-write fake dashboard numbers merely to make screens look active.

### Building state

Owner controls:

```text
Launch
Pause
Resume
Reset demo
```

State:

```text
STOPPED
RUNNING
PAUSED
```

Use an application-level simulation clock. Do not alter host/OS time.

### Scenario engine

Deterministic scenario packs should create realistic building activity such as:

```text
morning resident wake/activity flow
scheduled appointments
resident activity signups
transportation requests
transportation booking/assignment/departure/completion
nursing calls
care aid calls
maintenance calls
housekeeping/kitchen events as those lanes connect
front-desk handoffs
staff acknowledgements/start/completion
resident request status changes
community announcements
shift changes/handoffs
```

### Event progression

The simulator should produce events over simulated time rather than creating the whole day instantly.

Example:

```text
08:00 resident day becomes visible
08:20 resident asks for maintenance
08:22 maintenance acknowledges
08:40 appointment reminder becomes upcoming
09:10 transportation run is assigned
09:30 resident asks "do I have a ride?"
09:45 transportation departs
10:30 appointment occurs
13:30 resident signup appears for 14:00 activity
14:00 activity starts
15:15 care aid call created
15:18 care aid acknowledges
```

The browser should visibly change as this happens.

## Simulation truthfulness

All synthetic records must be marked DEMO/simulation provenance.

Simulation may create realistic workflow pressure, but it must not claim real human actions occurred.

External notifications/integrations should be sandboxed or disabled by default during simulation.

## Whole-building acceptance run

Before a Grand Central milestone merges to main, run a deterministic whole-building scenario and assert at least:

1. Calendar contains community and resident-specific events.
2. Resident signups are distinct from community-wide availability.
3. Room profiles show the correct resident's My Day.
4. Aria verbalizes the same My Day facts.
5. Transportation moves requested -> coordinated -> confirmed -> departed -> completed without duplicate bookings.
6. Nursing Calls, Care Aid Calls, and Maintenance Calls receive independent work.
7. Repeated delivery of selected events does not duplicate records.
8. Two different issues in the same department remain distinct.
9. Re-asking about the same open issue does not create a second ticket.
10. Staff acknowledgement/start/completion updates resident-visible status where appropriate.
11. Front Desk sees unresolved coordination work.
12. Grand Central records one traceable correlation chain for cross-agent workflows.
13. Another resident/room remains isolated throughout the run.
14. Pause freezes simulated progression; Resume continues; Reset returns to deterministic baseline.
15. All assertions pass from data AND browser-visible/voice-facing outputs.

## Merge gate

A lane may be merged into the Grand Central integration branch only when:

```text
focused tests pass
idempotency/duplicate tests pass
resident-isolation tests pass
relevant cross-agent contract tests pass
no known contradiction exists between UI and voice state
```

A Grand Central milestone may merge to `main` only when the whole-building acceptance run passes.

## Definition of "the building is alive"

The building is alive when time advances, residents have distinct days, staff queues receive work, departments respond, schedules trigger linked workflows, transportation moves through real states, room profiles update, Aria knows the same current facts the screens show, and Grand Central can trace why every cross-system change happened.

If the dashboards are merely populated but nothing progresses through real workflows, the building is not alive.
