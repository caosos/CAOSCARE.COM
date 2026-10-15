# CO-008 — Department operations reconciliation (verified, 2026-10-14)

Environment measured: EliteDesk, MongoDB database `caoscare_sim_acceptance_live20261014b`
(the isolated 75-resident test community), run `simrun:living:68d9abcc9c60b096a6c1`
(RUNNING; executor `resume_run.py` PID 2745567, code `261dfa8`; cursor 43,165 of
320,730 events; run clock simulated day 13; executed through simulated day 12/13).
Read-only queries; nothing was changed to make numbers agree. The real resident
database `caoscare` and Room 214 were not touched.

## 1. Sources of truth

| Thing | Source of truth |
|---|---|
| 75 simulated residents | `residents` rows provisioned for the run (markers `simulation_scope=living_community`, `simulation_community_id=sim:community:living-80-v1`) from `simulation/community_blueprint.py` |
| 50 simulated workers | the rota in `simulation/community_staffing.py` (`WORKERS`, `worker_statuses`). **Not user accounts, by design.** |
| Eight departments | `departments` collection (nursing, maintenance, housekeeping, transportation, kitchen, administration, activities, front_desk) |
| Shifts / availability | `community_staffing` rota + `community_coverage` (on duty / on call / closed / uncovered) at the executed simulated minute |
| Resident requests, routine tasks, assignments, status | `staff_tasks` (one canonical StaffTask per ticket; `source`, `conversation_session_id`, `assigned_to`, `status`, timestamps) |
| Transitions and completion | `receipts` (one per transition, chained) + `staff_tasks.event_log` |
| Simulated time | `sim_runs.sim_minute` (run clock) and the last executed event (`last_event_id`); real time = timestamps on tasks/receipts |

## 2. Why the simulator showed workers and the department pages said "no one works here"

Both screens read **the same database, the same tasks and the same departments**.
They differ only in where they look for people:

- Department pages (`DepartmentQueue` → `GET /staff/assignable`; department board →
  `users`) list **user accounts** of the department. This database has exactly one
  user account: the owner. So every department showed "No one works in … yet".
- The simulator dashboard lists the **rota** (`worker_statuses`), where the 50 simulated
  workers live, and their ids (`sim:staff:…`) appear as `assigned_to` on the tasks.

Fix (this PR): `GET /departments/{slug}/roster` returns REAL accounts plus the run's
SIM rota from the same department read the simulator dashboard uses
(`community_dashboard_detail.department_detail`), and every department page shows it.
Simulated workers stay non-accounts and are not offered in "Assign to" (the simulator
assigns their work from its plan); a person can cover a SIM worker's shift.

## 3. Department counts (canonical `staff_tasks`, at measurement time)

| Department | Completed | Waiting | In progress | Origin |
|---|---|---|---|---|
| Nursing | 8,226 | 7 | 5 | all scheduled routine (simulator) |
| Kitchen | 2,700 | 0 | 0 | all scheduled routine |
| Housekeeping | 898 | 2 | 0 | all scheduled routine |
| Activities | 877 | 23 | 0 | all scheduled routine |
| Front Desk | 540 | 0 | 0 | all scheduled routine |
| Administration | 360 | 0 | 0 | all scheduled routine |
| Transportation | 276 | 0 | 0 | all scheduled routine (coordination) |
| Maintenance | 180 | 0 | 0 | all scheduled routine |

- **Resident-initiated requests: 0.** Every task is a scheduled routine
  (`conversation_session_id` `simulator:event:day-NNN:resident-NNN:<routine>`). The
  simulator plan contains no resident-initiated calls at all. Michael's expectation of
  roughly 100 resident calls/day in an 80-apartment community is therefore not yet
  represented: measured resident calls/day = 0; measured scheduled routine work =
  1,163 tasks per simulated day across all departments (Nursing 675).
- Staff-created tasks: 0. Genuine duplicates: none found (one ticket per scheduled
  event; dedup within the same event only, SIM-006).

## 4. Transportation: the 276 "requests"

- All 276 are `Scheduled simulated transport coordination.` tickets
  (routine `transport_coordination`, `source=simulator`), created by the simulator's
  daily routine plan, assigned to and completed by SIM drivers.
- They are **coordination tasks, not ride requests**: none carries
  `requested_for_date`, a time label, `transport_slot_id` or `transport_run_id`.
- The transportation system has **0 runs, 0 drivers and 0 vehicles** in this database,
  and the simulator deliberately does not call the booking engine (transportation is
  coordination-only until a simulation-isolated booking path exists). That is why the
  Transportation page shows 0 booked and 0 completed trips: no ride was ever booked,
  and none is invented.
- Next correction (later PR in this change order): show these as "Coordination tasks"
  separately from "Ride bookings" on the Transportation screens.

## 5. Remaining CO-008 work (tracked)

1. Compact expandable department task list (Phase 5).
2. Transportation: coordination vs bookings separation (Phase 4 UI).
3. Human participation acceptance as Michael: Work as → cover → accept → start →
   note → complete → receipts → hand back → simulator resumes (Phase 6, 8 G–J).
4. Resident-initiated call generation in the simulator, measured against ~100/day
   (Phase 7) — a simulator-plan change on the PR #146 line.
