# CAOSCARE Running Facility Testbed

_Last updated: 2026-08-23_

This document defines how CAOSCARE becomes a **running facility**, not a collection of static admin screens.

For conversation/UI shorthand, Michael may call CAOSCARE **the Care app**. This is shorthand, not a repository/product rename unless explicitly decided later.

## 1. Goal

A configured DEMO community should be able to operate continuously enough that Michael can test the building as if staff and residents are actively using it.

The system should produce and process realistic synthetic activity through the same application workflows used by real users.

The acceptance question is not "are there rows in Mongo?"

It is:

**Can Michael run the building from the Care app and watch work enter, route, get acknowledged, progress, complete, notify people, and appear in history?**

## 2. Owner-only Facility Control

Add an obvious owner/admin test control surface, conceptually:

- **Launch demo facility**
- **Pause**
- **Resume**
- **Reset demo activity** (only synthetic/test records, with explicit confirmation)
- simulation state: RUNNING / PAUSED / STOPPED
- current simulated scenario/day context
- recent generated events
- next scheduled synthetic events
- provenance: every generated item clearly marked DEMO / MOCK / simulation

Do not alter the EliteDesk/OS clock. Use an application-level simulation clock/scenario scheduler where accelerated time is useful.

## 3. The demo community must have prerequisites

Do not generate downstream business activity against nonexistent organizational context.

Required baseline:

1. organization/company
2. community/facility
3. departments
4. staff accounts / roles / department assignments
5. Front Desk coverage
6. residents + rooms
7. kiosks/devices where relevant
8. transportation drivers/vehicles if transportation is exercised
9. schedule/activities/menu baseline where relevant

If prerequisites are missing, Launch must say exactly what needs setup rather than silently fabricating detached data.

## 4. Synthetic operational activity

The running facility should create realistic events across separate workflows, using real application boundaries/endpoints wherever practical.

Examples:

### Resident / Aria / requests
- maintenance request
- housekeeping request
- dining/kitchen request
- activity/program question
- Front Desk callback request
- transportation request
- resident follow-up on an existing request

### Department workflow
- new routed task
- acknowledgment
- assignment
- start/in-progress
- completion
- overdue/aging item
- escalation when configured

### Front Desk
- callback item
- transportation needing information
- transportation needing slot/confirmation
- appointment coordination item
- resident lookup/context
- department contact/handoff

### Scheduling / activities
- today's programs
- upcoming program reminders
- resident interest/attendance test activity if/when implemented
- facility event changes

### Transportation
- new request
- needs-information state
- pending/unslotted state
- scheduled run
- driver assignment
- vehicle assignment
- confirmed ride
- in-progress/completed states
- conflict scenario

### Medication reminders / clinical coordination
Current CAOSCARE medication support is a **voice-reminder system**, not an eMAR.

The testbed can safely exercise:
- synthetic medication reminder schedules
- kiosk reminder due events
- reminder spoken/acknowledged history
- missed/unacknowledged reminder test states when intentionally simulated
- clinician visibility into reminder history and resident-related events

For a real facility, authoritative medication orders/administration should integrate with the facility's existing clinical/eMAR source rather than CAOSCARE pretending to replace it without an explicit future product decision.

### Notifications
Exercise the real notification pipeline, but DEMO mode must default to safe destinations/sinks so synthetic activity does not accidentally contact real residents, families, providers, or external recipients.

Where email/SMS/push is configured for demo acceptance, provenance must clearly indicate simulation.

## 5. Deterministic scenarios first

Do not make testing dependent on random noise.

Provide deterministic scenario packs such as:

- Normal morning
- Busy Front Desk
- Transportation-heavy day
- Maintenance backlog
- Clinical/reminder day
- Evening/shift handoff
- Mixed normal day

Optional randomness can be layered on later, but a given scenario + seed should be reproducible so defects can be repeated.

## 6. Event engine rules

Every synthetic event must have:
- event/scenario ID
- facility/community ID
- resident/staff/department IDs where applicable
- timestamp/simulation timestamp
- source/provenance = demo/simulation
- action taken
- resulting durable record IDs
- current status

The simulator must not bypass important business rules merely to make dashboards look busy.

If the real API rejects an action, that is useful test evidence and should be reported rather than silently direct-writing around it.

## 7. Clinician / Clinical workspace target

The existing Clinician Dashboard is a useful analytics surface but is not yet a full clinical operating workspace.

Target direction:

### Clinician overview
- resident search / resident count
- calls, falls, response time, unresolved events
- clinical/relevant alerts
- medication-reminder status and history
- recent resident events
- resident-specific trends
- quick access to resident record

### Resident clinical view
- resident identity / room
- relevant recent events
- current medication **reminders/coordination records** from CAOSCARE
- reminder acknowledgment history
- appointment/schedule items relevant to care
- recent calls / falls / pain / confusion-type events
- notes/context that CAOSCARE legitimately owns
- links to authoritative external clinical system when integration exists

Do not duplicate a full EHR/eMAR merely because other systems contain that data. CAOSCARE should coordinate and surface the information it legitimately owns or receives through integration.

## 8. Staff Care app / tablet workflow

Every staff member who needs CAOSCARE should have a real account and role-appropriate dashboard on the tablet/browser.

Minimum workflow:

- sign in
- community/facility context is known
- role and department are known
- current assigned/open work is visible
- notifications/alerts are visible
- acknowledge / start / complete work as authorized
- resident lookup as authorized
- department workspace access as authorized
- Front Desk workspace for front-desk role
- clinical workspace for clinical role
- transportation workspace for driver/front-desk/authorized role
- actions write accountable history tied to the staff user

Do not expose the entire owner/admin console to every staff member.

## 9. Facility should feel alive in the browser

When the simulator is RUNNING, Michael should be able to open Admin/role dashboards and observe:

- new work appearing over time
- statuses changing
- departments accumulating/clearing work
- Front Desk queue changing
- schedules showing today's actual dated events
- transportation progressing
- reminders becoming due/acknowledged
- notifications being generated
- history/audit showing who/what caused each change

A background simulator that changes Mongo without visible product behavior is not accepted.

## 10. Safe separation from real operation

Simulation must be unmistakable and controllable.

Requirements:
- demo facility or demo mode is clearly labeled
- synthetic residents/staff/events are clearly labeled
- generated activity never masquerades as real resident statements
- no destructive cleanup of real records
- reset targets only records carrying verified simulation provenance
- external notifications disabled/sandboxed by default
- no autonomous medication administration or clinical decision-making

## 11. Architecture constraints

- simulator/event engine separate from UI rendering
- scenario definitions separate from execution engine
- use domain services/endpoints instead of giant direct-DB scripts where important rules exist
- no God files; normal ~300-line handwritten production-code ceiling applies
- deterministic, testable functions
- explicit provenance
- idempotent/repeat-safe scenario setup where practical

## 12. Acceptance milestone

The first meaningful running-facility milestone passes when Michael can:

1. open the owner/community workspace
2. click **Launch demo facility**
3. see the facility enter RUNNING state
4. open Front Desk / Departments / Clinician / Scheduling / Transportation
5. watch pre-defined synthetic events enter and progress through real workflows
6. take actions as a staff user and see them persist
7. pause/resume the simulator
8. inspect the audit/activity history and distinguish every synthetic action from real activity

That is the baseline for calling CAOSCARE a functioning facility testbed.
