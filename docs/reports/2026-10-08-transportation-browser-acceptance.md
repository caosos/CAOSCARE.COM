# RQ-020 — Transportation lifecycle browser acceptance (2026-10-08)

Tip tested: `integration/2026-09-27` `90a5d7d` (RQ-018/RQ-019 merged). Worker branch `bounded/rq-020-transport-accept`.

## Environment (isolated, torn down afterwards)
- Throwaway DB `caoscare_rq020_accept`, a copy of `caoscare_public_demo`. Its one old demo driver, vehicle, run and ride were deleted; all resources below were created in the UI. Passwords reset in the copy only; the DB was dropped afterwards.
- Backend from this worktree on `:8090`; `OPENAI_API_KEY`, `RESEND_API_KEY`, Twilio, Home Assistant blank, escalation loop off. No provider could be called.
- Frontend dev server on `:3014` proxied to `:8090`. Headless Chrome over CDP (throwaway script in `/tmp`, not committed), desktop 1280 px and phone 390 px.
- Aria requests: the **unchanged** `executeOperationsTool` from `frontend/src/lib/realtimeOperationsTools.js` (with `api.js` stubbed to the lane backend) ran `request_transportation`, `check_transportation_status`, `change_transportation_request`, `cancel_transportation_request`, `check_transportation_availability`. This is the exact code path Aria's tools use; no spoken audio was tested.
- `:3000`, `:8092`, other worktrees untouched.

## What works (observed)
**Resources (owner, Admin → Communication & requests → Transport resources)**
- Added drivers "Demo - Dana Driver" (Mon–Fri 08:00–16:00 via the hours dialog) and "Demo - Flex Fiona" (flex), vehicles "Demo - Van A" (3 seats) and "Demo - Car B" (1 seat). Table shows hours, flex flag, capacities.

**Resident request → pending** (Aria tool, residents 3W01/3W02)
- `request_transportation` with no pickup time → "request submitted … the front desk needs to coordinate the time, no confirmed time yet." Status → "still waiting … no confirmed pickup time yet". Never "on the way".
- A repeat ask is deduplicated ("asked 2 times"); the calendar card shows "asked 2x".
- A request naming "3 PM" the resident never said is refused with a clarifying question (422 → spoken message).

**Front desk (demo front desk user, `/front-desk` → Transportation)**
- Mon Oct 12 shows two "Needs coordination" cards with the resident's own words.
- Assign (pickup 09:00, destination "Conway Clinic", Van A picked from the list): card becomes "Pickup 09:00 · Confirmed" with destination, driver, vehicle; Aria status → "confirmed - … pickup at 09:00 … (driver …, Demo - Van A)".
- Second resident, same destination, "any free driver": joined the same run ("Shared ride — 2 residents").
- Aria `change_transportation_request` moved the second rider to Oct 13 11:00: new run (Car B), Aria "changed and confirmed", the first rider's run unchanged.
- New ride from the page header (pharmacy, Oct 12, 14:00): booked at once with Car B.
- Cancel with a reason (cancel dialog): card shows "Cancelled"; Aria status → "was cancelled - reason noted: Resident not feeling well".
- A Saturday ride with "any free driver": refused with a clear message (Dana works Mon–Fri; the flex driver is never auto-picked); the request stays pending; Aria still says "still waiting". Assigning "Demo - Flex Fiona" + Car B by name booked it.
- Aria-cancelled and re-cancelled ride: second cancel returns "couldn't cancel that (404)" (acceptable; see notes).

**Transportation staff (demo user, lands on `/workspace`)**
- Sees the same calendar, no Assign / Cancel / New ride (correct). "Departed" → Aria "has been marked departed by staff (pickup was 09:00)"; "Ride completed" → "is marked completed". Run shows Completed.

**History and receipts**
- Shared timeline (`RequestHistoryDialog`) shows, for the completed ride: created (aria voice), asked again (2x), ride booked by <front desk> with pickup/driver/vehicle, claimed/started/completed by the driver, each with name and time. For the cancelled ride: created (front desk), booked, the cancel reason as a note, and the closing entry.
- `GET /receipts?correlation_id=<origin receipt>` returns the same set as by-object lookup for all four checked rides. Every receipt has an actor, identity basis (room claim for Aria, authenticated for staff) and authority (`public_resident_bus` / `front_desk_transport` / `acts_for:transportation`); parent links unbroken; before/after statuses match the step. Chain for the completed ride: requested → re_requested → booked → departed → completed. Cancelled: requested → booked → cancelled. Aria-cancelled unbooked ride: requested → no_slot → cancelled.

**Phone width (390 px):** the calendar, pending/run cards, assign dialog (buttons on screen) and history dialog fit; no horizontal overflow; no console errors in any run.

## Defects found
1. **FIXED — calendar jumps back to today after "New ride" in the page header.** On the Front desk Transportation tab the header "New ride" saved the ride and then reloaded the calendar by remounting it, which reset the day to today ("Nothing scheduled") so the new ride was not visible. Fix: `TransportationCalendar` takes a `refreshKey` prop and refetches in place; `FrontDeskDashboard` passes it. Test `frontend/src/pages/__tests__/transportationCalendarRefresh.test.jsx`; re-verified in the browser (day stays Mon Oct 12).
2. **FIXED — refusal text "No a free driver and vehicle for 09:00 …"** (`transportation_assign.py`). Now "No free driver and vehicle is available for 09:00 on <date> - …" or "The chosen driver/vehicle is not available …". Test `backend/tests/test_rq020_transport_assign_message.py`.

## Observations (not changed)
- Two "New ride" buttons appear on the same tab (page header and inside the calendar); the header one now behaves correctly after fix 1.
- A rider added to a shared run gets the run's pickup time. Frank was assigned 09:15 but Aria tells him "pickup at 09:00" (the first rider's time). Accurate for the vehicle, but it overrides the time staff typed for him. Product decision.
- The shared timeline shows a cancelled ride as "Skipped by …" and a departed ride as "Started by …/Claimed by …" (shared-timeline wording, Lane E file; already noted in the Lane C entry).
- "My tasks today" in the transportation workspace does not list rides.
- Re-cancelling an already cancelled ride by voice says "couldn't cancel that (404)" rather than "that ride is already cancelled".
- The driver hours dialog opens with no day boxes ticked for a driver with no saved days after an earlier empty save; a fresh driver's defaults were not verified.
- Not exercised: Admin → Transportation report tab and the legacy slot screens; real email delivery; spoken Aria audio; real drivers/vehicles (none exist on any real DB — Michael must supply names, hours and seat counts).

## Tests
- Gate (`CAOSCARE_TEST_PORT=8091 CAOSCARE_TEST_DB=caoscare_gate_rq020 OPENAI_API_KEY= HA_BASE_URL= HA_TOKEN= backend/scripts/run_backend_tests.sh`): 305 passed, 0 failed, 31 skipped (tip baseline 304).
- Frontend: 38 suites / 285 tests; `CI=true yarn build` compiles.
