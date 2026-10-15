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

## 6. Human participation acceptance (Phase 6 / 8 G–J), 2026-10-14 19:25–19:31 CDT

Driven in Michael's signed-in owner session (Claude in Chrome, `localhost:3006`) on the
test community only. Receipts name Michael because the actions ran in his session at
his instruction (CO-008).

| Step | Evidence |
|---|---|
| Cover SIM Housekeeper 02 | first attempt **refused** ("not on site at the run's current time"): the cover checked the run clock (day 19, night) while all screens show the worked moment (day 13, 11:36). **Fixed**: cover uses the moment work has reached. Then `sim_shift_cover_started` `rcpt_da57cabbc42d`, actor Michael (real-human) |
| Work as Housekeeping | workspace "Michael (owner), real person … not as a simulated worker"; roster "Housekeeper 02 · Covered by a person · Michael covering" |
| Accept, start, note, complete | `task_6cb1cf86d28f` (SIM Resident 030 room service): `resident_request_created` (sim:resident:030) → `task_assigned` → `task_in_progress` → `task_note_added` → `task_completed`, each by Michael, chained; completed_by Michael; outcome text recorded |
| Simulated worker yields | 4 executor receipts `cancelled`: "SIM - Housekeeper 02 did not claim/complete this ticket: Michael is covering the shift; the ticket stays in the queue" |
| Hand back | `sim_shift_cover_ended` `rcpt_4902eee39f62`, actor Michael |
| Autonomous work resumes | **Defect found**: Housekeeper 02 had started a ticket 2 s before the cover; the cover cancelled its completion, the ticket stayed in progress, the one-active-ticket rule refused the worker's next claim, and the **run stopped** (cursor 44,287 from 00:27:40Z). Recovered truthfully: the orphaned ticket `task_40051053b62f` was **cancelled (not completed)** by Michael with the reason recorded; the run advanced (cursor 44,293) and Housekeeper 02 claimed its next ticket at 00:29:40Z. **Fixed**: a cover is refused while the worker is mid-ticket (verified in the browser). |
| Integrity | 44,287 executor event receipts = cursor 44,287; 0 events with more than one receipt; no worker holds more than one in-progress ticket |

## 7. Realistic operations (Phase 7) — measured

- Overlapping jobs: none (unique in-progress-per-worker index + check; verified above).
- Off-duty work: none — ticket phases go only to on-shift workers (SIM-006); maintenance
  after 15:30 is on call (roster shows On call), closed departments queue work
  (Activities 0 on duty before 09:00 with its work waiting).
- **Executor lag**: at 60× the run clock reads simulated day 19 while work is done to
  day 13 (≈135 simulated hours behind). Screens state this; covers now use the worked
  moment. Throughput, not correctness — tracked as SIM-007B.
- **Resident-initiated calls: 0 per simulated day** (plan generates only scheduled
  routines); Michael's expectation ≈100/day in 80 apartments is not yet represented.
  Scheduled routine load: 1,163 tasks/simulated day (Nursing 675). Adding resident calls
  is a simulator-plan change (next CO-008 part).
