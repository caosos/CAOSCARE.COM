# Living Community Simulator Requisition

**Task ID:** `careops-living-community-simulator-001`  
**Status:** AUTHORIZED / WORKING  
**Owner direction:** Michael Chambers, 2026-10-13  
**Coordinator branch:** `feature/living-community-simulator`  
**Requisition branch:** `agent/living-community-requisition`  
**Base:** `origin/integration/2026-09-27` at `4744e0df0c995d8b6250d74d883b4bf4b1617d37`  
**Integration target:** the coordinator branch above, then a reviewable pull request into `integration/2026-09-27`  
**Production/runtime authority:** none; this requisition does not authorize a merge, deployment, service restart, paid provider call, or mutation of a shared/live database

## 1. Owner direction

Build a believable living senior-community simulation inside the Care app, on
its own branch, without interfering with other active Care work. The product
must include workable departments, residents, round-the-clock community
operations, staff shifts and handoffs, resident routines, and an owner/admin
ability to work in department contexts from one authenticated account.

The first burn-in uses 10 residents. The design must scale to the full
community target without replacing the canonical resident, request, task,
department, staff, receipt, schedule, alert, communication, or device systems.

The simulator is an acceptance system for the actual Care app, not an animated
dashboard or a second fake application.

## 2. Factual correction to current status

The historical `RQ-007 Operations Simulator` entry says `DONE (SIM-1..4
accepted)`. That label describes only the accepted thin slices that existed at
the time. It must not be read as proof of a living-community simulator.

What repository evidence currently proves:

- one synthetic resident in the demo room;
- one maintenance simulated worker and one nursing simulated worker;
- two deterministic scenarios: `sink_leak` and `nursing_assist`;
- Start, Pause, Step, Resume and Stop controls;
- a visible run/request receipt stream;
- simulated/real role handoff for one scenario role;
- canonical request/task lifecycle use for those two scenarios.

What it does **not** prove:

- a 10-resident burn-in community;
- a 75-resident, 70-occupied-apartment community;
- a 50-worker roster across all operating departments;
- a persistent 24-hour shift system with clock-in/out and handoff;
- resident routines across days and months;
- safe simulation reset;
- speed control and a durable 90-day run;
- one-login admin Work-as behavior across all departments;
- restart-safe, idempotent community event generation;
- full-department workload and staffing coverage.

For this requisition, the old `RQ-007` result is classified as **thin-slice
foundation accepted; community-scale scope not built**.

## 3. Community targets

These numbers are product simulation targets, not real-world staffing advice or
a claim that one staffing pattern is safe for every community.

| Target | Required value |
|---|---:|
| Apartments | 80 |
| Occupied apartments | approximately 70 |
| Residents at scale | approximately 75 |
| Initial burn-in residents | 10 |
| Simulated workers | 50 |
| Operating clock | 24 hours per simulated day |
| Endurance run | 90 simulated days |

### Initial 50-worker simulation mix

The mix below creates load, handoffs and coverage conditions for product
testing. Communities must configure their actual staffing under their own
leadership, clinical, legal and regulatory requirements.

| Department group | Roster identities | Daily assignments | Scheduled coverage | Simulation intent |
|---|---:|---:|---|---|
| Nursing / Care / medication support | 26 | 16 | 24 hours | Continuous resident assistance and reminder support; no autonomous clinical decisions |
| Dining | 6 | 4 | 05:30–18:30 | Breakfast/lunch/dinner preparation, service and corrections |
| Housekeeping | 4 | 3 | 06:30–18:30 | Scheduled room work with explicit closed-hours behavior |
| Maintenance | 3 | 3 | 24 hours | Planned work, urgent building issues and after-hours response |
| Transportation | 2 | 1 | 06:30–15:00 | Planned rides with explicit closed-hours/on-call behavior |
| Activities | 2 | 1 | 09:00–17:00 | Day programs with explicit closed-hours behavior |
| Front Desk | 5 | 3 | 24 hours | Continuous front-desk/community presence |
| Administration / Leadership | 2 | 1 | 08:00–16:00 | Daytime leadership and coordination work |
| **Total** | **50** | **32** | **Three continuous departments** | |

The 18 roster identities not assigned on a given simulated day are off duty;
the deterministic 90-day projection rotates identities through the 32 daily
assignments. Off-duty status must be displayed explicitly before the staffing
plan is treated as an executed schedule.

Non-24-hour departments must show truthful closed/on-call/unavailable state.
The simulator must not silently invent overnight employees merely to make a
request succeed.

## 4. Required resident and community activity

The simulator must eventually exercise these ordinary routines through the
same canonical records and services used by real people:

- medication **reminder** times and acknowledgements, clearly distinct from
  medication administration or eMAR;
- showers/bathing assistance;
- meals, preferences, refusals and substitutions;
- toileting and transfer assistance requests;
- room checks and resident check-ins;
- housekeeping schedules, supplies, inspections and returns for correction;
- activities, attendance, missed activities and resident choices;
- appointments, reschedules and cancellations;
- transportation requests, booking, departure and completion;
- maintenance requests and planned room/building work;
- front-desk callbacks and family-contact requests;
- shift changes, unclaimed work, blocked work and handoffs;
- resident refusal, correction, later re-request and changed intent;
- safe simulated failures such as unavailable staff, missing information,
  delayed response, duplicate requests and provider/device failure.

Resident schedules are synthetic test inputs. The simulator does not decide
care plans, medication administration, clinical treatment or safe staffing.

## 5. Canonical-world and safety laws

The following rules are acceptance requirements, not implementation
preferences:

1. **No action without a receipt. No receipt without provenance.**
2. Human UI, Aria, simulator actors, schedulers and adapters use the same
   canonical services and domain objects.
3. The simulator may create explicit simulated actors and safe simulated
   adapters; it may not create a parallel task, resident, alert, schedule,
   department, notification or device universe.
4. Synthetic residents live in the canonical resident collection and carry a
   server-set synthetic identity marker. Client input cannot self-declare real
   data synthetic.
5. Simulated workers have stable `sim:` identities, roles, departments,
   shifts and behavior profiles. They are not login-capable `User` accounts.
6. A simulated worker may never act on an unmarked real object.
7. Every generated task/request uses the canonical request and lifecycle
   functions; every run event cites the canonical receipt that proves the
   actual state change.
8. Simulated delivery, call or device results are labeled simulated and never
   presented as real provider/hardware evidence.
9. Pause and Stop prevent new simulated actions but preserve history.
10. An agent's text saying `done` is never completion evidence. Acceptance
    requires durable records, tests and visible behavior.
11. Care behavior remains assistive, advisory and human-supervised. The
    simulator does not confer medical, nursing or emergency authority.

## 6. Owner/admin Work-as identity rule

Michael or another authorized owner/admin keeps one authenticated account.
Work-as changes the department/role context being viewed and acted through; it
does not log the owner in as a fake employee and does not alter the owner
account's durable identity.

Every Work-as action receipt must preserve:

- actual actor ID and name: the authenticated owner/admin;
- `actor_type=real-human` and `identity_basis=authenticated`;
- actual account role and authority, such as `admin_override:owner`;
- selected acting department and acting role as separate context;
- target object and before/after state;
- originating run/workflow and parent receipt where applicable.

The UI must say `Working as <role> · <department>` and offer a clear exit back
to the normal owner/admin command center. It must never say or imply that
Michael is the simulated worker whose queue he is viewing.

Backend authorization remains authoritative. A UI-only department filter is
not sufficient acceptance.

## 7. Reset safety contract

Reset is destructive and is not part of the first implementation slice.
Before it can be enabled, it must satisfy all of these conditions:

1. Stop the selected run before any cleanup action.
2. Produce a dry-run inventory showing exact object types, IDs and counts.
3. Scope every target by server-set synthetic marker and the selected
   `simulation_run_id` or dedicated synthetic-community scope.
4. Refuse the reset if any candidate object lacks the required marker, belongs
   to another run, or resolves to a real resident/staff/device/provider.
5. Never use a blanket collection deletion or room/name-pattern-only match.
6. Preserve receipts and history by default. Closing/archiving simulated work
   is preferred to erasing evidence.
7. If later deletion is explicitly authorized, first preserve an exportable
   manifest and append one reset receipt listing every deleted object ID.
8. Resetting one run cannot touch another run's objects.
9. Automated tests must place real and simulated fixtures side by side and
   prove byte-for-byte that real rows are unchanged.
10. UI confirmation must name the run, scope and object counts. A generic
    `Reset all` control is forbidden.

## 8. Scope and non-scope

### In scope

- deterministic community blueprint and burn-in configuration;
- stable simulated resident and worker identities;
- 24-hour simulation clock, shifts, clock-in/out and handoff events;
- department coverage and truthful closed/on-call states;
- canonical resident routine/request/task lifecycles;
- current/next work visibility in Live Operations;
- pause/resume/step/stop and later speed controls;
- admin Work-as with real-actor/acting-context receipts;
- restart-safe, idempotent event scheduling;
- 10-resident burn-in, then scale and 90-day endurance acceptance;
- safe reset design and later verified implementation;
- automated, API and browser acceptance evidence.

### Explicitly out of scope

- real clinical judgment, care-plan decisions or medication administration;
- using simulated workers as login accounts;
- real email, SMS, telephone or device commands from simulation;
- production/Linode/EliteDesk deployment or restart;
- main/integration merge by a builder;
- paid provider calls;
- real resident/staff data mutation;
- replacing canonical department workflows with simulator-only code;
- hardware, wake-word, Room 214 voice or Aria personality changes;
- broad refactors unrelated to the simulator acceptance gap.

## 9. Branch, worktree and file ownership

The current Work Mode coordinator owns integration on
`feature/living-community-simulator`. Bounded builders use one worktree and one
branch each from the same base. Historical Agent One..Six or Claude lane names
in old coordination documents are not current dispatch authority.

| Current branch | Bounded responsibility | Ownership rule |
|---|---|---|
| `feature/living-community-simulator` | Coordinator integration, conflict resolution and final gates | No builder commits directly here |
| `agent/living-community-requisition` | This requisition only | Owns only `docs/reports/2026-10-13-living-community-simulator-requisition.md` |
| `agent/living-community-blueprint` | Community model/blueprint slice | Own only newly assigned community-definition modules/tests |
| `agent/living-community-staffing` | Worker shifts/coverage slice | Own only newly assigned staffing modules/tests |
| `agent/living-community-routines` | Resident routine/event-planning slice | Own only newly assigned routine modules/tests |
| `agent/living-community-work-context` | Admin Work-as contract/slice | Own only newly assigned work-context modules/tests |

The coordinator must verify each diff before cherry-picking. A builder that
discovers a need to modify a shared file must stop and request ownership rather
than editing it concurrently.

Shared/high-collision files that require coordinator assignment include:

- `backend/models.py`;
- `backend/server.py`;
- `backend/routes/task_lifecycle.py`;
- `backend/routes/resident_requests.py`;
- `backend/routes/departments.py`;
- `backend/simulation/scheduler.py` (already above the normal split threshold);
- `frontend/src/pages/Admin.jsx`;
- `frontend/src/pages/LiveOperations.jsx`;
- `frontend/src/pages/DepartmentQueue.jsx`;
- `docs/PROJECT_STATE.md` and the living trackers.

Prefer new cohesive modules/components under `backend/simulation/` and
`frontend/src/components/simulator/`. Do not materially enlarge the existing
372-line scheduler; extract community clock/event responsibilities.

## 10. Delivery phases and acceptance gates

### P1 — Burn-in foundation

Build the community definition, 10-resident burn-in, 50-worker actor roster,
department coverage view and one canonical resident-to-department workflow.

Acceptance:

- exact deterministic counts: 10 residents and 50 workers;
- stable IDs across repeated load/restart;
- all seven department groups represented;
- scheduled day/evening/night coverage and truthful closed/on-call state;
- simulated workers absent from the real login user collection;
- one scheduled resident event creates one canonical request/task chain;
- the run event cites the canonical action receipt;
- pause/stop prevents the next event;
- state read/restart does not duplicate residents, workers, events or tasks;
- owner-only controls and unmistakable simulated labels;
- zero real provider calls and zero real-row changes.

### P2 — Resident routine engine

Add deterministic recurring plans for meals, reminder-only medication times,
showers, toileting/transfer assistance, room checks, housekeeping, activities,
appointments, transportation, maintenance and family-contact requests.

Acceptance includes due/not-due behavior, refusal, reschedule, cancellation,
duplicate protection, literal resident wording where applicable, and one
canonical receipt chain per state-changing action.

The current medication-reminder route is not approved for simulation until its
mutation/acknowledgement path has proper authorization, receipts and simulation
provenance. P2 must not route around that gap.

### P3 — Worker shift lifecycle and handoff

Add scheduled clock-in, clock-out, delegated responsibilities, workload claim,
handoff and unavailable-worker cases.

Acceptance requires a durable receipt for each shift transition, no worker
acting off shift, open-work handoff without duplicate tasks, and restart-safe
continuation from the canonical state.

### P4 — Admin Work-as

Allow one authenticated owner/admin to enter every department role context and
work the same canonical queue that department staff use.

Acceptance requires backend authorization, visible active context, clean exit,
normal lifecycle actions and receipts retaining the real actor plus acting
role/department context. No impersonation is permitted.

### P5 — Community scale

Expand configuration from 10 to approximately 75 residents in approximately
70 occupied apartments while retaining 50 workers and the 80-apartment
capacity model.

Acceptance requires deterministic provisioning, no room/resident collision,
bounded queue growth, truthful staffing gaps, department filtering and usable
Live Operations performance at target scale.

### P6 — 90-day endurance run

Run 90 simulated days with controllable acceleration, persistent time/event
cursors and safe restart/catch-up.

Acceptance requires:

- deterministic seed and reproducible event ordering;
- no duplicate occurrence after pause, restart or catch-up;
- bounded catch-up rather than an unbounded event flood;
- zero orphan state changes;
- zero simulated actions on real objects;
- zero real provider/device actions;
- complete receipts for actions, refusals and failures;
- end-of-run metrics by resident, worker, department, routine, failure and
  handoff;
- no claim of success based only on process uptime or agent text.

### P7 — Reset, replay and final browser acceptance

Implement the reset contract only after P1-P6 identifiers and evidence are
stable. Prove dry-run, scoped cleanup/archive, history preservation, one-run
isolation and replay from a known seed.

Final browser acceptance covers desktop and 390-pixel layouts for Live
Operations, department work, resident status, owner Work-as, receipt drill-down
and reset confirmation.

## 11. First implementation slice authorized now

The first slice is **P1 burn-in foundation**, not the entire 90-day simulator.
It should deliver the smallest real vertical path that validates the scale
architecture:

1. a configuration-first community blueprint with the numeric targets;
2. 10 stable synthetic resident definitions;
3. 50 stable simulated worker definitions with departments and shifts;
4. coverage validation over a 24-hour clock;
5. a visible community summary in Live Operations;
6. one scheduled routine/request that enters the canonical request/task path,
   is worked by an on-shift simulated employee, and ends with a fully linked
   receipt chain;
7. pause, stop and restart/idempotency proof.

P1 may not claim that routine breadth, Work-as, reset, scale or the 90-day run
are complete. Those remain later gated phases.

## 12. Test and evidence plan

Every concurrent backend test run must use both a unique port and a unique
database. Real-hardware tests remain excluded unless separately authorized.

### Focused backend gate

```bash
cd backend
CAOSCARE_TEST_PORT=<free-port> \
CAOSCARE_TEST_DB=<unique-db> \
./scripts/run_backend_tests.sh -k 'sim_community or sim1 or sim3 or sim4 or sim_provenance'
```

### Full backend gate

```bash
cd backend
CAOSCARE_TEST_PORT=<free-port> \
CAOSCARE_TEST_DB=<unique-db> \
./scripts/run_backend_tests.sh
```

### Frontend focused, full and build gates

```bash
cd frontend
CI=true yarn test --watch=false --runInBand src/lib/__tests__/simulator.test.js <new-test-files>
CI=true yarn test --watch=false --runInBand
CI=true yarn build
```

### Required evidence at each phase boundary

- exact branch and commit SHA;
- exact files changed and production-code line counts;
- focused and full test commands/results;
- API evidence for authorization/refusal and receipt chains;
- browser evidence for the intended human surface;
- exact tested revision and, only if separately authorized, loaded revision;
- cleanup proof for temporary test data;
- explicit list of unfinished phases and blockers;
- cost or `UNKNOWN` when external cost is relevant.

## 13. Known blockers and dependencies

- `backend/simulation/scheduler.py` is already above the normal code-file
  split threshold; community behavior must be extracted into cohesive modules.
- Existing simulator provenance is demo-room scoped. Broader synthetic resident
  scope must be explicit and server-set before community provisioning.
- Existing medication reminder create/delete/ack behavior does not yet provide
  the provenance and authorization required for simulator use.
- Safe reset does not exist for a multi-resident community and cannot be
  inferred from test cleanup helpers.
- Admin already has broad department authority, but an explicit Work-as
  context and provenance contract are not implemented.
- The existing scheduler loop is process-local and revival is triggered from a
  state read. A 90-day run requires durable, idempotent restart/catch-up
  behavior.
- Department workflows differ in maturity. Simulation must expose missing
  canonical capabilities rather than hiding them with simulator-only writes.

These are implementation gaps, not permission to create parallel state.

## 14. Merge and deployment boundary

Builders may commit and push only their bounded branches. The coordinator may
integrate reviewed commits into `feature/living-community-simulator`, resolve
conflicts and run combined gates.

This requisition explicitly does **not** authorize:

- merging the feature branch into `integration/2026-09-27` or `main`;
- merging or closing another active pull request;
- deploying to Linode or the EliteDesk;
- restarting a shared/live CAOSCare service;
- changing Room 214;
- using real provider credentials or incurring paid calls;
- mutating shared/live resident, staff or operational data.

After P1 is integrated and verified on the feature branch, the next safe action
is coordinator review against the P1 acceptance list and creation of a draft,
non-merged pull request/requisition receipt. Later phases proceed only from the
remaining documented acceptance gaps.
