# Appointment details (provider, discipline, location) — build + browser acceptance (careops-therapy-details-001) — 2026-10-11

Dispatch (#129 comment 6108860768): on the existing canonical therapy StaffTask, optional **operational** provider name,
discipline and appointment location; authorization and provenance preserved; before/after receipted; truthful values in the
therapy queue, resident Home/schedule and Aria; create → edit → reschedule → visibility plus unauthorized refusal; focused tests,
gates, one isolated browser run. No diagnosis, clinical notes, provider registry, recurrence, billing, messaging, audio, deploy.

## What was built
- `StaffTask.provider_name` / `discipline` / `location` (free text; max 120 / 60 / 160; empty clears). Accepted by the existing
  `PATCH /tasks/{id}` (`StaffTaskUpdate`, unknown fields still rejected). No registry, no clinical content.
- `task_actions.set_details()`: one lifecycle transition per change (`task_details_updated`), same authority rule as every other
  step (admin/owner, assignee, department member); unchanged values are not a change (no write, no receipt). The three fields
  were added to the lifecycle's `STATE_KEYS`, so every receipt's before/after state carries them.
- Resident view (`/tasks/resident-request/mine`, `/status`) returns the three fields; Aria's spoken status says
  "Planned for <time> on <date> with <provider> (<discipline>) at <location>" from the task's own fields.
- Shared queue: the Plan dialog gains "With / Kind / Where"; the card shows "With: … (kind) · Where: …"; history shows
  "Details updated" with what changed. Resident Home screen request card shows "With:" and "Where:".

## Setup (silent, isolated)
Scratch DB from the public demo data + `therapy` department + synthetic therapist `Demo - Tess Ortiz PT`; backend `:8135` on this
tree (providers blank); frontend `:3018` proxied to it; headless Chrome; normal login API. Resident `Demo - Rosa Marchetti`
(3W05). The shared dev DB and the owner's browser were not touched. The two console errors are the kiosk page's menu/schedule
reads to caoscare.com from a non-production origin (EliteDesk-only env override).

## Result: 13 / 13 cases, 0 failed API calls, 0 page errors
| # | Case | Result |
|---|---|---|
| 1 | Front desk cannot set details on a therapy task: PATCH → 403, nothing written | PASS |
| 2 | Therapist's queue shows the appointment with no details line | PASS |
| 3 | Plan dialog offers With / Kind / Where | PASS |
| 4 | Plan with window + details → card "Planned: 10:00 AM · D+3" and "With: Tess Ortiz PT (physical therapy) · Where: Therapy room, 2nd floor" | PASS |
| 5 | One `task_details_updated` receipt (before `None` → after the values) plus one `task_schedule_updated` | PASS |
| 6 | Aria status: "… with Tess Ortiz PT (physical therapy) at Therapy room, 2nd floor." | PASS |
| 7 | Resident Home screen shows With and Where with the planned window | PASS |
| 8 | Edit Where → card updated, provider kept | PASS |
| 9 | Second details receipt: before "Therapy room, 2nd floor" → after "Clinic downtown, suite 4" | PASS |
| 10 | Reschedule keeps the details | PASS |
| 11 | History: two "Details updated" entries with their text, two "Visit window set" | PASS |
| 12 | Aria status after the edits names the new time and place | PASS |
| 13 | 390 px: queue with the details line, no overflow | PASS |

Screenshots (`docs/reports/assets/2026-10-11-therapy-details/`): `01_plan_dialog`, `02_card_with_details`, `03_resident_home`,
`04_history`, `05_390`.

## Tests
- Backend: new `tests/test_therapy_details.py` — nursing and front desk 403 with nothing written; 61-char discipline → 422 with
  nothing written; details + window in one PATCH → one details receipt with before/after (actor, `acts_for:therapy`) and one
  schedule receipt; history entry carries the receipt id; staff list, resident view and spoken status carry the values; edit →
  second receipt; repeating the same value is not a change; reschedule keeps details; admin clears a field (receipted, spoken
  without it); chain stays linked. Gate totals in PROJECT_STATE.
- Frontend 70 suites / 565 (plan test extended: five-field payload; card line). CI build compiled.

## Observations / limits
- The front-desk request form has no details fields: details are set by the department that owns the appointment (or an admin)
  in the Plan dialog, which is also where the window is set. The admin/front-desk detail dialog does not show or edit them yet.
- Not deployed.
