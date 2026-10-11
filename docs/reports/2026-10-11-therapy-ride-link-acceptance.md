# Ride for a therapy appointment — build + browser acceptance (careops-therapy-transport-link-001) — 2026-10-11

Dispatch (#129 comment 6108284581): from one labelled synthetic therapy task, a "ride needed" action must create or attach
**exactly one** ordinary transportation request; keep idempotency, authorization, canonical linkage, status visibility and
provenance-linked receipts; verify plan/reschedule and cancel/complete behaviour; one isolated browser run. No second store.

## What was built
- `backend/routes/task_ride_link.py` (new): `request_ride()` loads the appointment through the lifecycle `check` (its own
  authority rule: admin/owner, assignee, department member), requires a resident and a planned date, then calls the existing
  `submit_transport_request` core with the appointment's resident, room, date, time label and purpose, as `source front_desk`
  (staff-entered on the resident's behalf) with the staff member as actor. The core's own dedup makes an open ride for that
  resident on that date a re-request, so the appointment **attaches** to it instead of creating a second ride. The link is
  receipted on the appointment's chain (`task_ride_requested`, `provider_refs` = the ride's task id and origin receipt) and
  recorded on the ride's history (`linked_appointment`, carrying that receipt id). Fields: `StaffTask.linked_ride_task_id`
  (appointment) and `linked_appointment_task_id` (ride).
- Idempotent: while the linked ride is open, asking again returns it (`already_linked`). After the ride is cancelled, a new ask
  may create a new ride.
- Follow-through, hooked in the task routes: a change of the appointment's planned window (`PATCH /tasks/{id}` →
  `set_schedule`) moves the open linked ride through `change_request` (`transportation_changed`); cancelling the appointment
  (`POST /tasks/{id}/skip`) cancels the open linked ride through `cancel_request` with "Appointment cancelled: <reason>"
  (`transportation_cancelled`). A note-only PATCH does not touch the ride. Completing the appointment leaves the ride alone.
- Routes: `POST /tasks/{id}/ride`, `GET /tasks/{id}/ride` (the linked ride's status and real run facts; same authority).
  `transportation_voice_context.run_view_for_task()` extracted so the resident status view and this view share one source.
- Queue UI: a **Ride** button on a planned, open request with no open ride; a "Ride: …" line from the linked ride's record
  (requested / booked with time, driver, vehicle / departed / completed / cancelled with reason); history labels for the two
  new entries. `frontend/src/lib/rideLink.js` holds the wording and the button rule.

## Setup (silent, isolated)
Scratch DB `caoscare_therapy_acc` (public demo data + `therapy` department + synthetic therapist `Demo - Tess Ortiz PT`; one demo
driver and one demo van exist), backend `:8135` on this tree with providers blank, frontend `:3018` proxied to it, headless Chrome
(fake media, muted). Accounts via the normal login API: Dana Frost (front desk), Tess Ortiz (therapy), Pete Nash (transportation).
Resident `Demo - Gene Piotrowski` (3W04). The owner's browser and the shared dev DB were not touched; the two console errors are
the kiosk page's menu/schedule reads to caoscare.com from a non-production origin (EliteDesk-only env override).

## Result: 15 / 15 cases, 0 failed API calls, 0 page errors
| # | Case | Result |
|---|---|---|
| 1 | Unplanned appointment: no Ride button | PASS |
| 2 | Planned (10:00 AM, D+3) → Ride button appears | PASS |
| 3 | **Ride needed** → exactly one transportation request for the resident; card line "Ride: requested for 10:00 AM · D+3, not yet booked" | PASS |
| 4 | Ride button gone while the ride is open; API ask again → the same ride; still one ride | PASS |
| 5 | Ride carries the resident, room, date, time and the link back to the appointment | PASS |
| 6 | Appointment chain: one `task_ride_requested` receipt naming the ride, actor the therapist | PASS |
| 7 | Transportation staff see the ride on that day's calendar | PASS |
| 8 | Resident Home screen lists both the appointment and the ride | PASS |
| 9 | **Reschedule** to 2:00 PM, D+5 → the ride moved with it (`transportation_changed`), card line updated | PASS |
| 10 | Appointment history shows "Ride requested" with the ride id | PASS |
| 11 | **Cancel** the appointment → ride cancelled with "Appointment cancelled: …" (`transportation_cancelled`) | PASS |
| 12 | Resident ride status: cancelled, not booked | PASS |
| 13 | Second appointment on a day with an existing open ride (front desk pharmacy run) → **attached**, no second ride | PASS |
| 14 | Completing that appointment leaves the ride open for transportation | PASS |
| 15 | 390 px: therapy workspace with ride lines, no overflow | PASS |

Screenshots (`docs/reports/assets/2026-10-11-therapy-ride/`): `01_ride_requested`, `02_resident_home`, `03_rescheduled`,
`04_history`, `05_attached`, `06_390`. The demo ride was closed through the normal transportation cancel at the end.

## Tests
- Backend: new `tests/test_therapy_transport_link.py` — unplanned → 422 nothing created; nursing → 403 nothing created; create
  with both links and both receipts; transportation sees it; nursing cannot read the link view (403); resident ride status sees
  it; idempotent second ask; reschedule moves the ride (receipt before/after); note-only PATCH leaves the ride untouched; cancel
  cancels the ride with the reason; attach to an existing same-day ride; completing leaves the ride open. Gate totals in
  PROJECT_STATE.
- Frontend 70 suites / 564 (new `rideLink.test.js`, `departmentQueueRide.test.js`); CI build compiled.

## Observations / limits
- The demo ride was not auto-booked (driver hours / flex rules of the demo resources); the line truthfully says "not yet booked".
- A note-only PATCH never touches the ride; clearing the planned window does not change the ride either (someone cancels or
  changes it explicitly). The ride is not re-linked on reopen of a cancelled appointment; a new Ride ask creates a new one.
- Import note: the transportation core is imported lazily inside `task_ride_link.py` because `routes.transportation` imports
  `routes.tasks` for `_resolve_denorms` and `routes.tasks` imports this module for its hooks.
- Not deployed.
