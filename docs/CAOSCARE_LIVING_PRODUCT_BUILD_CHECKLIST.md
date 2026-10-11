# CAOSCare — Living Product Build Checklist

Updated: 2026-10-10 (owner direction, America/Chicago).

This is the owner-facing product build and progress tracker for the Care Operations build. Canonical owner direction: [Issue #129](https://github.com/caosos/CAOSCARE.COM/issues/129). Detailed historical evidence remains in [PILOT1_EXECUTION_CHECKLIST.md](https://github.com/caosos/CAOSCARE.COM/blob/integration/2026-09-27/docs/PILOT1_EXECUTION_CHECKLIST.md). This file controls current phase, active task, milestones, ETA, blockers, and the reporting contract.

**Do not mark a feature DONE because code exists or an agent says it is done.** Track these states separately:

- **PLANNED** — requirement captured; no accepted implementation.
- **IMPLEMENTED** — code exists at an exact commit.
- **TESTED** — automated checks passed with a receipt.
- **DEV_ACCEPTED** — intended user completed the workflow in the development runtime with receipt/provenance evidence.
- **LIVE_VERIFIED** — the deployed environment was exercised successfully and the exact deployed SHA is recorded.
- **READY_FOR_OWNER_REVIEW** — the whole bounded section meets its written acceptance criteria and is presented to Michael.
- **OWNER_ACCEPTED / DONE** — Michael inspected the completed section and explicitly approved it.
- **BLOCKED** — a named dependency prevents the next acceptance gate.
- **PARKED** — deliberately outside the active lane.

## Checklist marks and owner approval

- `[ ]` — not completed.
- `[~]` — work or evidence exists, but the item/section is not owner-approved DONE.
- `[!]` — blocked by a named dependency.
- `[x]` — Michael has reviewed and approved the completed item/section.

Existing evidence may support IMPLEMENTED, TESTED, DEV_ACCEPTED, or LIVE_VERIFIED without making the section `[x]`. The final checkmark is the owner acceptance record.

## Completion/update protocol

This protocol applies to every bounded build item, fix, workflow, and section.

1. **Select from the living checklist.** Record the active item, expected acceptance, branch/PR, dependencies, and ETA range before or when work begins.
2. **Build without routine permission stops.** Implementation, tests, integration, deployment, restarts, repair, and verification continue within existing authority.
3. **At every meaningful completion, update records before advancing.** A meaningful completion is a finished bounded task, accepted fix, merged PR, deployment, or completed acceptance case—not every keystroke or tiny commit.
4. **The completion update must record:** exact commit/PR/deployed SHA; tests; development and live acceptance; receipt IDs/provenance; changed checklist item; blocker if any; next bounded task; updated ETA; and whether owner review is ready.
5. **Update the existing sources of truth together:** this checklist, the active issue/queue, the applicable project-state or acceptance receipt, and PR/commit links. Do not create an unlinked parallel status record.
6. **Preserve history.** Do not delete prior DONE entries, failures, blockers, owner decisions, or superseded evidence. Append or clearly supersede with a dated reason.
7. **Section gate:** when every required item in a section meets its acceptance criteria, mark the section **READY_FOR_OWNER_REVIEW** and present the actual usable workflow to Michael with the exact URL/environment and a concise evidence summary.
8. **Michael reviews the completed section.**
   - If Michael approves it, record the approval date and evidence, change the section/items to `[x]`, mark **OWNER_ACCEPTED / DONE**, and advance to the next section.
   - If Michael does not approve it, record the punch list, keep the section `[~]`, and make the first correction the active task.
9. **No silent advancement.** A section is not DONE and is not checked off solely because code, tests, a PR, a merge, or a deployment exists.

## No-idle execution protocol

- An agent that finishes a bounded task must produce its completion receipt and accept the next eligible task immediately.
- An agent that becomes blocked must record the exact blocker and take another compatible, authorized task.
- The coordinator keeps the next bounded task prepared before the current task finishes.
- Idle is permitted only when every authorized task is blocked, unsafe, conflicting, or awaiting a genuine owner decision; the reason must be recorded.
- No invented busywork, duplicate worker, duplicate queue, or conflicting edit is allowed merely to keep an agent occupied.
- GitHub activity is not a process heartbeat. The EliteDesk local coordinator/watchdog must enforce the five-minute idle-detection and next-task handoff target and publish timestamped receipts.
- The hourly cloud supervisor is a backup reconciliation layer; PR Watch handles matching GitHub PR events. Neither is represented as a five-minute host watchdog.

## Current build control

- **Current phase:** 3/7 — Care Operations workspaces.
- **Today’s active engineering task:** make the Transportation staff workspace usable end to end.
- **Control issue:** [#129](https://github.com/caosos/CAOSCARE.COM/issues/129).
- **Active review:** [PR #130](https://github.com/caosos/CAOSCARE.COM/pull/130).
- **Integration branch:** `integration/2026-09-27`.
- **Product-code baseline at reconciliation:** `cf3500ea538d36541d56a7b8cb7f3369806ba43b`; later integration commits in this work block are documentation/control receipts only.
- **Transportation branch/head:** `agent/transport-workspace-workable` at `21b2261f021d152181c94d8c95d006c533b18529`.
- **Branch relation:** diverged from integration and requires refresh before runtime acceptance; re-check the exact ahead/behind count immediately before merging because the living-control documentation advances the integration tip.
- **Accepted state:** IMPLEMENTED; focused frontend TESTED; frontend production build passed; Python compile passed.
- **Not yet accepted:** Mongo-backed lifecycle test, development browser flow, receipt inspection, integration merge, main promotion, Linode deployment, and live browser verification.
- **Current live worker heartbeat:** not provable from GitHub alone. Recent code and PR activity are proven; a running Claude process is not.
- **Owner decision required now:** none.

### Exact current sequence

1. Refresh PR #130 onto current integration and resolve any conflicts.
2. Run the extended Transportation lifecycle test and the full backend gate on the EliteDesk integration runtime.
3. Restart the necessary development services.
4. Browser-test as Transportation staff: create → open details → change → cancel → inspect receipt IDs.
5. Browser-test an active trip: Departed → Completed → inspect receipt IDs.
6. Merge the accepted slice into integration.
7. Run the integration regression gate.
8. Promote the verified release to `main`, deploy the exact SHA to Linode, and perform live browser verification.
9. Update this checklist, Issue #129, and the release receipt with the actual result.

**ETA for this bounded slice:** 3–6 focused engineering hours after an EliteDesk worker/runtime is available. Confidence: medium. The estimate includes refresh, tests, browser acceptance, merge, deploy, and verification; it expands if branch conflicts or runtime failures are found.

## What “usable” means

A Care Operations workflow is usable only when the intended person can perform it without SSH or developer knowledge:

```text
resident / family / staff request
→ canonical record
→ correct department queue
→ staff action
→ truthful status update
→ resident/admin visibility
→ durable receipt with provenance
```

## Phase 1 — Core platform, identity, governance, and truth

Current status: **TESTED / partially DEV_ACCEPTED; not globally LIVE_VERIFIED.**

- [~] Canonical resident, staff, department, request/task, actor, and receipt structures exist.
- [~] Role and department access boundaries exist and have automated coverage.
- [~] Append-only lifecycle/history and provenance architecture exist.
- [~] Real and simulated records are structurally distinguishable.
- [~] Operations Simulator can exercise canonical task services rather than a separate fake business-logic universe.
- [~] Verify every active product surface reads/writes the canonical records; no parallel demo-only operational stores.
- [ ] Verify backup/restore, data retention, audit export, and facility isolation against the current runtime.
- [ ] Record one current release-wide security and permission acceptance pass.
- [ ] Record exact LIVE_VERIFIED runtime and SHA.

Milestone: one trustworthy shared foundation for all departments.

## Phase 2 — Core requests, service tickets, routing, and lifecycle

Current status: **Nursing and Maintenance DEV_ACCEPTED locally; cross-department completion incomplete.**

### Nursing / care

- [~] Request creation, department routing, queue, claim, acknowledge, start, notes, complete, history, receipts, and truthful resident status — DEV_ACCEPTED on the integration development path.
- [ ] Re-run the complete workflow on the current release candidate and record LIVE_VERIFIED evidence.
- [ ] Add explicit reassignment, unable-to-complete, escalation, and supervisor review acceptance where required.

### Maintenance / service tickets

- [~] Request/work order, queue, assignment, progress, notes, time spent, completion, resident status, history, and receipts — DEV_ACCEPTED on the integration development path.
- [ ] Re-run the complete workflow on the current release candidate and record LIVE_VERIFIED evidence.
- [ ] Verify priority, category, location/asset, photos/attachments, parts/costs, vendor handoff, reopen, and preventive-work paths.

### Shared lifecycle

- [~] Pending → claimed/assigned → acknowledged → in progress → completed lifecycle exists.
- [~] Status truth avoids claiming a worker is coming unless system evidence supports it.
- [~] Front desk can create and follow requests; full normal-work acceptance remains incomplete.
- [~] Admin can inspect cross-department work and history; every department has not been walked.
- [ ] Confirm cancellation, rejection, reschedule, duplicate, reopen, overdue, escalation, and supervisor override across supported departments.
- [ ] Mobile/desktop accessibility acceptance for staff lifecycle actions.

Milestone: every service request is actionable, traceable, and truthfully visible.

## Phase 3 — Care Operations workspaces (ACTIVE)

Current status: **ACTIVE. Transportation is the current bounded slice.**

### Transportation — current task

- [~] Calendar, Day/Week, My rides/All rides, Completed, History, ride log, JSON/CSV export, and receipt-backed lifecycle exist in code.
- [~] PR #130 implements Transportation staff authority to create, assign, change, cancel, and open trip details.
- [~] Focused frontend tests passed: 3 suites / 3 tests.
- [~] Frontend production build passed; changed Python modules compile.
- [~] Refresh PR #130 onto current integration.
- [ ] Run Mongo/FastAPI lifecycle test.
- [ ] Configure acceptance drivers and vehicles in clearly labeled test data.
- [ ] DEV_ACCEPT create → open → change → cancel → receipt inspection.
- [ ] DEV_ACCEPT Departed → Completed → receipt inspection.
- [ ] Merge integration and run full gate.
- [ ] Promote/deploy and LIVE_VERIFY the workflow.

### Front desk and administrative communication

- [~] Resident directory, request queue, callback/request handling, communications views, and status lifecycle exist in part.
- [ ] One unified inbox for requests, messages, callbacks, approvals, and failed deliveries.
- [ ] Create/assign/reassign/close/reopen from the workspace with truthful status and receipts.
- [ ] Shift notes, handoff, announcements, internal messages, read/acknowledge state, and searchable history.
- [ ] Browser acceptance by a front-desk role and an administrator.

### Dining / menus

- [~] Menu intake, review, publish, and resident lookup exist in part.
- [ ] Real correction propagation, version history, dietary/allergen fields, meal changes, and resident-facing confirmation.
- [ ] Live inbound source acceptance belongs to Phase 5.

### Activities / programs

- [~] Schedule intake, publish, Today view, and Aria lookup exist in part.
- [ ] Registration, attendance, capacity/waitlist, cancellation, transport link, reminders, and resident preferences.
- [ ] Staff and resident browser acceptance.

### Housekeeping

- [~] Request/task, queue, assignment, progress, completion, and receipt paths exist in part.
- [ ] Room/area schedule, recurring work, inspection, supplies/linen, unable-to-complete, and supervisor review.
- [ ] Staff browser acceptance.

### Therapy and appointments

- [ ] Therapy provider/discipline, appointment, recurrence, location, transport need, attendance, cancellation/reschedule, notes/status, and resident-facing schedule.
- [ ] Permission boundaries for operational versus clinical information.
- [ ] Calendar conflict detection and linked transportation request.
- [ ] Staff and resident browser acceptance.

### Alerts / escalation

- [!] Canonical state model is unresolved; historical evidence records competing implementations.
- [!] Automatic timer/rule behavior is not accepted.
- [ ] One escalation model, policy editor, acknowledgements, timers, fallback, receipts, and acceptance test.

Milestone: each department has a normal-work workspace, not a dead demo panel.

## Phase 4 — Scheduling, records, resources, and coordinated calendars

Current status: **PARTIAL / not accepted as a complete system.**

- [~] Transportation calendar and ride log exist; current workspace correction is in Phase 3.
- [ ] Real drivers, vehicles, capacity, availability, service status, assignment, conflicts, and recurring runs.
- [ ] Resident appointment calendar linking therapy, medical appointments, activities, dining events, and transportation.
- [ ] Staff schedules, department coverage, handoffs, absence/substitution, and assignment visibility.
- [ ] Resource calendars for rooms, vehicles, equipment, and shared spaces.
- [ ] Conflict warnings, reminders, cancellation/reschedule propagation, and receipt history.
- [ ] Daily/weekly printable and exportable schedules.
- [ ] DEV_ACCEPT and LIVE_VERIFY each calendar from its intended role.

Milestone: one coherent schedule rather than disconnected department calendars.

## Phase 5 — Communications, family, email, SMS, and phone

Current status: **internal plumbing partially TESTED; real external delivery/calling not LIVE_VERIFIED.**

- [~] Admin communications and notification delivery/status views exist.
- [~] Provider states distinguish queued/logged/sent/delivered/failed where evidence exists.
- [~] Inbound email webhook, allowlist, parsing, review, and mock-provider tests exist.
- [ ] Configure verified domain, webhook, API keys, real inbound addresses, sender allowlists, and department destinations.
- [ ] Real inbound menu email → review → publish.
- [ ] Real inbound activities email → review → publish.
- [ ] Real outbound Nursing, Maintenance, Transportation, Front Desk, and Admin delivery with delivery/bounce receipts.
- [ ] Resident/family contact directory, permissions, preferred channel, message history, and opt-in/opt-out.
- [ ] Family updates and reply workflow without exposing unrelated resident information.
- [ ] SMS delivery and failure acceptance.
- [ ] Front-desk and approved-family voice calling with requested/dialing/connected/unanswered/failed/ended states and receipts.
- [ ] No delivery or connection claim without provider/runtime proof.

Milestone: communication actually reaches the intended person and comes back into the same record.

External dependency: provider accounts, domain/DNS, real addresses/numbers, and approved contacts. Estimate after configuration is available: 1–3 focused days per external service.

## Phase 6 — Pilot operation, reliability, room integration, and accessibility

Current status: **PARTIAL; broad voice work is PARKED while Care Operations is active.**

- [~] Room 214 home test proves portions of voice, lights, and local workflow; it is not a facility production pilot.
- [~] Demo room is synthetic and must stay visibly separate from real resident records.
- [ ] Select the real pilot community/room(s), network, resident identity, staff roster, department destinations, permissions, and hardware.
- [ ] Autostart, reboot recovery, network interruption/recovery, service health, backup, restore, rollback, and monitoring.
- [ ] One real resident request through staff completion and resident follow-up.
- [ ] One real transportation workflow.
- [ ] One real communication workflow.
- [ ] One real room-control workflow with hardware read-back.
- [ ] Accessibility: low vision, hearing assistance, touch targets, keyboard use, mobile staff use, clear language, and no color-only status.
- [ ] Ordinary operation without SSH babysitting.
- [ ] Repeat the installation in a second room from documented provisioning.

Milestone: one room and its staff workflows operate reliably, then reproduce in room two.

## Phase 7 — Release, deployment, and live acceptance

Current status: **AUTHORIZED; current Care Operations release not yet executed or LIVE_VERIFIED.**

Owner authorization permits verified CAOSCare work to proceed through integration, `main`, Linode deployment, necessary service restarts, testing, repair, and continued bounded development without routine permission stops.

- [ ] Complete the active slice's implementation/test/DEV_ACCEPTED gates.
- [ ] Merge accepted work into `integration/2026-09-27`.
- [ ] Run the full integration regression gate and record results.
- [ ] Create the exact release candidate and change summary.
- [ ] Merge/promote the verified candidate to `main`.
- [ ] Deploy the exact `main` SHA to Linode.
- [ ] Verify health, authentication, permissions, the active workflow, responsive UI, receipts, and rollback path.
- [ ] Record deployed SHA, time, operator, commands/actions, test cases, receipt IDs, failures, repairs, and final verdict.
- [ ] Update public capability claims only after LIVE_VERIFIED acceptance.

Milestone: code is not merely present; the deployed product is usable.

## Milestone schedule

| Milestone | Acceptance result | Current state | Evidence-based estimate |
|---|---|---|---|
| M0 — Build control | Living checklist, current task, gates, ETA, and reporting contract in GitHub | COMPLETE with this file | Complete |
| M1 — Transportation usable | Staff creates/opens/changes/cancels and completes trips with receipts in the deployed app | ACTIVE | 3–6 focused hours after EliteDesk runtime is available |
| M2 — Core Care Operations loop | Nursing, Maintenance, Front Desk/Admin, and shared service-ticket lifecycle re-accepted on current release | PARTIAL | 2–4 focused workdays after M1 |
| M3 — Coordinated schedules | Transportation + therapy/appointments + resident/staff calendar links accepted | PARTIAL | 3–6 focused workdays after M2 |
| M4 — Remaining departments | Dining, Activities, Housekeeping, Admin/reporting, alerts/escalation usable | PARTIAL / some planned | 5–10 focused workdays |
| M5 — Real communications | Email, then SMS/phone, with real delivery/call receipts | BLOCKED on provider configuration | 1–3 focused days per service after configuration |
| M6 — Pilot acceptance | One real room + staff + communications + recovery; then repeatability | NOT STARTED as a complete gate | 3–5 focused workdays after dependencies |
| M7 — Release verified | Exact SHA on Linode, live workflow accepted, release receipt recorded | NOT STARTED for current slice | 0.5–1 focused day per accepted release |

**Current honest overall position:** the foundation is substantial, and Nursing/Maintenance have local end-to-end evidence. The product is not yet release-ready because Transportation is under correction, the other department workspaces are incomplete or unaccepted, external communications are not live, and the full pilot/release gate has not passed.

**Overall planning range:** approximately 2–4 focused engineering weeks for the broader Care Operations product slice, plus calendar time for provider/hardware access. This is a planning range, not a promise; each milestone will replace it with actual cycle-time evidence.

## Owner-facing reporting contract

For every meaningful task completion, update this checklist and the active queue/issue atomically where authorized. Record:

- owner requirement and task/issue/PR;
- active phase and milestone;
- exact base, branch, implementation SHA, integration SHA, main SHA, and deployed SHA where applicable;
- files changed;
- automated test receipt;
- development browser acceptance;
- live acceptance;
- runtime/service restarted;
- receipt IDs and provenance;
- blocker and who/what can remove it;
- next bounded task;
- ETA range, assumptions, and confidence;
- whether an owner decision is actually required.

Do not report “built,” “done,” or “live” as interchangeable words. State exactly: IMPLEMENTED, TESTED, DEV_ACCEPTED, LIVE_VERIFIED, READY_FOR_OWNER_REVIEW, or OWNER_ACCEPTED / DONE.

## Autonomous build rule

Continue through bounded tasks without asking Michael for routine permission. Merge, deploy, restart, test, repair, and continue when the defined gates pass. The normal approval stop is when a complete section reaches READY_FOR_OWNER_REVIEW: present it to Michael, record his approval or punch list, then check it off and advance. Also stop for a genuine owner decision such as new spending, destructive loss of real data, a material product-direction choice, unavailable credentials/account access, or an irreversible external commitment.

Permanent law: **No action without a receipt. No receipt without provenance.**
