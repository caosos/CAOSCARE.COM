# CO-008 plan realism (living-community plan v9)

- Date: 2026-10-15. Branch `co008/plan-realism` from `feature/co008-request-sources` @ `232d9a0`.
- Fixes the defects in `CAOSCARE-OPS-WORKSPACE/docs/reports/2026-10-15-co008-staffing-capacity-audit.md`.
- New plan revision: `living-community-timeline-v9-plan-realism-<cohort>`.
- All numbers below come from the pure plan for `community_75` (no database). "Before" is v8, "after" is v9.

## What changed

| Area | Change | Where |
|---|---|---|
| Qualified roles | One table maps routine → eligible job roles, in preference order. Medication reminders go to the med tech, then the RN, never to a care aide. Hands-on care goes to care aides first, then the med tech, the RN last. Single-role departments use their one role. An unlisted nursing routine is refused. With no qualified worker on site, the ticket waits (`waiting_for_qualified_staff`). | `simulation/community_role_eligibility.py` |
| On-call call-in | With no qualified worker on site, a high or urgent ticket calls in the on-call worker. That worker claims it after a response delay (simulation assumption: maintenance 40 min, RN 30 min), and the claim receipt carries `called_in_on_call: true`. There is no call-in if the on-site shift would arrive first. A worker already on site from an earlier call-in takes the next one without a new delay. Normal and low priority work waits for on-site hours. The worker never holds two tickets at once and stays "on call" (not present) until the claim. | `simulation/community_on_call.py` |
| Wait reasons | Every waited minute is attributed to its blocker: staff busy, qualified staff absent, on-call only, on-call response, or department closed. The claim and expire receipts carry `wait_breakdown` (minutes per blocker, summing to the wait), and `wait_reason` is the dominant blocker. | `simulation/community_wait_blockers.py` |
| Time-bound work | Dinner (window closes 19:30) and the afternoon activity offer (closes 18:00) expire if not claimed in their window. The plan then has an `expire` phase: the on-site department lead closes the canonical task as `skipped` through `task_actions.skip`, which produces a `task_cancelled` receipt plus an executor receipt. Resident calls and care needs never expire. | `simulation/community_service_windows.py`, `simulation/community_ticket_phase.py` |

## Before / after (community_75, 90 days, 114,445 tickets)

**Medication reminders by role:**

| | Care aide | Med tech | RN | Med-tech share |
|---|---|---|---|---|
| Morning, before | 4,211 | 1,108 | 1,431 | 16.4% |
| Morning, after | 0 | 3,681 | 3,069 | 54.5% |
| Evening, before | 4,028 | 783 | 1,939 | 11.6% |
| Evening, after | 0 | 4,290 | 2,460 | 63.6% |

**Hands-on care** (showers, toileting, room checks; aide / med tech / RN):

| | Care aide | Med tech | RN |
|---|---|---|---|
| Before | 30,701 | 11,813 | 4,647 |
| After | 32,012 | 10,084 | 5,065 |

The med tech still helps when every aide is busy.

**Waits, max / median minutes:**

| Department | Before | After |
|---|---|---|
| Nursing | 247 / 11 | 246 / 14 |
| Kitchen | 685 / 28 | 599 / 22 |
| Activities | 1,113 / 89 | 113 / 40 |
| Maintenance | 2,441 / 553 | 2,375 / 50 |
| Housekeeping | 1,382 / 51 | 1,382 / 51 |
| Front desk | 880 / 87 | 880 / 87 |
| Transportation | 853 / 0 | 853 / 0 |
| Administration | 0 / 0 | 0 / 0 |

**Maintenance high-priority waits** (n=332):
- Max wait fell from 970 min to 80 min; the median fell from 16 to 13 min.
- There were 132 call-ins. Each waited the 40-min response, or up to 80 min when queued behind another call-in.
- The median for all maintenance work fell from 553 to 50 min. Call-ins take after-hours urgent work off the day technician, so the backlog of that slightly over-capacity department stops growing. Without call-in, the v9 median is still 553 min.

**Unclaimed at day 90:** 139 before, 97 after.

**Wait-reason distribution:**

| Reason | Before | After |
|---|---|---|
| none | 26,146 | 27,319 |
| waiting_for_available_staff | 87,552 | 78,097 |
| waiting_for_department_opening | 518 | 2,221 |
| waiting_for_on_site_staff_on_call_only | 90 | 942 |
| waiting_for_on_call_response | — | 132 |
| waiting_for_qualified_staff | — | 0 |
| not_served_service_window_closed | — | 5,637 |
| still_waiting_at_simulation_end | 139 | 97 |

**Closed-period waits:** 2,322 claimed non-nursing tickets waited through a closed period. Of these, 2,221 are now labelled `waiting_for_department_opening`. The other 101 have staff-busy as their dominant blocker. Before, 7,131 of 7,739 such tickets were labelled staff-busy.

**Time-bound work:**
- No dinner or activity is served on a later day any more. Before: 1,761 dinners and 2,047 activity offers.
- 2,577 of 6,750 dinners (38%) and 3,060 of 6,750 activity offers (45%) are now closed **not served**.
- This is the truthful consequence of one evening dining worker at 3 min per plate, and two activity coordinators at 10 min per escort. See the proposal below.

**Plan size:**
- `community_75`: 344,524 events. There are 114,445 open, 108,711 claim, 108,711 complete and 5,637 expire events, plus 7,020 shift milestones.
- `burn_in_10`: 52,873 events, digest `798135a8…`.

## Plan revisions and the running v8 run

The codebase supports **one plan revision per cohort**. `PLAN_REVISIONS` maps each cohort to a single revision. The runner and controls build the one current plan, and `DatabaseRunnerTimeline` refuses a run whose persisted fingerprint differs.

So **v9 code cannot load a v8 run**. The runner fails closed with "persisted run … plan fingerprint is invalid", and the read views' `cohort_of_revision` rejects the v8 revision; the latter is pinned in `test_v9_plan_is_deterministic_and_v8_runs_are_not_loadable`. The owner must stop the v8 run and start a new v9 run before deploying this code to the process that executes runs.

Keeping v8 loadable would mean keeping the v8 scheduler alive beside v9 as a second code path. This change does not add that.

## Proposal: task durations (not changed; owner decision pending)

| Routine | Now | Proposed | Effect to expect |
|---|---|---|---|
| Medication reminder | 3 | 5–8 | The morning pass outgrows one med tech; the RN covers more, or the med pass starts earlier. |
| Shower | 20 | 30–45 | More aide time goes to showers, so toileting calls wait longer. |
| Toileting / transfer | 8 | 10–15 | Nursing medians rise. |
| Plated meal | 3 | 3 dining room / 10–15 tray | Model dining-room service as table batches, not one plate per worker, or add a second evening server. Otherwise dinners will be missed truthfully. |
| Housekeeping room service | 10 | 30–45 | Needs a third housekeeper, or a rotating cleaning schedule (each room every 2–3 days) rather than daily service. |
| Activity offer and escort | 10 | Batched | Escort a group per activity rather than each resident individually. |

**Breakfast and lunch windows:** the window table can also take breakfast (closing 11:00) and lunch (closing 15:00). Measured on v9, that would expire 2,127 breakfasts and 383 lunches. That is left to the owner.

## Design note: pre-start phantom bookings (not implemented)

**Problem.** The capacity schedule is precomputed per cohort from minute 0. A run that starts mid-day cancels the tickets requested before its start, with a "before run start" receipt. Their planned workers still stay booked in the plan, which the audit counted as 125 phantom worker-minutes.

**Proposal.**
1. Make the schedule a function of `(cohort, start_minute)`. `cohort_schedule(cohort, start_minute)` drops routines whose `requested_at < start_minute` before scheduling, so capacity starts empty at the run's start. Cache it per pair (`lru_cache`) and build it once per distinct run start.
2. Make the timeline revision name the start minute, for example `…-v10-<cohort>@<start_minute>`. A run created with `started_at_minute` then persists the exact plan it executes, and `validate_timeline` and the runner select the plan by `(cohort, start_minute)` read from the run row.
3. Move plan selection in `community_control_composition`, the runtime, dashboard and queue views from "cohort from env" to "plan from the run row". This is the same change that would make several revisions loadable at once, and would also have allowed v8 runs to stay loadable here.

**Cost.** A full `community_75` build takes about 30 s and about 800 MB per distinct start minute. Runs therefore need a bounded cache, or a precomputed start-minute grid such as every 15 min.

**Why not done here.** The change spans plan identity, run creation, the runner, composition and four read views. It needs its own tested slice.
