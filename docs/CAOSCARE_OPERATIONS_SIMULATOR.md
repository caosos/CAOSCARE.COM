# CAOSCare Operations Simulator

**Status:** Approved architecture + implementation target  
**Owner:** CAOSCare coordination / simulator lane  
**Set by Michael:** 2026-10-02  
**Core rule:** **No action without a receipt. No receipt without provenance.**

## 1. Purpose

CAOSCare needs a continuously observable simulated community that exercises the
**same canonical workflows** as real residents and real staff.

The simulator is not a separate fake application and must not create a second
task/request/resident universe. It drives the real CAOSCare service layer with
explicitly simulated actors and simulated-safe adapters, so failures discovered
in simulation are failures in the same operational paths real users depend on.

The simulator exists to let Michael and the team:

- watch a community operate in real time;
- pause/resume simulation;
- inspect every action and its origin;
- mix simulated actors with real logged-in people;
- schedule Michael or another real person into a staff role;
- take over work manually;
- observe handoffs between resident, staff, department, Aria, devices and communications;
- reproduce failures from the receipt/provenance trail;
- prove workflows before relying on them in a live community.

## 2. Non-negotiable receipt law

> **No action is performed without a durable receipt.**
>
> **If CAOSCare cannot trace an action to its origin, the action is not validly complete.**

Every meaningful action or state transition must have enough provenance to answer:

1. **Origin** — what caused this action?
2. **Actor** — resident, real staff user, simulated staff agent, Aria, scheduler, inbound email, device event, admin, API integration, etc.
3. **Authority** — what permission/rule allowed the action?
4. **Intent** — what was requested or expected?
5. **Execution** — which service/tool/provider performed it?
6. **Target** — which resident/request/task/device/message/workflow was touched?
7. **Before state** — what was true before the action?
8. **After state** — what changed?
9. **Evidence** — what proves attempted/succeeded/failed/unknown?
10. **Time** — when was it requested, started and completed?
11. **Parent link** — which originating request/event/receipt caused it?
12. **Next state** — what is now waiting, due, blocked, completed or escalated?

An agent saying "done" is never proof by itself.

### Minimum receipt fields

The canonical receipt/event contract should support, directly or by linked
records:

- receipt/event ID
- parent/origin receipt ID
- correlation/workflow ID
- actor ID
- actor type: real-human / simulated-agent / system / external-provider
- actor role + department where applicable
- source channel
- action type
- target object type + ID
- requested parameters
- authorization/policy result
- status: requested / attempted / succeeded / failed / unknown / cancelled
- before/after state references where applicable
- provider/tool response reference
- error/failure reason
- timestamps
- branch/build/runtime version where relevant for test evidence

Receipts are append-only operational evidence. Corrections create new events;
they do not silently rewrite history.

## 3. Same-world rule

The simulator must use the same canonical service functions and domain objects
used by:

- resident Aria;
- resident room UI;
- staff workspaces;
- admin;
- front desk;
- inbound/outbound communications;
- device adapters;
- real humans.

The simulator may use simulated-safe **actors** and **adapters**, but not a
parallel business-logic universe.

Examples:

- simulated resident request → canonical request service → real task lifecycle;
- simulated maintenance worker accepts task → canonical task assignment/status service;
- simulated menu email → normal inbound email validation path, explicitly marked simulated;
- simulated room command → normal device command contract → simulated adapter → verified simulated state;
- real Michael logs in as Maintenance → same task queue and lifecycle as a simulated Maintenance worker.

## 4. Actor model

Every actor is explicit and visible.

### Real actors

Examples:

- Michael
- real staff users
- approved family contacts
- real residents
- real admins/operators

Real actors authenticate normally and their actions are marked
`actor_type=real-human`.

### Simulated actors

Initial mock community roles should include:

- resident
- nursing/care staff
- maintenance
- housekeeping
- transportation
- kitchen/dining
- activities/programs
- front desk/administration
- leadership/admin
- approved family contact where useful

Simulated actors have stable IDs, roles, departments, shifts and behavior
profiles. They are never presented as real people.

### Mixed operation

A simulation can intentionally mix both kinds of actors.

Example:

1. simulator creates a resident sink-leak request;
2. simulated front desk routes it;
3. Michael is scheduled as the real Maintenance worker;
4. Michael claims and completes it in the normal workspace;
5. the simulator observes the real completion receipt and moves on.

This mixed mode is a first-class acceptance target.

## 5. Simulation clock and controls

The operator needs visible controls for:

- start
- pause
- resume
- stop
- reset simulated data only
- normal speed
- accelerated time
- step one event
- schedule/unschedule actors
- switch a role from simulated to real
- inspect current queue / next due actions
- inspect receipt stream
- filter by resident / department / actor / workflow
- replay a scenario from a known starting point

Stopping the simulator stops new simulated actions. It must not erase history.

## 6. Scenario engine

Scenarios should generate ordinary community operations, not scripted demos.

Initial scenario families:

- resident asks for restroom assistance;
- resident reports sink leak;
- resident asks what is for dinner;
- kitchen menu is due but missing;
- activities schedule arrives;
- transportation request with appointment time;
- front-desk callback request;
- housekeeping request;
- resident asks later for request status;
- family contact attempts an allowed interaction;
- room light / thermostat / TV control against simulated devices.

The simulator must also intentionally create operational friction:

- staff does not respond;
- wrong department receives a request;
- duplicate request;
- email delivery failure;
- missing menu;
- stale information;
- staff shift ends before completion;
- device command fails;
- ambiguous resident wording;
- resident corrects Aria;
- provider reports delayed/bounced/failed;
- network/service interruption where safe to simulate.

The expected result is not that every scenario succeeds. The expected result is
that CAOSCare remains truthful, traceable and recoverable.

## 7. Visible Live Operations surface

Michael must be able to **watch it run**.

The first operator surface should show at minimum:

- simulation RUNNING / PAUSED / STOPPED state;
- simulated time and speed;
- current residents/actors on shift;
- real vs simulated badge on every actor;
- active requests by department;
- actions happening now;
- next scheduled actions;
- failures / blocked items;
- receipt/event stream;
- click-through from receipt → originating request → actor → resulting state;
- controls to pause, step, resume and take over a role.

No terminal should be required for normal simulator operation.

## 8. Truth and privacy boundaries

- Simulated and real data must be unmistakably distinguishable.
- Simulation reset can never delete real resident/staff data.
- Public/demo mode cannot expose real resident information.
- A simulated provider result cannot be presented as a real delivery/call/device result.
- Real provider actions require the same permissions and receipts as normal operation.
- Safety-critical care decisions remain human-supervised.

## 9. Implementation sequence

### SIM-0 — Receipt/provenance spine

Before autonomous simulation expands, prove that every simulator-generated
state change creates a durable, origin-linked receipt.

Acceptance:
- one request can be traced from origin through every status transition;
- receipt chain identifies every actor;
- no orphan state change is accepted as complete.

### SIM-1 — Minimal actor scheduler

Implement stable simulated actors, role/department assignment, shifts and a
small deterministic scheduler.

Acceptance:
- start/pause/resume;
- one simulated resident;
- one simulated staff actor;
- one request moves through the canonical lifecycle.

### SIM-2 — Live Operations UI

Make the simulation visible and controllable without SSH.

Acceptance:
- operator watches events live;
- pauses;
- steps one event;
- resumes;
- drills from event to receipt and originating object.

### SIM-3 — Mixed real + simulated staffing

Allow a role/shift to be assigned to a real logged-in user.

Acceptance:
- simulated resident creates a task;
- real Michael is scheduled into the responsible department;
- Michael receives/claims/completes the task through normal UI;
- simulator recognizes the real receipt and continues.

### SIM-4 — Department expansion

Add Nursing, Maintenance, Front Desk, Transportation, Kitchen, Activities,
Housekeeping and Admin scenarios one at a time.

Each new department requires canonical lifecycle evidence and receipt coverage.

### SIM-5 — Communications + room/device simulation

Exercise email/notification/calling/device contracts with explicitly simulated
adapters until real provider/hardware acceptance is available.

## 10. Definition of done

The simulator is useful when Michael can open CAOSCare, press **Start**, watch a
believable community operate, pause it, inspect exactly why anything happened,
take over a staff role himself, complete work through the normal CAOSCare UI,
and see the simulator continue from the resulting real state.

It is not done if:

- agents act without receipts;
- actions cannot be traced to origin;
- simulation has its own hidden business logic/state universe;
- Michael needs a terminal to understand what happened;
- simulated and real actors/data are ambiguous;
- an agent can silently modify state;
- "done" depends on agent self-report rather than system evidence.
