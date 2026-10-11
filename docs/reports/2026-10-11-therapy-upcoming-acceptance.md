# Upcoming therapy schedule — build + browser acceptance (careops-therapy-upcoming-view-001) — 2026-10-11

Dispatch (#129 comment 6109222803, addendum 6109259199): a facility-time, date-ordered upcoming therapy schedule for
authorized therapy staff and for residents, over the canonical StaffTask and resident-safe endpoints — planned time,
operational provider/discipline/location, lifecycle status and linked-ride truth; tests for authorization and stable
ordering; one isolated browser run (staff + resident, desktop + 390 px). Addendum: in the same run, an authorized admin
edits the details in the request detail dialog and front desk is truthful/read-only. No calendar store, recurrence,
conflict detection, clinical content, billing, messaging, audio, paid service, deploy or real-data mutation.

## What was built
- `backend/routes/upcoming_schedule.py` (new, 125 lines): two READS over `staff_tasks`, no new collection or copy.
  - `GET /tasks/upcoming?department=&days=` (signed-in staff): open requests with a planned date from the facility's
    today through today+days (`today_facility_date`), using the task list's own visibility rule (`staff_visibility_query`:
    a staff member sees only their department; owner/admin/front desk see all), narrowed to `department`. Each row carries
    the task fields, `lifecycle` + `spoken` from `aria_request_status.request_status_view` (the same words the resident
    hears) and `ride` = `task_ride_link.ride_summary` of the linked ride (real run facts, never a guess).
  - `GET /tasks/resident-request/upcoming?resident_id|room&days=` (public, resident Home screen / Aria): the same rows
    in the resident-safe view (`_resident_safe_view`, same scoping as `/mine`) plus `ride`.
  - Order: facility day → planned time label parsed to minutes (`time_minutes`: "9:30 AM", "2-4 PM" → 14:00,
    "around 3 pm", "14:30"; a label with no readable clock time sorts after the timed ones that day) → created → id,
    so two reads return the same order. A ride linked to an appointment is not a row of its own (it is that
    appointment's ride line); a standalone ride still lists for the resident.
- Frontend: `lib/upcomingSchedule.js` (day grouping, labels, wording from the record; reuses `rideLink.rideLine`),
  `components/UpcomingSchedule.jsx` (therapy workspace, "Upcoming", grouped by day: time, resident, what, lifecycle
  badge, details line, ride line), `components/kiosk/UpcomingPanel.jsx` ("Coming up" on the resident Home screen,
  hidden when nothing is planned). Mounted for `therapy` in `DepartmentWorkspace.jsx` and on `Kiosk.jsx`.
- Addendum repair: `RequestDetailDialog.jsx` now applies the backend's authority rule client-side (`actsFor` or the
  assignee): anyone else sees the plan and details read-only with the rule stated instead of a form the server would
  refuse. Front desk's direct PATCH is still refused by the server (403, nothing written).

## Tests
- Backend gate (isolated port/DB, OpenAI/HA blank): **541 passed, 0 failed, 31 skipped** (+1 `test_therapy_upcoming_view.py`:
  order C/untimed/B/A across two days; unplanned, completed, past-dated and the linked ride excluded; stable across
  reads; a claim changes lifecycle not order; nursing sees nothing of therapy, front desk and admin see it, anonymous 401;
  days=0 window; resident view in the same order with resident-safe fields and ride truth; standalone ride listed first on
  its day; room scoping equal; no scope → 400).
- Frontend **74 suites / 577** (new `upcomingSchedule.test.js` 3, `upcomingScheduleView.test.js` 2; `requestDetailDialogDetails.test.js`
  grows to 5 with the read-only / authority cases); `CI=true` build compiled.

## Setup (silent, isolated)
Scratch DB `caoscare_therapy_acc` (public demo data + `therapy` department + synthetic therapist `Demo - Tess Ortiz PT` +
synthetic `Demo - QA Admin`); backend `:8135` on this tree (providers blank); frontend `:3018` proxied to it; headless
Chrome; accounts via the normal login API (front desk = seeded `Demo - Dana Frost`). Resident `Demo - Rosa Marchetti`
(3W05). The shared dev DB and the owner's browser were not touched.

## Result: 25 / 25 cases, 0 failed API calls
| # | Case | Result |
|---|---|---|
| 1–2 | Therapist `/workspace` Upcoming: days in date order (D+1, D+2); items C (around 3 pm, D+1) → B (9:30 AM, D+2) → A (2:00 PM, D+2); unplanned request absent; the linked ride is not its own row | PASS |
| 3–4 | A shows "With: Tess Ortiz PT (physical therapy) · Where: Therapy room, 2nd floor"; C shows "Kind: speech therapy" | PASS |
| 5 | A carries the linked ride truth: "Ride: requested for 2:00 PM · D+2, not yet booked" | PASS |
| 6–7 | Lifecycle from the record ("Not yet picked up"); after the therapist claims B the order is unchanged and B reads "Taken on" | PASS |
| 8–9 | Staff desktop: no page errors; staff 390 px: renders, scrollWidth 390 | PASS |
| 10–11 | Resident Home screen 1280: "Coming up" lists C, B, A in date order; A shows time, With, Where and the ride line | PASS |
| 12–13 | Resident 1280: panel fits; only the kiosk's two known external reads (menu/schedule at caoscare.com) fail | PASS |
| 14–17 | Resident 390: same list and content; panel fits (right edge 358); same external reads only | PASS |
| 18 | Admin `/admin?tab=requests` → row A → detail dialog shows the details line and the With/Kind/Where form pre-filled | PASS |
| 19 | Admin edits Where → Save: location changed, provider kept, exactly one new `task_details_updated` receipt (authority `admin_override:admin`, before "Therapy room, 2nd floor" → after "Clinic downtown, suite 4") | PASS |
| 20–21 | Admin: no page errors; the therapist's Upcoming view shows the new location | PASS |
| 22 | Front desk `/front-desk` → All requests → row A: plan and details read-only, "Only therapy staff, the assignee or an administrator can change this plan."; no inputs, no Save | PASS |
| 23–24 | Front desk direct PATCH → 403, location unchanged; no page errors | PASS |
| OBS | Resident screen at 390 px: page-level scrollWidth 590 **pre-exists** (kiosk accessibility row: voice/contrast buttons + room label), unchanged with the new panel hidden — not this slice; recorded for the kiosk lane | noted |

Screenshots (`docs/reports/assets/2026-10-11-therapy-upcoming/`): `01_staff_upcoming_1280`, `02_staff_upcoming_390`,
`03_resident_coming_up_1280`, `04_resident_coming_up_390`, `05_admin_detail_dialog`, `06_admin_after_save`, `07_frontdesk_readonly`.

## Observations / limits
- Only `therapy` shows the Upcoming panel today (`UPCOMING_DEPARTMENTS`); the backend view is department-generic.
- Resident-screen 390 px overflow above is pre-existing kiosk layout, not fixed here.
- Same day, follow-up: the dialog's Acknowledge/Start/Complete buttons now follow the same authority rule as the plan form
  (hidden for a viewer the server would refuse; still offered to department staff, the assignee and admins). Component tests
  cover both; frontend 74 suites / 578; build compiled. Not browser-run.
- Not deployed; `main` `880d10f`, production `d7ff96a`.
