# RQ-022 — Escalation + Staff/Admin overview browser acceptance (2026-10-08)

Tip tested: `integration/2026-09-27` `a90c9f8` (RQ-018 escalation, SC-1..SC-17, RQ-021). Worker branch `bounded/rq-022-escalation-accept`.

## Environment (isolated, torn down afterwards)
- Throwaway DB `caoscare_rq022`, a copy of `caoscare_public_demo`. Demo passwords were reset in the copy and the 3 old demo alerts were set to `resolved` so they could not confuse the test. Dropped afterwards.
- `backend/scripts/setup_demo_room.py` was run against the copy to create the demo room `DEMO` (synthetic resident) as on the real demo.
- Backend from this worktree on `:8093`, `CAOSCARE_ESCALATION_INTERVAL=5`, `EscalationRule` set to level 2 at 20 s and level 3 at 40 s. `OPENAI_API_KEY`, `RESEND_API_KEY` and Home Assistant blank, so no provider could be called.
- Frontend dev server on `:3015`, proxied to `:8093`. Driven with headless Chrome over CDP (throwaway script, not committed), 1280 px and 390 px.
- `:3000`, `:8092` and other worktrees were not touched. Both servers stopped and the DB dropped at the end.

## Results

### 1. Unanswered help alert escalates on the schedule — PASS
Two assist alerts were raised from the room screen endpoint (`POST /alerts`) at 07:07:19 UTC: A in the demo room, B in room 3W01. Nobody called `/escalation/tick`.
- Both went `level 0 → 2` at 07:07:40 (about 20 s) and A went `2 → 3` at 07:08:00 (about 40 s). There is no level 1 any more (RQ-018 design).
- Exactly one new `alert_escalated` receipt per level change per alert: A has two (`0→2`, `2→3`), B has one (`0→2`). Receipts name `system:escalation`, the rule used and before/after level; the alert timeline has the same entries. `status` stays `active`.
- A third and fourth alert raised later behaved the same.
- Staff dashboard (`/staff`) with the page left open and no reload: a fresh alert showed no badge, then `ESCALATED LV2`, then `ESCALATED LV3` as the schedule ran.
- Alerts board (`/alerts`): badges "Esc Lv2" / "Esc Lv3".
- Operations overview: see defect 1 (fixed) — the level was not shown before the fix. After the fix the attention rows read "Unacknowledged assistance call - escalated to level 3".

### 2. Acknowledging stops escalation — PASS
B was acknowledged (by the owner) at 07:07:44, just after reaching level 2. Over the next 45 s (past its level-3 time) B stayed `acknowledged`, level 2, with one escalation receipt; A, still unanswered, went to level 3.

### 3. `/alerts/feed` performs no writes — PASS
With active alerts present, a digest (SHA-1 of every document) of `alerts` and `receipts` was taken before and after 3 calls each of `/alerts/feed`, `/alerts/stats` and `/ops/overview` (and after 3 calls of the feed alone while the alerts were all resolved): identical both times (5 alerts, 20 receipts).

### 4. Nursing and maintenance lifecycles, and overview/report consistency — PASS (one observation)
A nursing request (3W03, high) and a maintenance request (3W02) were filed through the resident request endpoint. A demo nurse (Nancy Reyes) used `/staff` and a demo maintenance user (Carl Boone) used `/workspace` in the browser: Acknowledge, Claim, Start, Note, Complete with a closing note, then History.
- Each step is its own history entry with the actor's name and time (created, acknowledged, claimed, started, note, closing note, completed with minutes). Receipts: `resident_request_created, task_acknowledged, task_assigned, task_in_progress, task_note_added, task_completed` — six per request, none rewritten.
- Operations overview (API and screen): Nursing 3 open / 2 unassigned / 1 completed today; Maintenance 1 open / 1 in progress / 1 completed today — matching the Nursing and Maintenance department tabs ("3 OPEN, 2 UNASSIGNED" and "1 OPEN, 0 UNASSIGNED, 1 IN PROGRESS") and the staff dashboard.
- Ops reports → Weekly workload: Nursing created 1 / completed 1 / still open 3, Maintenance created 1 / completed 1 / still open 1, with per-staff counts naming Nancy Reyes and Carl Boone. Daily exceptions: 9 rows (2 open assistance events, 2 transportation, 5 unassigned), matching the overview's attention count of 9.
- Observation: the closing note is its own history entry but shares the completion receipt (six receipts for seven history lines), as designed by SC-13; not a defect.

### 5. Phone width (390 px) — PASS
Staff dashboard, Alerts board, Admin overview, Admin Nursing, Maintenance and Ops reports tabs, nurse `/staff` and maintenance `/workspace`: `scrollWidth` equals `clientWidth` on every page, no action button off-screen on the two staff workspaces, no console errors on any page at either width.

## Defects
1. **FIXED — Operations overview did not show the escalation level.** The Staff dashboard and Alerts board did, so a manager reading only the overview could not tell a call had reached level 3. `backend/routes/ops_overview.py` now appends "- escalated to level N" to the reason of an open assistance event at level 2 or 3; `tests/test_ops_overview.py` asserts it. Verified in the browser.
2. **Reported — Ops reports → Daily exceptions has no escalation level either.** Same data, `routes/reports.py` (a separate row builder). Not changed.
3. **Reported — a signed-in nurse sees an "Admin" button on `/staff`.** Clicking it leaves the nurse on `/staff` with no message (the route refuses non-admins). Cosmetic, in `StaffDashboard.jsx` header.
4. **Reported — the escalation loop only runs after a backend restart.** The live backend on `:8092` was not started in this test; this stack proves the schedule, not the live process.

## Not tested
Real SMS/on-call notification at level 3 (no rule phone, no Twilio), the Aria voice path, real pendant hardware, multi-worker concurrency of the tick (covered by `test_rq018_escalation.py`), a Staff dashboard alert acknowledged through the browser button (acknowledged by the owner through the API).

## Gate
`CAOSCARE_TEST_PORT=8094 CAOSCARE_TEST_DB=caoscare_gate_rq022 OPENAI_API_KEY= HA_BASE_URL= HA_TOKEN= backend/scripts/run_backend_tests.sh`: 312 passed, 0 failed, 31 skipped (tip baseline 312).
