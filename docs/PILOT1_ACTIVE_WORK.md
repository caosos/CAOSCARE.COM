# CAOSCare Pilot 1 Active Work

Target: 2026-10-10

Integration branch: `integration/2026-09-27`
Integration SHA: `7ae91bc` (last code state). Workers branch from the current tip of `origin/integration/2026-09-27`, which adds only documentation on top of it.
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
| A | Nursing / care requests | `pilot/nursing` | `~/CAOSCARE-LANE-NURSING` | Unassigned. Core loop already integrated at `7ae91bc` (see checklist Phase 3 Nursing); remaining gaps are shared-core requests SC-1, SC-2 below. | Nursing queue use of `DepartmentQueue.jsx` on `/staff` and the Admin Nursing tab; nursing-specific workflow and acceptance tests | StaffTask/request model, receipts, notifications, roles, Aria tool contracts, `DepartmentQueue.jsx` / `RequestHistoryDialog.jsx` (shared with Lane B) |
| B | Maintenance | `pilot/maintenance` | `~/CAOSCARE-LANE-MAINTENANCE` | Unassigned. Next checklist task. | `MaintenanceWorkspace.jsx`, `MaintenanceWorkOrderForm.jsx`, maintenance-specific lifecycle/UI (claim/assign/start/notes/time/complete), maintenance acceptance tests | Same as Lane A; `DepartmentQueue.jsx` is shared with Nursing, so changes to it go through Lane E |
| C | Front desk / transportation | `pilot/frontdesk-transport` | `~/CAOSCARE-LANE-FRONTDESK` | Unassigned | Front desk workspace, non-call front desk requests and callbacks, transportation driver/vehicle/request/assignment lifecycle, domain acceptance tests | Request model, receipts, notifications; calling is Lane F |
| D | Dining / activities / housekeeping | `pilot/community-services` | `~/CAOSCARE-LANE-SERVICES` | Unassigned | Kitchen/menu, activities/programs, housekeeping UI and workflows, domain acceptance tests | Inbound email infrastructure (Lane F / E), request model |
| E | Shared core / integration contracts | `pilot/shared-core` | `~/CAOSCARE-LANE-SHARED` | Unassigned | StaffTask/request schema and lifecycle, shared statuses, receipts/history, notification routing, permissions/roles, shared API contracts, shared UI primitives (incl. `DepartmentQueue.jsx`, `RequestHistoryDialog.jsx`), common Aria operational tools, migrations used by several lanes | Changes only on a concrete request from an active lane; no speculative redesign |
| F | Communications / calling | `pilot/communications` | `~/CAOSCARE-LANE-COMMS` | Unassigned | Inbound/outbound email provider config and code gaps, department notifications delivery, call lifecycle, SIP/PBX/Aria phone bridge, front desk/family call receipts | Request/status changes coordinate with Lane E |
| Coord | Integration coordinator | `integration/2026-09-27` | `~/CAOSCARE-INTEGRATION` | This checkout | This file, the authoritative checklist, merge order, whole-system tests, localhost:3000 | Everything, read-only except integration merges |

Pending coordinator item: merge `wip/public-capability-panels` (`0985ae5`, Michael-accepted panel pattern, incl. the Therapy/Beauty Shop image punch list) into integration, then point localhost:3000 back at the integration checkout.

## Shared core requests

| ID | From | Requirement | Reason | Consumers | Status |
|---|---|---|---|---|---|
| SC-1 | Lane A (nursing acceptance 2026-09-28) | Status changes append a receipt instead of updating the last one in place (`receipts.py::update_receipt_status`) | History shows "task assigned · completed" as one entry | Nursing, Maintenance, Front desk, reports | Open |
| SC-2 | Lane A | Timestamped note history on a request (the single `notes` field is overwritten by completion notes; note edits create no receipt) | Progress notes are lost on completion | Nursing, Maintenance | Open |

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
