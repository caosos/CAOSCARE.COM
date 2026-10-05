# CAOSCare Pilot 1 Active Work

Target: 2026-10-10

Integration branch: `integration/2026-09-27`
Integration SHA: tip `0f331b7` (2026-10-04; last code state `268963c` — Shared Core SC-1..SC-7, SC-13..SC-15, Maintenance, Demo kiosk, Front desk/transport merged; later commits are docs and the legacy wake-listener re-scope `79699a0`). Workers branch from the current tip of `origin/integration/2026-09-27`.
Coordinator: the Claude Code session in the protected integration checkout `~/CAOSCARE-INTEGRATION` on the EliteDesk
Last updated: 2026-10-04 (Round 5 board)
Recovery snapshot: [`PILOT1_RECOVERY_CHECKPOINT.md`](PILOT1_RECOVERY_CHECKPOINT.md)  
Ready queue: [`PILOT1_READY_QUEUE.md`](PILOT1_READY_QUEUE.md)

This is the short-lived coordination map for parallel Pilot 1 work.
[`PILOT1_EXECUTION_CHECKLIST.md`](PILOT1_EXECUTION_CHECKLIST.md) remains the authoritative tracker; only the coordinator marks checklist items `[x]`, after accepted integration.

The coordinator also owns [`PILOT1_READY_QUEUE.md`](PILOT1_READY_QUEUE.md): approved bounded future work that an idle compatible worker may take. Worker agents never invent work merely because they are idle. Shared-contract dependencies still go through Shared Core, and integration remains one branch at a time with tests between merges.

**Michael's control rule:** “Capture everything. Execute one thing. Finish it. Then move.” Michael should normally receive one active decision/action at a time. Safe independent lanes may still run in parallel.

**Rule:** before modifying code, every parallel agent reads this file and identifies:

- its assigned domain (lane)
- its branch and worktree
- its owned files and modules
- its shared dependencies
- other agents touching adjacent systems

No two agents independently redesign the same shared contract.

---

## Round 5 live board (2026-10-04, Michael: parallel execution; all six agents active)

Current assignments (2026-10-05, Michael): Agent 2 (Claude Two) wake training-method A/B, one-model Okay Sequoia · Agent 3 scenario-aware `latest_run()` fix, then SIM-4 Nursing · Agent 4 SC-8 + SC-9 · Agent 5 RQ-008 storage report + Phase 2 deletion proposal only · Agent 6 stale integration-gate test fixes only. Coordinator watches all lanes, merges one PR at a time, gates each merge and posts the new tip to the affected worker.

GitHub is the communication bus. Every worker: one bounded objective, one branch, one worktree, owned files below, tests, pushed commits, a **draft PR into `integration/2026-09-27`**, no self-merge. The coordinator merges one PR at a time and runs the integration gate between merges. A worker whose base goes stale after a merge refreshes against the new tip and reruns its tests.

PR body (keep current):

```text
OBJECTIVE:
OWNED AREA:
BASE SHA:
CURRENT HEAD:
FILES CHANGED:
SHARED DEPENDENCIES:
TESTS:
ACCEPTANCE:
KNOWN LIMITATIONS:
STATUS:
NEXT:
```

| Agent | Objective | Branch (base `0f331b7` unless noted) | Owned files | Shared — do not change; file a SHARED CORE REQUEST | Status |
|---|---|---|---|---|---|
| Claude Two (Agent 2) | Wake training-method A/B: one-model Okay Sequoia test with TV-dialogue-style hard negatives (batch 1 finished) | `research/wake-phrase-funnel` (based on `main`/firmware line, not integration) | `research/wake-phrase-funnel/`, `firmware/voice-pe-aria/lab/` | anything under `backend/`, `frontend/` | Active, `24ceaff`. Not an integration candidate: it carries the firmware history from `main`; anything for integration comes as a separate reviewed branch. Last verified receipt `772e216` (coordinator PASS 2026-10-04). |
| Agent Three | **Scenario-aware latest run** (follow-up), then **SIM-4 Nursing** scenario (RQ-007); SIM-1/2/3 merged (`1126d8c`, `5567d3e`, `c276a2b`) | `pilot/sim-latest-run-scenario`, then `pilot/sim-4-nursing` (from the current tip) | `backend/simulation/*`, `backend/routes/simulation.py`, `frontend/src/pages/LiveOperations.jsx` + `components/simulator/*`, their tests | `task_lifecycle.py`, `task_actions.py`, `actor_context.py`, `receipts.py`, `resident_requests.py`, `models.py` (call them, never edit) | Assigned 2026-10-04. SIM-4 adds one department scenario at a time (Nursing first), each with canonical lifecycle evidence and receipt coverage (`CAOSCARE_OPERATIONS_SIMULATOR.md` §9 SIM-4). Same scope **until Michael lifts the ENGINEERING_CONTRACT gate:** demo room only (synthetic resident in room `DEMO`, `StaffTask.simulated`), StaffTask lifecycle only; no alerts, escalation or pendant events (gate items 7 and 8 — stale-alert quarantine and canonical escalation — are not implemented). Acceptance = `CAOSCARE_OPERATIONS_SIMULATOR.md` §9 SIM-1. |
| Agent Four | **SC-8 + SC-9** resumed (HA VM recovery audit merged at `c438142`; host changes P1–P3 await Michael) | `pilot/shared-core-sc8-sc9` (from the current tip) | Shared Core: SC-8 — every `notify_department` call site passes the task/receipt link, dead `tasks.py::_notify_department` removed; SC-9 — department staff can read department names | `pilot/communications` prepared part of SC-8 (`aa10645`, not integrated) — note the overlap; simulator files are Agent Three's | Assigned 2026-10-04 |
| Agent Five | **RQ-008 only:** draft PR for the storage report + Phase 2 deletion proposal for Michael (RQ-001 merged at `5bc1f8c`) — no deletion | `docs/rq-008-storage-receipt` (refresh onto the tip) | `docs/reports/2026-10-04-elitedesk-storage-audit.md` | new files only: `backend/demo_continuity.py` (catch-up/progression), a route or startup hook if needed, `backend/tests/test_demo_continuity.py`; calls SIM-1/SIM-2 and canonical services — no edits to `backend/simulation/*`, `task_lifecycle`, `resident_requests`, `notifications`, `models` (SHARED CORE REQUEST instead). Demo room `DEMO` only; real resident data never touched. RQ-008: no further deletion; Phase 2 list for Michael | Assigned 2026-10-04 |
| Agent Six | **Test-only stale-gate fixes** (RQ-009 research `ee8057e` and requirements PR #54 merged) | `tests/stale-gate-fixes` (from the current tip) | `backend/tests/iter10_test.py`, `iter11_test.py`, `test_ops_overview.py` only (port the test changes from `f36351c`/`aa3d2f1`; do not change production code) | everything outside those test files | Assigned 2026-10-04 |

### Merge queue (one at a time; gate between merges)

| # | Candidate | Head | State | Blocker / next |
|---|---|---|---|---|
| ✓ | SIM-1 (Agent Three), PR #49 | `6dc4ea5` | **Merged at `1126d8c`** 2026-10-04 | Gate 240/3/13 (the same 3 stale tests); SIM-1 test 6 passed. `server.py` +2 (router) accepted |
| ✓ | RQ-004 BOM (Agent Five), PR #47 | `e45a840` | **Merged at `42ac6f3`** 2026-10-04 (docs; log conflicts resolved, both sides kept) | Remaining facts need Michael (request at the end of the BOM) |
| ✓ | SC-10/11/12 (Agent Four), PR #48 | `95b4df8` | **Merged at `085813e`** 2026-10-04 | Frontend device tests 4 suites / 38 passed; gate 248/3/13 (the same 3 stale tests; the 8 device-truth tests ran). `routes/devices.py` labels-only change accepted |
| ✓ | SIM-2 Live Operations UI (Agent Three), PR #50 | `89e99a6` | **Merged at `5567d3e`** 2026-10-04 | Agent Three's browser run (scratch DB) in the PR body; frontend 34 suites / 263; gate 248/3/13 |
| ✓ | SC-16/SC-17 (Agent Four), PR #51 | `d29f1ca` | **Merged at `895769a`** 2026-10-04 | `test_sim_provenance.py` 7 + SIM-1 6 passed; gate 255/3/13; frontend 34/263. Shared touches (models, notifications, resident_requests, task_lifecycle, transportation notification sites, one keyword in `backend/simulation/`) are the SC-16/17 sites |
| ✓ | RQ-009 hearing assistance research (Agent Six), PR #53 | `449c841` | **Merged at `ee8057e`** 2026-10-04 (docs only) | Gate on the merge 254/4/13: the known 3 stale tests + `test_ops_overview` (UTC-vs-facility-date test bug in the 00:00 UTC–local-midnight window; fix exists as `aa3d2f1` on `spike/voice-bridge`) |
| ✓ | RQ-001 Demo data continuity (Agent Five), PR #52 | `797961f` | **Merged at `5bc1f8c`** 2026-10-04 | All five review items done (SC-17 run id via a registered STOPPED `demo_continuity` run; SC-16 holdoff removed; hooks off unless `CAOSCARE_DEMO_CONTINUITY_AUTO`). Focused 27 passed; gate 268/4/13 (known 4) |
| ✓ | HA VM recovery audit (Agent Four), PR #55 | `3d80011` | **Merged at `c438142`** 2026-10-04 (docs) | HA VM running, autostart enabled, CAOSCare connected (68 entities). Reboot test and P1–P3 host changes need Michael's approval |
| ✓ | SIM-3 mixed real + simulated staffing (Agent Three), PR #56 | `ff9465a` | **Merged at `c276a2b`** 2026-10-04 | Focused 31 passed (SIM-3/SIM-1/SC-16-17/RQ-001); gate 272/4/13 (known 4); frontend 34/267; Agent Three's browser run in the PR |
| ✓ | Scenario-aware `latest_run()`/`view` (Agent Three), PR #57 | `9c3c4bf` | **Merged at `737df76`** 2026-10-05 | Focused 33 passed; gate 273/4/14 (known 4; new skip: `test_sim_latest_run_scenario.py:85` skips when the DB already holds simulator runs — make it self-contained); frontend 34/268 |
| 2 | SIM-4 Nursing scenario (Agent Three) | — | Assigned | Branch `pilot/sim-4-nursing` from the tip; include the self-contained latest-run test |
| 3 | SC-8 + SC-9 (Agent Four), PR #59 | `eb5b7be` | PR open; Agent Four's gate running | Review when Agent Four posts final test evidence |
| — | **Michael decision:** HA host reboot test; P1 qemu OOM protection, P2 crash-restart timer, P3 memory caps for heavy builds (`docs/HA_VM_RECOVERY.md`) | — | Awaiting Michael | Agent Four applies only what Michael approves, with receipts |
| ✓ | RQ-009 Pilot Room hearing/handset requirements (Agent Six), PR #54 | `536ed68` | **Merged at `cf0ac00bba1ea18a0b67cec9b3c1cd13d6acce8b`** 2026-10-04 (docs only) | Gate unchanged (known failures only) |
| 5 | RQ-008 audit report (Agent Five), PR #58 | `6ac8164` | Not mergeable against the tip | Agent Five refreshes onto the tip; docs only; no deletions without Michael |
| ✓ | Test-only fixes for the stale gate failures (Agent Six), PR #60 | `70f3b68` | **Merged at `69f1490`** 2026-10-05 | Tests only (iter10, iter11, test_ops_overview). Gate 277 passed / **0 failed** / 14 skipped (skips unchanged) |
| — | PR #45 `docs/2026-10-03-hardware-priority-reset` | `41b544c` | Draft, conflicting | Owner refreshes; the BOM cites it as unmerged |
| — | `pilot/shared-core-rerequest` | `bbfce3b` | No PR | Michael's review; clean branch without the Nabu test path |
| — | `docs/care-app-audit-2026-10-03` | `6b15e5e` | No PR | Owner opens a draft PR if it should land |
| — | `spike/voice-bridge` | `ac11d76` | Spike, not proposed | Not in this round's train |

**Runtime (2026-10-05):** Michael opened the integrated Live Operations UI on the EliteDesk and started simulator runs from it — verified read-only in the shared `caoscare` DB: `simrun_d0ea805fa522` (sink_leak, started 01:23:40 UTC by MICHAEL CHAMBERS, owner, authenticated, staff_ui; STOPPED at cursor 6) and `simrun_4b9a3f2c415d` (started 01:28:25 UTC, RUNNING at cursor 4). Served by :8092 (integration checkout, restarted 2026-10-04 20:22 CDT). The HA VM was recovered by Agent Four (PR #55).

**Earlier runtime findings (2026-10-04, read-only, from the RQ-004 BOM):** the Home Assistant VM `caoscare-homeassistant` is `shut off (crashed)` since about 2026-10-03 20:19 CDT; the RTL-SDR stopped enumerating at 06:30 today; the RF bridge process still posts to a stale lane backend. Restarting HA or the RF path is Michael's call.

**Integration gate baseline (2026-10-04, tip `55b733e`, code `268963c`; `scripts/run_backend_tests.sh`, port 8077, throwaway DB, HA disabled):** 234 passed, 3 failed, 13 skipped. The 3 failures are stale test expectations, not product defects: `iter10_test.py::TestRealtimeSession::test_session_default` and `iter11_test.py::TestRealtimeSession::test_session_has_nine_tools_and_anchors` expect the old 5/9-tool session (it has 26 tools); `iter11_test.py::TestWeather::test_default_facility_weather` expects "the facility" but this machine's `.env` sets `FACILITY_LABEL`. Corrected versions exist on `spike/voice-bridge` (`f36351c`); a test-only extraction is a candidate READY task. Any new failure after a merge is a regression.

**Runtime note:** the "Okay Nabu" test stack from 2026-10-03 is still running (wake listener PID 2833238 on 127.0.0.1:8766 from `~/CAOSCARE-JARVIS`, backend :8096). Nabu is superseded as product identity; left running per Michael's earlier instruction — stop only on his word.

---

## Lanes

| Lane | Domain | Branch | Worktree | Owner / status | Owned (may modify) | Shared dependencies (read, do not redesign) |
|---|---|---|---|---|---|---|
| H | Operations Simulator / synthetic community | TBD after coordinator assignment; governance/spec on `agent/operations-simulator-receipts` | TBD | **READY / not yet coding.** Michael approved 2026-10-02. Build visible multi-agent community simulation using canonical services, explicit simulated identities, mixed real+simulated staffing, pause/step/resume controls, and mandatory origin-linked receipts. | Simulator scheduler/actor profiles/scenario engine/operator simulator UI once assigned; simulator-specific tests | Canonical request/task/receipt contracts and shared services belong to Lane E; department workflows remain owned by their lanes; no parallel data universe |
| A | Nursing / care requests | `pilot/nursing` | `~/CAOSCARE-LANE-NURSING` | Unassigned. Core loop integrated at `7ae91bc`; SC-1..SC-3 integrated (`3249fcd`, `1d02630`); status after a claim verified 2026-10-02. Live voice acceptance is RQ-003 (READY, needs Michael). | Nursing queue use of `DepartmentQueue.jsx` on `/staff` and the Admin Nursing tab; nursing-specific workflow and acceptance tests | StaffTask/request model, receipts, notifications, roles, Aria tool contracts, `DepartmentQueue.jsx` / `RequestHistoryDialog.jsx` (shared with Lane B) |
| B | Maintenance | `pilot/maintenance` | `~/CAOSCARE-LANE-MAINTENANCE` | **Integrated at `6d1ffa4`** (`51deae0`). SC-3 test passes since `1d02630`; status after a claim verified 2026-10-02. | `MaintenanceWorkspace.jsx`, `MaintenanceWorkOrderForm.jsx`, maintenance-specific lifecycle/UI (claim/assign/start/notes/time/complete), maintenance acceptance tests | Same as Lane A; `DepartmentQueue.jsx` is shared with Nursing, so changes to it go through Lane E |
| C | Front desk / transportation | `pilot/frontdesk-transport` | `~/CAOSCARE-LANE-FRONTDESK` | **Integrated at `5e6413c` (2026-10-03).** Front-desk ride verified in the browser; ride-step receipts bypass the SC-13 lifecycle service — blocker assigned to Agent 2. Earlier: reworked and handed off 2026-09-28: `6b67ac8` (on `a95acbe`) — every ride step goes through `task_history.update_task_with_history`, history shown with the shared `RequestTimeline` (lane claim; coordinator verifies at integration). Needs SC-6, SC-7 (implemented on `pilot/shared-core`). Integrate after Shared Core and Demo kiosk. | Front desk workspace, non-call front desk requests and callbacks, transportation driver/vehicle/request/assignment lifecycle, domain acceptance tests | Request model, receipts, notifications; calling is Lane F |
| D | Dining / activities / housekeeping | `pilot/community-services` | `~/CAOSCARE-LANE-SERVICES` | Handed off 2026-09-27: `d95c4d6` (on `e9373d5`) — Kitchen/Activities/Housekeeping workspaces, menu paste intake/review, schedule draft batches. Lane tests only; live/integration acceptance not done. Needs SC-9, CM-1. | Kitchen/menu, activities/programs, housekeeping UI and workflows, domain acceptance tests | Inbound email infrastructure (Lane F / E), request model |
| E | Shared core / integration contracts | `pilot/shared-core` | `~/CAOSCARE-LANE-SHARED` | SC-1..SC-7 integrated (`3249fcd`, `1d02630`). Open: SC-8, SC-9, SC-10. | StaffTask/request schema and lifecycle, shared statuses, receipts/history, notification routing, permissions/roles, shared API contracts, shared UI primitives (incl. `DepartmentQueue.jsx`, `RequestHistoryDialog.jsx`), common Aria operational tools, migrations used by several lanes | Changes only on a concrete request from an active lane; no speculative redesign |
| F | Communications / calling | `pilot/communications` | `~/CAOSCARE-LANE-COMMS` | Implemented, tests only: `0978bb1` (on `e9373d5`) — truthful notification delivery/fallback, Communications tab; calling per Michael's D1–D8 (Asterisk, ATA hotline, `0` front desk, Aria SIP, approved family calls, call lifecycle, 911 bypasses Aria). No Asterisk/ATA/trunk/OpenAI SIP test yet. Needs SC-8. | Inbound/outbound email provider config and code gaps, department notifications delivery, call lifecycle, SIP/PBX/Aria phone bridge, front desk/family call receipts | Request/status changes coordinate with Lane E |
| G | Demo kiosk / resident experience | `pilot/demo-kiosk` | `~/CAOSCARE-LANE-DEMO-KIOSK` | **Integrated at `239324a`** 2026-10-02 (`0b69cae`). Proven: light on/off, thermostat, TV on/off, DEMO RESET (isolated DB), real-room separation. Not proven/built: volume/channel, blinds tool, staff-help in the visual, front-desk call visual, real spoken voice. Open: SC-10, SC-11, SC-12; Demo kiosk moved to demo-only room `DEMO` 2026-10-03 (Michael's decision). | Demo kiosk room visual and its live state display, demo device set-up (simulated/`mock` adapter), typed input on the kiosk, DEMO RESET, demo acceptance tests | Aria room-control tool contracts and `/devices/public/room/{room}/command` (use as-is; changes go through Lane E), device adapters, Kiosk.jsx shared with the real room, resident requests. Must never change real room/device state |
| Coord | Integration coordinator | `integration/2026-09-27` | `~/CAOSCARE-INTEGRATION` | This checkout | This file, the authoritative checklist, merge order, whole-system tests, localhost:3000 | Everything, read-only except integration merges |

Coordinator log: 2026-10-03 demo kiosk moved to demo-only room `DEMO` (synthetic resident; reset restricted to it; Room 401 untouched). 2026-10-02 merged `pilot/demo-kiosk` (`0b69cae`) at `239324a` (docs-only conflicts); :8092 restarted on it; DEMO RESET not run on Room 401. 2026-10-02 merged `pilot/shared-core` (`5a9eb32`) at `1d02630` (docs-only conflicts); :8092 restarted on it. 2026-09-28 recovery checkpoint (`PILOT1_RECOVERY_CHECKPOINT.md`); all lane worktrees clean and pushed. Merged `pilot/maintenance` (`51deae0`) at `6d1ffa4` (docs-only conflicts). Merged `pilot/shared-core` (`a6230cb`) at `3249fcd` (log conflicts only); :8092 restarted on the merged code. Earlier: merged `wip/public-capability-panels` (`0985ae5`) at `e70fbce`; Therapy/Beauty Shop placeholders `7a5fbe9`; localhost:3000 serves integration again (proxying /api to :8092). `wip/public-capability-panels` and `~/CAOSCARE-WIP-PANELS` are now merged and can be retired once Michael agrees.

## Shared core requests

| ID | From | Requirement | Reason | Consumers | Status |
|---|---|---|---|---|---|
| SC-1 | Lane A (nursing acceptance 2026-09-28) | Status changes append a receipt instead of updating the last one in place (`receipts.py::update_receipt_status`) | History shows "task assigned · completed" as one entry | Nursing, Maintenance, Front desk, reports | **Done** — integrated at `3249fcd`; browser-verified 2026-09-28 (separate receipts per step) |
| SC-2 | Lane A | Timestamped note history on a request (the single `notes` field is overwritten by completion notes; note edits create no receipt) | Progress notes are lost on completion | Nursing, Maintenance | **Done** — integrated at `3249fcd`; browser-verified 2026-09-28 (three notes kept in order) |
| SC-3 | Lane B (lane-local SC-3) | A claim must count as "seen" for resident status: `aria_operational_state.task_lifecycle` returns `open` for a claimed, unacknowledged task, so `aria_request_status` says "no one has picked it up yet" | **Truth defect.** Re-proven on integration `3249fcd` 2026-09-28 for nursing (`task_f34bfff0a8c8`) and maintenance (`task_e5dd5e5527b5`): after a claim, Aria said "no one has picked it up yet… assigned to <name>" | Every Aria status answer | **Done** — integrated at `1d02630`; browser-verified 2026-10-02 (nursing + maintenance: "<name> has taken it on" after a claim); test passes |
| SC-4 | Lane B (lane-local SC-4) | Spoken summary carries the latest staff note while `in_progress`; history answer names who completed it and the completion note | Minor, not false | Nursing, Maintenance | Integrated at `1d02630`; latest note while in progress verified 2026-10-02; completer/closing note in the history answer covered by backend tests only |
| SC-5 | Coordinator (2026-09-28) | `realtimeOperationsTools.js:132` tells Aria the latest note has "no timestamp on record", but since SC-2 the backend returns `latest_update_at` (e.g. "today at 8:33 PM"). Also the duplicate reply says "ask #1" while the queue shows "asked 2x" | Aria states something untrue about the record | Every Aria status answer | Integrated at `1d02630`; real note time verified 2026-10-02; "times asked" wording covered by backend tests only |
| SC-6 | Lane C (lane-local SC-3) | Front desk can claim, assign and note Administration-department requests (`task_assignment.py`, `tasks.py` PATCH notes, `maintenance.js` `canClaim`/`canAssign`, `DepartmentQueue.jsx` `canNote`, `/staff/assignable?department=administration`) | Front desk can't own a callback | Front desk, Admin | Integrated at `1d02630`; backend/frontend tests only — browser verification comes with the Front desk lane |
| SC-7 | Lane C (lane-local SC-4) | Skip `reject_unconfirmed_time` for authenticated `source="front_desk"` requests | Staff-entered callback times are rejected (422) | Front desk | Integrated at `1d02630`; backend tests only — browser verification comes with the Front desk lane |
| SC-8 | Lane F (lane-local SC-3) | Pass `related_object_type="task"`, `related_object_id` to `notify_department` at every call site; delete dead `tasks.py::_notify_department` | Per-request delivery status | All departments, history UI | Assigned to Agent Four 2026-10-04. Partly prepared on `pilot/communications` `aa10645` (not integrated) |
| SC-9 | Lane D (lane-local SC-3) | Department staff can read the department list (`GET /departments` is admin-only) or the workspace heading gets another label source | Workspace headings show the slug | All department workspaces | Assigned to Agent Four 2026-10-04 |
| SC-10 | Lane G (lane-local, `pilot/demo-kiosk` @ `a95acbe`) | `realtimeLightControl.js::handleToggleLight` checks the light's capabilities before the implicit power-on | **Truth defect.** Demo 2026-09-28: "Make the light green" on an off light switched it on, then reported only "doesn't support color" with `ok: true` | Every room with lights (real and demo) | **Done** — integrated at `085813e` (PR #48): any unsupported attribute refuses the request before anything is sent, `ok:false` |
| SC-11 | Coordinator (2026-10-02, Demo kiosk review) | Mock devices outside a demo room are now recorded `verified: true` against the simulator (`device_adapters.execute_mock` → `simulated_device.py`); e.g. real Room 214's mock TV/thermostat. Record them as simulated (not verified), or limit the simulator read-back to demo rooms | Records/receipts call a non-existent device "verified" in a real resident room | Room 214 and any real room with mock scaffolding; receipts; Aria | **Done** — integrated at `085813e`: mock commands always `simulated`, verified only in room `DEMO`; receipts/events labelled `simulated` |
| SC-12 | Coordinator (2026-10-02) | `toggle_tv` and `adjust_room_temperature` pass `session_id` to the room command like `toggle_light` does | TV/thermostat `device_commands` have no conversation link (light commands do) | Traceability, Resident hub | **Done** — integrated at `085813e`: TV power/volume/input and thermostat commands carry `session_id` |
| SC-13 | Michael / Agent 2 (SIM-0, 2026-10-03) | ActorContext, one lifecycle service (`task_lifecycle.py`, `task_actions.py`) with authority checks, a receipt per action chained to the request's origin, legacy no-origin refusal, `Resident.synthetic` / `StaffTask.simulated` | Receipt law for staff requests | All departments, simulator | Integrated at `79ca54b` (2026-10-03); nursing + maintenance browser lifecycles: one receipt per step incl. each note, with actor/authority/before/after |
| SC-14 | Coordinator (2026-10-03, SC-13 integration) | Closed-state guard: start/complete/acknowledge/note on a completed or skipped request must be refused (or an explicit reopen) | `POST /tasks/{id}/start` on a completed request sets it back to in progress and overwrites `started_at` (pre-existing; SC-13 records it truthfully but allows it). UI hides the buttons. | All departments | Integrated at `268963c` (2026-10-03): closed requests refuse lifecycle actions (409; transport keeps 400); refusal recorded. Verified: start on completed `task_e3f03fbf6092` → 409, `started_at` kept, `task_start_refused` recorded |
| SC-15 | Michael (2026-10-03 approval) | Transportation ride steps (`transport_task_history.py`, `transportation_runs.py`, `transportation.py`, `transportation_assign.py`) go through `task_lifecycle` so each step has a linked receipt | Ride steps write receipts outside the SC-13 lifecycle service | Transportation acceptance | Integrated at `268963c` (2026-10-03): ride steps go through `task_lifecycle`. Verified: browser front-desk ride `task_bb4109c4a4da` request → cancel; both receipts chained to the origin with actor/authority; assign/depart/complete by `test_transport_ride_receipts.py` (gate) |
| SC-16 | Agent Three (SCR-SIM-1, PR #49) | Department notifications for a simulated request must not send real mail: mark or route simulated notifications (simulated adapter, or subject marker + receipt link; cf. SC-8) | Once RQ-005 adds a provider key, a simulated request would send real, unmarked email. SIM-1 refuses to start while a key is set | Simulator, notifications | **Done** — integrated at `895769a` (PR #51): simulated requests' notifications recorded as `simulated`, never sent; SIM-1's start guard still in place |
| SC-17 | Agent Three (SCR-SIM-2, PR #49) | A `simulator` channel and/or server-set `simulation_run_id` on canonical requests (`create_resident_request` accepts only aria_voice/kiosk_button/front_desk) | Simulated origin receipts say `channel: aria_voice` although no Aria session happened; ENGINEERING_CONTRACT decision 4 | Simulator, receipts, reports | **Done** — integrated at `895769a`: source `simulator`, `simulation_run_id` on the StaffTask and every receipt of its chain |
| CM-1 | Lane D → Lane F | `email_inbound.py` activities lane: set `linked_object_id` to the `ingest_id` from `create_schedule_items()` | Link inbound email to its draft batch | Activities | Open |

Shared core work queue (priority order, 2026-10-02): SC-10 unsupported light attribute truth · SC-11 mock devices recorded as verified in real rooms · SC-12 · SC-8 · SC-9 · CM-1 (SC-1..SC-7 integrated) · unsupported light attribute truth · SC-8 notification/request linkage · SC-9 department-list staff access · CM-1 activity email batch linkage (Lane F). SC-3 and SC-5 are Aria truth defects and go first.

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

**Universal receipt rule.** No worker, simulator actor, human action, scheduler, provider or adapter may silently change meaningful state. Every action must leave durable origin-linked evidence. An agent's self-report is never proof. See `docs/CAOSCARE_OPERATIONS_SIMULATOR.md`.

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

**Handoff to Michael (Michael-directed, 2026-10-03).** At the end of each work block, commit and push the completed work to the authorized branch, then give Michael one GitHub reference he can paste to Aria instead of screenshots:

```text
REFERENCE: <full commit SHA>
BRANCH: <branch name>
GITHUB: https://github.com/caosos/CAOSCARE.COM/commit/<full SHA>
RESULT: what changed, in 2–4 sentences
VERIFICATION: tests/build performed and their actual results
RECEIPT: originating task, files/state changed, evidence of the result
STATUS: complete | blocked | still in progress
NEXT: the one next action
```

Work spanning several commits: give the branch or PR link plus the start and end SHAs. A change that exists only on the EliteDesk is reported as **LOCAL ONLY**, with no GitHub reference, and is not called complete until it is pushed and verified there. No merge to `main` and no Linode deploy without Michael's exact approval.

**Production.** No worker or coordinator deploys. Release: accepted EliteDesk integration → push GitHub → show Michael the current production SHA, the proposed SHA and the exact commit/file range → Michael explicitly approves → deploy that exact GitHub SHA to Linode → verify production.
