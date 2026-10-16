# CO-008 staffing and capacity audit: living-community simulator

- Date: 2026-10-15 (04:44 UTC). Read-only audit. No writes, restarts or commits.
- Code: `CAOSCARE-OPS-WORKSPACE/backend` at `d466ca9`.
- Data: scratch DB `caoscare_sim_acceptance_live20261014b`. The resident DB `caoscare` was not touched.
- Active run: `simrun:living:f24c347040991ddde766`, plan `living-community-timeline-v8-player-raised-community_75`.
- Plan numbers come from `cohort_schedule("community_75")`: 114,475 raised events, 114,445 scheduled inside the 90-day horizon.

## 1. Night staffing, 19:00-07:00 (day 1 into day 2)

Source: `active_assignments` / `on_call_assignments`, sampled on the hour.

| Hour | Nursing on site (aide / RN / med tech) | Other on site | On call |
|---|---|---|---|
| 19:00 | 3 / 1 / 1 | kitchen 1, activities 1, front desk 1 | maintenance 1 |
| 20:00-21:00 | 3 / 1 / 1 | front desk 1 | maintenance 1 |
| 22:00 | 2 / 0 / 1 | front desk 1 | RN 1, maintenance 1 |
| 23:00-05:00 | 2 / 0 / 1 | none | RN 1, maintenance 1 |
| 06:00 | 4 / 1 / 1 | kitchen 1 | maintenance 1 |
| 07:00 | 4 / 1 / 1 | kitchen, maintenance, front desk 1 each | none |

The schedule matches the owner direction:
- 3 care staff are on site overnight: 2 aides and 1 night med tech.
- An RN is on call 22:00-06:00.
- Maintenance hands over to on-call at 15:30: minute 929 has tech 03 on site, minute 930 has tech 04 on call. On-call ends at 07:00, when the day tech arrives.

One caveat: the on-call technician never works any ticket. The capacity scheduler only books on-site workers (`community_capacity_schedule.py` docstring). In 90 days, 90 maintenance tickets carry `waiting_for_on_site_staff_on_call_only`. That includes high-priority call-cord and bed-alarm reports: median wait 16 min, max 970 min, n=332.

## 2. Qualifications: work given to the wrong role

**Defect.** The scheduler matches workers by department only. `_schedule_department` never reads `job_role`. Plan totals by role over 90 days:

| Routine | Care aide | Med tech | RN |
|---|---|---|---|
| morning_medication_reminder | 4,211 | 1,108 | 1,431 |
| evening_medication_reminder | 4,028 | 783 (11.6%) | 1,939 |
| shower_assistance | 4,481 | 841 | 1,428 |
| toileting (3 routines combined) | 13,384 | 3,880 | 2,969 |
| resident_call_check_on_me | 469 | 123 | 161 |

So 88% of medication reminders go to someone other than the med tech. At the same time the med tech and RNs spend their time on toileting, showers and room checks.

The live run shows the same pattern. Receipt `rcpt_5013e95bf692` has `medication_reminder_support:02` claiming `evening_toileting_transfer_support` for resident 058, and 4 of the 13 live completions were done by the med tech. Other departments map one-to-one, since each has a single role.

## 3. Overlapping tickets

- **Plan:** `peak_active_tickets` returns 1 for all 48 workers who ever hold a ticket. No overlaps.
- **Live:** among `staff_tasks` with `status: in_progress` in the active run, care_aide:08, care_aide:09 and med tech:02 hold one each. No worker holds two.
- **Enforcement:** the database enforces this with the unique partial index `living_tasks_one_active_per_worker` on (run_id, assigned_to). The executor also checks it (`_refuse_second_active_ticket`). Both checks are scoped to one run.
- **Hygiene risk:** the STOPPED run `68d9…` still has 11 `in_progress` and 28 `pending` tasks. They are held by the same synthetic IDs, including care_aide:08, care_aide:09 and med tech:02. Across runs, those workers therefore look like they hold two tickets.

## 4. Demand vs capacity, day 1

- Demand = hands-on minutes of tickets requested in the hour.
- Capacity = on-site worker-minutes in the hour.
- Queue = tickets requested but not yet claimed at the start of the hour.

| Department | Hours over capacity (demand / capacity) | Peak queue | Max wait in day-1 requests |
|---|---|---|---|
| Nursing | 08 (456/360), 09 (435/360), 13 (503/360), 14 (495/300), 21-23 (330/300, 306/180, 210/180) | 67 at 01:00 | 178 min |
| Kitchen | 08-10 (85-90/60), 13, 17-18 (90-95/60) | 24 | 651 min (dinner served the next morning) |
| Housekeeping | 11-14 (150-160/120), 17-21 (closed) | 16 | 1,014 min |
| Activities | 14-17 (200/120, 150/60 at 17:00) | 34 | 1,113 min |
| Front desk | 17-19 (130/60) | 21 | 726 min |
| Maintenance | 10, 12-14 (75-85/60), 04-06 and 17-19 (on-call only) | 17 | 2,294 min |
| Transportation, Administration | none | 1 | 0 / 734 (one late ride) |

Daily totals (demand / capacity, minutes):

| Department | Demand | Capacity |
|---|---|---|
| Nursing | 4,887 | 6,720 |
| Maintenance | 580 | 510 (over capacity for the whole day) |
| Housekeeping | 885 | 1,020 |
| Activities | 750 | 960 |
| Kitchen | 760 | 960 |

Over 90 days:
- 87,552 of 114,445 tickets wait for staff.
- Median waits: maintenance 554 min, activities 89, front desk 87, housekeeping 51, kitchen 28, nursing 11.
- 1,761 of 6,750 dinners (26%) and 2,047 of 6,750 activity offers (30%) are claimed on a later day.

**Request times are kept.** Each ticket's open event is written at `requested_at`. The claim receipt carries `requested_at_minute`, `wait_reason` and `waited_minutes`. Live example: resident 058 `requested_at_minute: 1374`, `waited_minutes: 41`. One nuance: the wait is counted from request + 5 min (`OPEN_TO_CLAIM_MINUTES`), not from the request itself.

**The wait reason is often wrong (defect).** It reflects the department's state only in the minute before the claim. Of 7,739 non-nursing tickets whose wait spans a closed period, 7,131 are labelled `waiting_for_available_staff`, not `waiting_for_department_opening`.

## 5. Task-duration assumptions (opinion, reasoned rather than measured)

These values are my judgement of typical assisted-living practice, not measured data:

| Routine | Current | Suggested | Reasoning |
|---|---|---|---|
| Shower assistance | 20 | 30-45 | Includes undressing, the transfer, drying, dressing and grooming. |
| Toileting / transfer | 8 | 10-15 | 2-person transfers and incontinence care run longer. |
| Meals, per resident | 3 | 5 for plated dining room service; 10-15 for a tray delivered to a room | Dining-room service is shared work, so per-resident time can be low. |
| Medication reminder | 3 | 5-10 | Med passes typically take 5-10 min per resident with prompting and documentation. |
| Room checks | 3 | 2-3 overnight | Reasonable as is. |
| Housekeeping room service | 10 (default) | 30-45 | Cleaning a room plus a linen change. |
| Activity offer and escort | 10 (default) | — | Escort is batched in reality. Per-resident escort for all 75 residents drives the activities backlog. |

## 6. Live run health (sim_runs at 04:43:52Z)

- **Clock:** state RUNNING, cursor 3,506 of 350,077, sim_minute 1,421 (23:41 day 0). Start was 1,347 (22:27). That is 74 simulated minutes over about 75.5 real minutes since `created_at` 03:27:32Z, so the clock is running at 1x. The highest receipt cursor is 3,505, which matches.
- **Pre-start events:** 3,409 events were cancelled as before-start (`after_state.not_simulated_before_run_start`).
- **Tickets:** 70 in total.
  - Nursing: 52 pending, 3 in progress, 13 completed.
  - Front desk: 1 pending. Housekeeping: 1 pending.
- **Oldest waiting ticket:** `day-000:resident-003:night_room_check`, requested at 1354, so 68 simulated minutes old. Its planned claim is 1476.
- **Overdue or off-shift:** no pending ticket is past its planned claim time. All 11 claim/complete receipt pairs were checked against `active_assignments`, and every worker was on site with the planned worker matching. Every simulated job took exactly its `work_minutes` (8 min of simulated time, about 8 real minutes).
- **Fast completions:** these were all by the human owner (Michael), not the simulator:
  - resident-046 toileting: `started_at == completed_at`, `assigned_to: null`.
  - resident-001 and resident-002 night checks: started and completed in the same instant, about 64 simulated minutes before their planned claim.
  - When the human takes a ticket, the simulator correctly cancels its own claim/complete with "Michael is working it".

**Phantom-busy workers (defect).** The plan still reserves care_aide:08, care_aide:09 and med tech:02 for 20 tickets that were requested before the start and then cancelled. That is 125 worker-minutes, lasting until minute 1393. The evening toileting tickets recorded waits of 34-41 min `waiting_for_available_staff`, but in the database those workers held nothing. Human work does not free planned capacity either: when Michael completes a ticket, the planned worker's slot still goes unused.

## Top defects and fixes

1. **Work is matched by department, not role.** Add a `routine → eligible job_roles` map, for example medication reminders to med tech and RN, and showers and toileting to aide first. Have `_schedule_department` filter `present` by role.
2. **Phantom-busy workers and fixed capacity.** Schedule capacity from the run's start minute so that tickets cancelled before the start reserve nobody. Rebuild the schedule, or reschedule incrementally, when a human claims or completes a ticket.
3. **Wrong wait reasons.** Record the main blocker over the whole wait, or the minutes per blocker, instead of only the state in the minute before the claim.
4. **On-call cover never acts.** Allow urgent and high tickets, such as call cords and bed alarms, to call in the on-call tech or RN. That needs an on-call-to-on-site transition with a receipt. Expire time-bound routines, such as dinner and the afternoon activity, rather than serving them the next morning.
5. **Unrealistic durations and orphaned tasks.** Raise shower, housekeeping, medication and toileting minutes (§5) and re-check maintenance capacity (580 min demand vs 510 available per day). Close or tag the STOPPED run's 39 open tasks so they do not appear as live work held by the same worker IDs.
