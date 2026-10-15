# CO-008 service model: dining and activities (plan v10)

Owner direction (Michael, 2026-10-15, #166/#168): correct how dining and activities are served before adding staff;
never shorten task durations to improve completion numbers; use a realistic evening staffing level for a
75-resident community, and keep any remaining shortage visible.

Branch `co008/service-model` (from `co008/v9-candidate`). Plan revision `living-community-timeline-v10-service-model`.
All numbers below come from the deterministic 90-day capacity schedule for `community_75` (planning, no database).
Every duration and mix below is a **simulation assumption**, not facility data or an assessment.

## What changed in the model

Source of truth: `backend/simulation/community_service_model.py`.

**Dining**
- Kitchen roles are now `cook` and `dining_server` (was one `dining_team_member` per shift).
  - Cooks hold prep, plating and dish/bussing work on their shift. They never take a resident service ticket (`community_role_eligibility`).
  - Dining servers serve residents in parallel at each seating.
- Seatings: breakfast from 07:30, lunch from 11:30, dinner from 17:00. Residents arrive one per minute over the first hour. Before, dinner arrivals were spread 17:00–19:28 and breakfast 08:10–10:38.
- Per-resident service time:
  - Dining room: 3 server-minutes (plate, settle, clear), unchanged from v9.
  - Apartment delivery: 8 minutes (walk the meal there). About one resident in eight eats in the apartment; v9 had one in two.
- Meals record service only, never what anyone ate.

**Activities**
- The activity is a 14:00 group session run by the coordinator on shift. It is not a resident ticket.
- Synthetic mobility (planning only, never a clinical finding):
  - 60% independent and 15% use a walker: both attend on their own, with **no staff ticket**.
  - 20% need an escort and 5% use a wheelchair: they get an **escort ticket** (8 min) before the session, starting 13:35.
- About one resident in seven prefers a one-to-one activity: a 20-minute coordinator visit, 14:30 onward.
- Attendance rotates: each resident attends three days in five.
- Before (v9), every resident got a 10-minute "offer and escort" ticket, staggered 14:00–17:42.

**Service windows:** dinner and apartment dinner close at 19:30; an escort closes at 14:30 (after the session starts, it is no longer an escort to it); one-to-one visits close at 18:30.

## Staffing (realistic evening level, 75 residents)

| Department | Role | Shifts per day (on site) | Headcount |
|---|---|---|---|
| Nursing | care aide | day 06–14 ×4, evening 14–22 ×3, night 22–06 ×2 | 15 |
| Nursing | med tech | 07–19 ×1, 19–07 ×1 | 3 |
| Nursing | RN | day ×1, evening ×1, night on call | 4 |
| Kitchen | cook | 05:30–13:30 ×1, 12:00–20:00 ×1 | 3 (was 0) |
| Kitchen | dining server | 06:30–14:30 ×2, 12:00–20:00 ×2 | 6 (was 4 "dining team member") |
| Activities | coordinator | 09–17 ×1, 12–20 ×1 | 4 |
| Activities | assistant | 11–19 ×1 | 2 (new) |
| Housekeeping, maintenance, transportation, front desk, administration | — | unchanged | 4 each |

Totals: **57 workers** (was 50) and **31 on-site shifts a day** (was 26). Evening (17:00–20:00) kitchen = 1 cook + 2 servers; evening activities = 1 coordinator + 1 assistant (until 19:00). Overnight care (2 aides + night med tech), maintenance hours plus on-call, and med techs 7-7 are unchanged.

## Before / after (community_75, 90 days)

| Measure | v9 | v10 service model |
|---|---|---|
| Dinners not served (window closed) | 2,577 / 6,750 (38%) | **5 / 6,750 (0.1%)** |
| Breakfast / lunch not served | not time-bound | 0 / 0 |
| Activity tickets | 6,750 "offer + escort" | 918 escorts + 540 one-to-one visits |
| Activity tickets not served | 3,060 (45%) | **0** |
| Residents attending a group activity on their own (no ticket) | — | 2,592 resident-days |
| Total tickets | 114,445 | 109,153 |
| Still queued at day 90 | 97 | 97 |

Meal and activity waits (simulated minutes, n / median / p90 / max):

| Service | Waits |
|---|---|
| Breakfast | 6,750 / 29 / 56 / 75 |
| Lunch | 6,750 / 7 / 10 / 15 (four servers overlap at lunch) |
| Dinner | 6,745 / 29 / 55 / 71 |
| Activity escort | 918 / 5 / 20 / 25 |
| One-to-one visit | 540 / 0 / 0 / 0 |

Department waits (median / p90 / max minutes):

| Department | Median | p90 | Max |
|---|---|---|---|
| Nursing | 14 | 104 | 246 |
| Kitchen | 14 | 53 | 636 (overnight snack calls) |
| Housekeeping | 51 | 903 | 1,382 |
| Front desk | 87 | 535 | 880 |
| Maintenance | 50 | 997 | 2,375 |
| Activities | 0 | 15 | 25 |
| Administration | 0 | 0 | 0 |
| Transportation | 0 | 0 | 853 |

Wait reasons, all tickets:

| Wait reason | Count |
|---|---|
| Staff busy | 79,272 |
| None | 26,459 |
| Department opening | 2,208 |
| On-call only | 942 |
| On-call response | 132 |
| Still waiting at day 90 | 97 |
| Qualified staff absent | 38 |
| Not served | 5 |

## Remaining failures: genuine shortage or modelling artifact?

| Finding | Classification | Why |
|---|---|---|
| Breakfast/dinner median wait ~29 min (p90 ~55) | **Genuine staffing shortage** | Two servers at 3 min/plate serve 40 residents an hour, against 60 arrivals an hour. Lunch, with four servers overlapping, waits 7 min. A third evening server would roughly halve dinner waits. Kept visible as the owner directed. |
| 5 dinners not served | **Genuine, marginal** | Apartment deliveries late in a backed-up seating. |
| 38 snack/tray calls wait for qualified staff | **Genuine model of policy** | Between 05:30 and 06:30 only the cook is on site, and cooks do not take service tickets. Night calls wait for the department to open. Whether night care staff should take snack calls is an owner decision. |
| Housekeeping p90 903 min, max 1,382 | **Modelling artifact** | Every apartment gets a full clean every day (6,750 tickets). Real assisted living cleans weekly, with daily light touches. Not changed here (outside this order). |
| Front desk median 87 min | **Mostly artifact** | Half of all residents ask for a family-call coordination every day (2,700 tickets). That volume is high. |
| Maintenance after-hours waits | **Genuine policy** | Non-urgent work waits for the day shift; urgent work calls in the on-call technician. |
| Nursing p90 104 min | **Genuine staffing** | Evening has 3 aides for 75 residents. |

## Not modelled as tickets (stated, not hidden)
- Cook prep, plating and dishwashing are the cook's shift. They are not individual tickets, so they do not show in queues.
- The group activity session itself is the coordinator's shift.
- Group escorts (one staff member bringing several residents together) are not modelled. Each escort-needing resident is one 8-minute ticket. That overstates escort labour slightly, and it still finishes before the session.

## Gates
- Simulator suites (`test_sim_community_*`, `test_living_community_*`, task detail, haiku boundary, ops metrics): **602 passed** (597 existing + 5 new in `test_sim_community_service_model.py`).
- Frontend: 119 suites / 775 tests passed.
- Updated pins: worker counts 50 → 57, on-site shifts 26 → 31, routine names, event counts and digests.
  - burn_in_10: 52,009 events, digest `48db0598…1742`.
  - community_75: 335,630 events.
