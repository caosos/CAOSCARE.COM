# CO-008 Worker workflow and staffing — acceptance checklist

Status: **ACTIVE, ready for owner review** (2026-10-15 ~02:00 CDT). Not owner-accepted.
Queue #166, workflow #168, draft PR #167. Branch `feature/co008-request-sources` (@ `86e501a` at writing);
plan-v9 cutover candidate `co008/v9-candidate`.

Evidence was produced by a separately identified test operator ("Claude Test Operator (automation)",
`user_c12e6d3a8d68`) on the scratch test stack (backend :8096, frontend :3006, DB
`caoscare_sim_acceptance_live20261014b`, 1x run `simrun:living:f24c347040991ddde766`). No receipt names
Michael for work he did not do. Room 214 and the real `caoscare` DB were not touched by CO-008 work.

| # | Directive item | Status | Evidence |
|---|---|---|---|
| 1 | Fix the Start failure (500 "Could not start") | Done | `d466ca9`: one-active rule checked before writing (409 naming the ticket held); `DuplicateKeyError` becomes a receipted 409. Chrome: overlap refusal toast. Test `test_task_work_rules` case 3. |
| 2 | Distinct lifecycle CREATED → ACKNOWLEDGED → CLAIMED → IN PROGRESS → COMPLETED | Done | Complete refused unless in progress by the worker (409); outcome required (422). Queue/My tasks offer Start only when waiting and Complete only when in progress. Chrome chain on `task_2dd2f3b6aa62`. |
| 3 | Cancellation, reassignment, blocked work and handoff as distinct outcomes | Done | Cancel needs a reason (`task_cancelled`); reassign → `task_reassigned`, release → `task_unassigned`, handoff → `task_handed_off` (back to waiting), each with a required reason (`aa12f85`); blocked = "Can't complete" → supervisor review (`task_escalated`), frees the worker. Chrome handoff with reason, then restart and completion. Tests cases 5-7. |
| 4 | Admin overrides need a reason | Done | Admin completion outside the flow needs `override_reason`; recorded on the task, history and receipt (`admin_override:<role>`). Test case 4. |
| 5 | Realistic staff capacity with queues and escalation | Done on v8; v9 awaiting cutover | One active ticket per worker (persisted index + pre-check); queues with wait reasons; simulated escalation level 1 → lead, level 2 → supervisor with receipts (`97c619b`), shown as overdue + "Escalated · level N" (`58999d1`, `f3bed01`). v9 (`co008/v9-candidate`): role eligibility (0 reminders to care aides), on-call call-in, wait by cause, service-window expiry. Real-Mongo acceptance passed on `caoscare_sim_acceptance_co008v9a20261015`. |
| 6 | Desktop workspace detail fields and clear errors | Done | Task detail: requested (sim) beside receipt time, expected, waited/working with reason, raised by, sim clock, next step (`26c7eb0`); v9 adds wait by cause and call-in. Errors show the server's reason (`apiErrorText`). |
| 7 | Automated plus Chrome acceptance with a test operator | Done | Backend gate 0 failures after `86e501a` (was 29); simulator suites 565 (v9: 584); frontend 119 suites / 774 (v9: 775). Chrome walkthroughs above. Receipts on #168. |

## Owner decisions still open

1. **v9 cutover:** stop the v8 1x run (kept, not reset), deploy `co008/v9-candidate`, start a v9 run at 1x.
   v9 code cannot load a v8 run.
2. **Staffing/durations:** under v9, 38% of dinners and 45% of afternoon activity offers close as not served
   (one evening kitchen worker at 3 min a plate; per-resident escorts). Options in
   `docs/reports/2026-10-15-co008-plan-realism.md` (on `co008/plan-realism`).
3. **Breakfast/lunch service windows:** proposed only.

## Defects found and fixed during acceptance

- MyTasksCard fetched a nonexistent `/tasks/mine` (empty list) — `232d9a0`.
- 84 escalations displayed as 0 overdue — `58999d1`.
- Simulated escalation labelled "Couldn't complete" in history — `f3bed01`.
- Assign box blank for a holder off the roster — `5f5ae16`.
- Demo-room simulator requests refused as "Unknown simulation run" (empty projection treated as missing) — `cca8e66`.
- v9: a called-in on-call worker flagged as an off-site anomaly — `be8d0cb` (candidate).
