# CO-008 room delivery: about 30 of 75 meals delivered (plan v11)

Owner correction (Michael, 2026-10-15, #166/#168): in a 75-resident community roughly 30 residents
have meals delivered to their rooms. Model that instead of the v10 one-in-eight assumption, without
shortening service times, and show any remaining shortage honestly.

Branch `co008/room-delivery` (from `co008/service-model` @ `8a7a845`). Plan revision
`living-community-timeline-v11-room-delivery`. The v10 run and its history are kept; v11 is a new plan
and a new run. Every number below comes from the deterministic 90-day capacity schedule for
`community_75` (planning only, no database). Every duration and mix is a **simulation assumption /
owner-informed operating estimate**, not facility data and not a clinical fact.

## 1. Room-delivery assumption

- **30 of 75 residents (40%)** have every meal delivered to the apartment, and **45 eat in the dining
  room**. The 30 are spread through the building (residents whose `(index-1) % 5` is 1 or 3), not grouped
  by room number. Resident-specific plans can override this later. Source of truth:
  `backend/simulation/community_service_model.py::meal_location_for`.
- Each seating is 75 resident tickets per meal: 45 dining-room and 30 deliveries (test
  `test_room_delivery_is_about_30_of_75_and_every_tray_takes_its_full_trip`).

## 2. Staff roles and shifts for meals

| Role | Shift | On site per day | Headcount |
|---|---|---|---|
| Cook (prep, plating, dishes; never a service ticket) | 05:30–13:30 ×1, 12:00–20:00 ×1 | 2 | 3 (unchanged) |
| Dining server | 06:30–14:30 ×2, 12:00–20:00 ×2 | 4 | 6 (unchanged) |
| **Meal delivery aide (new)** | **07:15–13:15 ×3 (breakfast + lunch), 16:45–19:45 ×3 (dinner)** | **6** | **9** |

- Who takes what (`community_role_eligibility._KITCHEN_ROUTINES`):
  - Deliveries go to delivery aides first; dining servers help when free.
  - Dining-room service goes to dining servers first; delivery aides help when free.
- Per meal, 5 people serve: 2 servers and 3 aides at breakfast and dinner. Lunch has 7, because 4
  servers overlap with the 3 aides.
- Whole community: **66 workers** (was 57) and **37 on-site shifts a day** (was 31). No other
  department changed.

## 3. Per-delivery duration

One staff member carries one tray per trip (`ROOM_DELIVERY_STEPS`):

| Step | Minutes |
|---|---|
| Tray pickup and check | 2 |
| Walk to the apartment (incl. elevator) | 4 |
| Hand-off and setup | 3 |
| Walk back to the kitchen | 4 |
| **Total per delivery** | **13** (was 8 in v10) |

Dining-room service is unchanged at 3 server-minutes per resident (plate, settle, clear). Durations are
never shortened to improve results; a test asserts every claimed ticket takes exactly its minutes.

## 4. Throughput: dining room vs room delivery

| Per meal | Residents | Minutes each | Staff-minutes | Share of meal labor |
|---|---|---|---|---|
| Dining room | 45 | 3 | 135 | 26% |
| Room delivery | 30 | 13 | 390 | 74% |
| **Total** | **75** | | **525** | |

- Breakfast and dinner have 5 serving staff, so 525 staff-minutes take about 105 minutes. Last tray
  delivered, median day:
  - breakfast 09:29 (seating opens 07:30);
  - dinner 18:58 (window closes 19:30).
- Lunch, with 7 staff, finishes by 13:06.

Over 90 days, tickets taken by each role:

| Meal | Dining room: servers / aides | Delivery: aides / servers |
|---|---|---|
| Breakfast | 2,181 / 1,869 | 1,771 / 929 |
| Lunch | 2,955 / 1,095 | 1,437 / 1,263 |
| Dinner | 2,140 / 1,910 | 1,756 / 944 |

Utilization over whole shifts: dining servers 41%, delivery aides 54%. Both are much higher inside meal
hours.
Peak meal queue: 27 (breakfast), 14 (lunch), 27 (dinner).

## 5. Served vs not served (90 days)

| Meal | Dining room served | Room delivery served | Not served |
|---|---|---|---|
| Breakfast | 4,050 / 4,050 | 2,700 / 2,700 | 0 |
| Lunch | 4,050 / 4,050 | 2,700 / 2,700 | 0 |
| Dinner | 4,050 / 4,050 | 2,700 / 2,700 | 0 |

Breakfast and lunch still have no service window (owner decision pending, unchanged by this order). They
are reported as served when claimed. Dinner closes at 19:30, and none was missed.

## 6. Waits (simulated minutes: median / p90 / max)

| Meal | Dining room | Room delivery |
|---|---|---|
| Breakfast | 14 / 27 / 35 | 13 / 26 / 35 |
| Lunch | 5 / 6 / 9 | 5 / 6 / 9 |
| Dinner | 14 / 26 / 34 | 13 / 26 / 34 |

Kitchen department overall: median 7 / p90 25 / max 636. The maximum is the overnight snack-call
policy, unchanged.

### Current staffing cannot do it (shown, not hidden)

With v10 staffing (2 servers per meal, no delivery aides) and the same 30 deliveries:

| Meal | Waits (median / p90 / max) | Not served |
|---|---|---|
| Breakfast | 91 / 169 / 193; last served about 12:00 | 0 (no window) |
| Lunch | 55 / 78 / 97 | 0 (no window) |
| Dinner | 51 / 98 / 105 | **2,927 of 6,750 (43%)** |

### Staffing sweep (delivery aides + dining servers on each meal shift)

| Aides + servers | Breakfast / dinner wait p90 | Dinner last done | Dinners not served |
|---|---|---|---|
| 0 + 2 (v10 staffing) | 169 / 98 | past 19:30 | 2,927 |
| 1 + 2 | 88 / 72 | 19:42 | 1,051 |
| 2 + 2 | 49 / 49 | 19:23 | 0 (7 min before close) |
| **3 + 2 (chosen)** | **27 / 26** | **18:58** | **0** |
| 2 + 3 | 27 / 26 | 18:58 | 0 |
| 3 + 3 or 4 + 2 | 11 / 11 | 18:42 | 0 |

**3 aides + 2 servers** is the smallest level that serves every resident in the seating period with
p90 under 30 minutes. 2 + 3 performs the same; 3 aides was chosen because delivery is 74% of the labor.

## 7. Remaining delays: genuine or modelling artifact?

| Finding | Classification | Why |
|---|---|---|
| Breakfast and dinner median 13–14 min, p90 26 | **Genuine staffing limit** | Keeping up with 75 residents in 75 minutes needs about 7 people (525 staff-minutes ÷ 75 minutes). 5 serve, so the queue builds and then drains about 1 h 45 min after the seating opens. Lunch, with 7, waits 5 minutes. One more person at breakfast and dinner brings p90 to about 11. |
| One tray per trip | **Conservative modelling assumption** | Many communities use carts carrying several trays per trip, which would shorten the walking. One tray per trip overstates delivery labor. Kept because the owner asked for each trip's full time. |
| Dirty-tray collection not modelled | **Modelling gap (understates)** | Picking trays back up after the meal is real labor, not yet a ticket. |
| Residents arrive one per minute in a fixed order | **Modelling simplification** | Real arrival is lumpier. |
| Housekeeping, front desk, maintenance and nursing waits | Unchanged from v10 | Same classification as the v10 report. Not touched by this order. |

## Changes

- `community_service_model.py`: `meal_location_for` (30/75), `ROOM_DELIVERY_STEPS`, `ROOM_DELIVERY_MINUTES`.
  Also `meal_of()` no longer returns "housekeeping" for `housekeeping_room_service`. There are no
  production callers; found by the new test.
- `community_role_eligibility.py`: kitchen meal routines and their roles in preference order.
- `community_staffing.py`: `meal_delivery_aide` headcount 9, with `meals_am` and `meals_pm` shifts.
- `community_timeline.py`: plan revision v11. Test pins updated; new room-delivery test.

## Gates

See the PROJECT_STATE entry and the #168 receipt for exact results. Those gates are:

- simulator suites;
- the full backend gate on the exact commit;
- real-MongoDB scratch acceptance;
- the loaded SHA and the new 1x run ID.
