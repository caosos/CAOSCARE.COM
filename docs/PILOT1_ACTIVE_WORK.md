# CAOSCare Pilot 1 Active Work

Target: 2026-10-10

Integration branch: `integration/2026-09-27`
Integration SHA: `6d1ffa4` (last code state; Shared Core + Maintenance merged). Workers branch from the current tip of `origin/integration/2026-09-27`.
Coordinator: the Claude Code session in the protected integration checkout `~/CAOSCARE-INTEGRATION` on the EliteDesk
Last updated: 2026-09-28

This is the short-lived coordination map for parallel Pilot 1 work.
[`PILOT1_EXECUTION_CHECKLIST.md`](PILOT1_EXECUTION_CHECKLIST.md) remains the authoritative tracker; only the coordinator marks checklist items `[x]`, after accepted integration.

**Rule:** before modifying code, every parallel agent reads this file and identifies:

- its assigned domain (lane)
- its branch and worktree
- its owned files and modules
- its shared dependencies
- other agents touching adjacent systems

No two agents independently redesign the same shared contract.

---

## Lanes

| Lane | Domain | Branch | Worktree | Owner / status | Owned (may modify) | Shared dependencies (read, do not redesign) |
|---|---|---|---|---|---|---|
| A | Nursing / care requests | `pilot/nursing` | `~/CAOSCARE-LANE-NURSING` | Unassigned. Core loop integrated at `7ae91bc`; SC-1/SC-2 history fixes integrated at `3249fcd`. Blocked on SC-3 (Aria status after a claim). | Nursing queue use of `DepartmentQueue.jsx` on `/staff` and the Admin Nursing tab; nursing-specific workflow and acceptance tests | StaffTask/request model, receipts, notifications, roles, Aria tool contracts, `DepartmentQueue.jsx` / `RequestHistoryDialog.jsx` (shared with Lane B) |
| B | Maintenance | `pilot/maintenance` | `~/CAOSCARE-LANE-MAINTENANCE` | **Integrated at `6d1ffa4`** 2026-09-28 (`51deae0`: resident sink-leak acceptance test incl. a strict xfail for SC-3). Remaining: SC-3, SC-4, SC-5. | `MaintenanceWorkspace.jsx`, `MaintenanceWorkOrderForm.jsx`, maintenance-specific lifecycle/UI (claim/assign/start/notes/time/complete), maintenance acceptance tests | Same as Lane A; `DepartmentQueue.jsx` is shared with Nursing, so changes to it go through Lane E |
| C | Front desk / transportation | `pilot/frontdesk-transport` | `~/CAOSCARE-LANE-FRONTDESK` | Reworked 2026-09-28 on integration `a95acbe` (see PROJECT_STATE "Lane C rework"): every ride step goes through `task_history.update_task_with_history` (requested / re-requested / booked / not booked / changed / departed / completed / cancelled); history shown with the shared `RequestTimeline`. Waiting on SC-6, SC-7 (not yet available; nothing consumed). Ready for coordinator review. | Front desk workspace, non-call front desk requests and callbacks, transportation driver/vehicle/request/assignment lifecycle, domain acceptance tests | Request model, receipts, notifications; calling is Lane F |
| D | Dining / activities / housekeeping | `pilot/community-services` | `~/CAOSCARE-LANE-SERVICES` | Handed off 2026-09-27 (needs SC-9, CM-1). | Kitchen/menu, activities/programs, housekeeping UI and workflows, domain acceptance tests | Inbound email infrastructure (Lane F / E), request model |
| E | Shared core / integration contracts | `pilot/shared-core` | `~/CAOSCARE-LANE-SHARED` | SC-1 + SC-2 (`a6230cb`) **integrated at `3249fcd`** 2026-09-28. Open: SC-3 (truth defect, highest), SC-4, SC-5, SC-6, SC-7, SC-8, SC-9 below. | StaffTask/request schema and lifecycle, shared statuses, receipts/history, notification routing, permissions/roles, shared API contracts, shared UI primitives (incl. `DepartmentQueue.jsx`, `RequestHistoryDialog.jsx`), common Aria operational tools, migrations used by several lanes | Changes only on a concrete request from an active lane; no speculative redesign |
| F | Communications / calling | `pilot/communications` | `~/CAOSCARE-LANE-COMMS` | In progress: email delivery truth done; calling awaits Michael's decisions D1–D8 (`docs/PILOT1_COMMUNICATIONS.md` on the lane). Needs SC-8. | Inbound/outbound email provider config and code gaps, department notifications delivery, call lifecycle, SIP/PBX/Aria phone bridge, front desk/family call receipts | Request/status changes coordinate with Lane E |
| G | Demo kiosk / resident experience | `pilot/demo-kiosk` | `~/CAOSCARE-LANE-DEMO-KIOSK` | Unassigned (created 2026-09-28, priority). Requirement and acceptance: checklist section "PRIORITY — Demo kiosk command-to-visual state". Branch from the integration tip that contains this row (`dc3e9ee` code state + docs). | Demo kiosk room visual and its live state display, demo device set-up (simulated/`mock` adapter), typed input on the kiosk, DEMO RESET, demo acceptance tests | Aria room-control tool contracts and `/devices/public/room/{room}/command` (use as-is; changes go through Lane E), device adapters, Kiosk.jsx shared with the real room, resident requests. Must never change real room/device state |
| Coord | Integration coordinator | `integration/2026-09-27` | `~/CAOSCARE-INTEGRATION` | This checkout | This file, the authoritative checklist, merge order, whole-system tests, localhost:3000 | Everything, read-only except integration merges |

Coordinator log: 2026-09-28 merged `pilot/maintenance` (`51deae0`) at `6d1ffa4` (docs-only conflicts). Merged `pilot/shared-core` (`a6230cb`) at `3249fcd` (log conflicts only); :8092 restarted on the merged code. Earlier: merged `wip/public-capability-panels` (`0985ae5`) at `e70fbce`; Therapy/Beauty Shop placeholders `7a5fbe9`; localhost:3000 serves integration again (proxying /api to :8092). `wip/public-capability-panels` and `~/CAOSCARE-WIP-PANELS` are now merged and can be retired once Michael agrees.

## Shared core requests

| ID | From | Requirement | Reason | Consumers | Status |
|---|---|---|---|---|---|
| SC-1 | Lane A (nursing acceptance 2026-09-28) | Status changes append a receipt instead of updating the last one in place (`receipts.py::update_receipt_status`) | History shows "task assigned · completed" as one entry | Nursing, Maintenance, Front desk, reports | **Done** — integrated at `3249fcd`; browser-verified 2026-09-28 (separate receipts per step) |
| SC-2 | Lane A | Timestamped note history on a request (the single `notes` field is overwritten by completion notes; note edits create no receipt) | Progress notes are lost on completion | Nursing, Maintenance | **Done** — integrated at `3249fcd`; browser-verified 2026-09-28 (three notes kept in order) |
| SC-3 | Lane B (lane-local SC-3) | A claim must count as "seen" for resident status: `aria_operational_state.task_lifecycle` returns `open` for a claimed, unacknowledged task, so `aria_request_status` says "no one has picked it up yet" | **Truth defect.** Re-proven on integration `3249fcd` 2026-09-28 for nursing (`task_f34bfff0a8c8`) and maintenance (`task_e5dd5e5527b5`): after a claim, Aria said "no one has picked it up yet… assigned to <name>" | Every Aria status answer | **Open — highest priority** |
| SC-4 | Lane B (lane-local SC-4) | Spoken summary carries the latest staff note while `in_progress`; history answer names who completed it and the completion note | Minor, not false | Nursing, Maintenance | Open, low |
| SC-5 | Coordinator (2026-09-28) | `realtimeOperationsTools.js:132` tells Aria the latest note has "no timestamp on record", but since SC-2 the backend returns `latest_update_at` (e.g. "today at 8:33 PM"). Also the duplicate reply says "ask #1" while the queue shows "asked 2x" | Aria states something untrue about the record | Every Aria status answer | Open |
| SC-6 | Lane C (lane-local SC-3) | Front desk can claim, assign and note Administration-department requests (`task_assignment.py`, `tasks.py` PATCH notes, `maintenance.js` `canClaim`/`canAssign`, `DepartmentQueue.jsx` `canNote`, `/staff/assignable?department=administration`) | Front desk can't own a callback | Front desk, Admin | Open |
| SC-7 | Lane C (lane-local SC-4) | Skip `reject_unconfirmed_time` for authenticated `source="front_desk"` requests | Staff-entered callback times are rejected (422) | Front desk | Open |
| SC-8 | Lane F (lane-local SC-3) | Pass `related_object_type="task"`, `related_object_id` to `notify_department` at every call site; delete dead `tasks.py::_notify_department` | Per-request delivery status | All departments, history UI | Open |
| SC-9 | Lane D (lane-local SC-3) | Department staff can read the department list (`GET /departments` is admin-only) or the workspace heading gets another label source | Workspace headings show the slug | All department workspaces | Open |
| CM-1 | Lane D → Lane F | `email_inbound.py` activities lane: set `linked_object_id` to the `ingest_id` from `create_schedule_items()` | Link inbound email to its draft batch | Activities | Open |

Shared core work queue (priority order, 2026-09-28): SC-3 claim/status truth · SC-5 note timestamp / ask-count wording · SC-4 latest note in status · SC-6 front-desk claim/assign/note · SC-7 callback-time handling · SC-8 notification/request linkage · SC-9 department-list staff access · CM-1 activity email batch linkage (Lane F). SC-3 and SC-5 are Aria truth defects and go first.

IDs are assigned only here, on the integration branch. Four lanes each filed a different "SC-3" on 2026-09-27/28; they were renumbered above. Before filing, read this table on `origin/integration/2026-09-27` and use the next free number, or file as `SC-?` and let the coordinator number it.

Format for new requests (report to the coordinator; do not implement in a feature lane):

```text
SHARED CORE REQUEST:
- requesting lane
- current branch/SHA
- shared file/module
- exact requirement
- reason
- expected consumers
- tests that require it
```

Shared Core implements the change once. Affected feature branches merge or rebase onto that commit before continuing.
Example: Nursing and Maintenance must not each add their own acknowledgement state; both report the need and consume one shared contract.

---

## Rules

**Branches and worktrees.** Each session gets its own branch and worktree, created from the integration starting SHA above. Before work, report `hostname`, `whoami`, `pwd`, branch, HEAD SHA and `git status --short`. No agent edits another lane's worktree, `main`, Linode, or the integration checkout unless assigned as coordinator.

**Merge train.** Finished work is integrated in an order the coordinator controls: shared-core dependency → feature lane → tests/build → EliteDesk integration → cross-domain regression test → next lane. Inspect dependencies first. Stop at the first regression and fix it before merging anything else. Never merge several branches and test afterwards.

**Definition of done.** A lane is not done because code compiles, unit tests pass, an endpoint exists or a screenshot looks right. The handoff report contains:

1. branch
2. HEAD SHA
3. files changed
4. shared-core changes required
5. tests passed
6. actual workflow acceptance performed
7. known limitations
8. checklist items satisfied (with evidence)
9. migration/config requirements
10. integration instructions

Operational workflows need real lifecycle evidence where practical.

**Checklist.** Workers update their row in this file at handoff and report checklist evidence; they do not mark `[x]` in the checklist. The coordinator updates the checklist after accepted integration.

**Public website.** Marketing does not outrun product truth. Public statuses advance only after acceptance evidence; the public site consumes accepted features and does not redefine backend truth.

**Production.** No worker or coordinator deploys. Release: accepted EliteDesk integration → push GitHub → show Michael the current production SHA, the proposed SHA and the exact commit/file range → Michael explicitly approves → deploy that exact GitHub SHA to Linode → verify production.
