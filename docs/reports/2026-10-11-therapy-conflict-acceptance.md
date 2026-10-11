# Planned-window conflicts — build + browser acceptance (careops-therapy-conflict-001) — 2026-10-11

Dispatch (#129 comment 6109958604): detect overlapping open planned work for the same resident using the canonical
planned fields plus one bounded operational duration (no calendar store); show a truthful warning in the existing
Plan / detail / Upcoming workflow and require an explicit save-anyway choice; receipt the override; keep the linked-ride
reschedule behaviour; prove overlap and non-overlap, authorization, unparseable-time honesty, staff/admin/front-desk
behaviour, responsive layout and the `b229485` lifecycle-button rule. Out of scope: recurrence, new calendar storage,
clinical data, billing, messaging, audio, paid services, deploy, real-data mutation.

## What was built
- `backend/routes/planned_time.py` (new): the one parser of a planned time label into minutes ("10:00 AM", "2-4 PM" →
  14:00, "around 3 pm", "14:30"; `UNTIMED` when no clock time can be read). Shared by the upcoming view and the conflict
  check so both read a label the same way (extracted from the upcoming module).
- `backend/routes/schedule_conflict.py` (new): `find_conflicts(task, date, label)` — the resident's other OPEN requests on
  the same facility day whose 60-minute slot (`SLOT_MINUTES`, env `CAOSCARE_PLAN_SLOT_MINUTES`) intersects. A label with no
  readable time → `checked: false` with the reason (never "no conflict"); other requests with unreadable labels are listed
  as `undetermined`. A ride linked to an appointment is that appointment's transport, not a second commitment (its
  appointment is what overlaps); a standalone ride still counts. `GET /tasks/{id}/conflicts` (same authority as the other
  read views) previews what a window would overlap.
- `PATCH /tasks/{id}` (`tasks.py`): authority first (`task_lifecycle.check`, so a caller who may not plan the request never
  learns what else is planned), then the overlap check; an overlapping window is refused `409 schedule_conflict` with the
  conflicts unless the body carries `conflict_override: true` (`StaffTaskUpdate`, never stored on the task). With the
  override, `set_schedule` records it: history text "… saved despite overlapping <what> (<time>)", receipt `result`
  `conflict_override`, `provider_refs` = the overlapped request ids, plus the usual actor/authority/before/after. Note-only
  and details-only PATCHes never trip the check. The linked ride still follows an overridden reschedule.
- Upcoming rows (`/tasks/upcoming`) carry `conflicts` and `conflict_check` (the honest reason when unchecked).
- Frontend: `lib/scheduleConflict.js` (409 recognition, one wording, save-anyway payload), `ConflictDialog` in
  `QueueDialogs.jsx` ("This time overlaps other planned work" → Pick another time / Save anyway; the plan is not saved until
  chosen), wired into the queue's Plan save and the request detail dialog's Save; the Upcoming panel shows "Overlaps …" or
  "Overlap not checked: …" per row and now polls every 20 s so a plan saved beside it shows up.

## Tests
- Backend gate (isolated port/DB, OpenAI/HA blank): **542 passed, 0 failed, 31 skipped** (+1 `test_therapy_conflict.py`:
  non-overlap saved; preview names the overlap; 409 refusal writes nothing; save-anyway writes, history text and receipt
  `conflict_override` + `provider_refs` + before/after; both sides flagged in Upcoming; note/details PATCH untouched;
  unreadable time → not checked, listed as undetermined for others; cross-department nursing overlap; linked ride follows an
  overridden reschedule and is not itself an overlap; a standalone ride on a ride-free day does count; nursing 403 on the
  preview; front desk 403 (not 409) on an overlapping PATCH; anonymous 401; completed work does not count).
- Frontend **75 suites / 585** (`scheduleConflict.test.js` 3; queue plan test +2: refusal → Save anyway re-sends with the
  override, Pick another time leaves it unsaved; detail dialog +1; Upcoming view +1); `CI=true` build compiled.

## Setup (silent, isolated)
Scratch DB `caoscare_therapy_acc` (public demo data + therapy department + synthetic therapist + synthetic admin), backend
`:8135` (providers blank), frontend `:3018`, headless Chrome, normal login API; resident `Demo - Rosa Marchetti`. The shared
dev DB and the owner's browser were not touched.

## Result: 17 / 17 cases, 0 failed API calls
| # | Case | Result |
|---|---|---|
| 1 | Therapist plans B at 2:30 PM on the day A is at 2:00 PM → warning "Overlaps Physical therapy for the knee (therapy) at 2:00 PM." | PASS |
| 2 | "Pick another time" → B still unplanned, no receipt | PASS |
| 3 | Save anyway → B at 2:30 PM; one `task_schedule_updated` receipt with `result conflict_override`, `provider_refs [A]`, authority `acts_for:therapy` | PASS |
| 4 | History entry: "… saved despite overlapping Physical therapy for the knee (2:00 PM)" | PASS |
| 5 | Upcoming flags both sides: A "Overlaps Hip strength session … 2:30 PM", B "Overlaps … 2:00 PM" | PASS |
| 6 | Upcoming is honest about C ("afternoon"): "Overlap not checked: the planned time can't be read as a clock time …" | PASS |
| 7 | Move B to 4:00 PM → saved at once, no warning, that receipt carries no override | PASS |
| 8 | After the move, no overlap shown on A or B | PASS |
| 9 | Staff desktop: no page errors (the designed 409 is not an error) | PASS |
| 10 | Staff 390 px: overlap warnings render, scrollWidth 390 | PASS |
| 11 | Admin detail dialog: moving A to 3:00 PM (B at 2:30) → warning before saving | PASS |
| 12 | Admin Save anyway → 3:00 PM, receipt `admin_override:admin` + `conflict_override`, `provider_refs [B]` | PASS |
| 13 | The linked ride followed the overridden reschedule (2:00 PM → 3:00 PM, still open) | PASS |
| 14 | Admin: no page errors | PASS |
| 15 | Front desk: plan read-only, no plan form, no Acknowledge/Start/Complete (the `b229485` rule) | PASS |
| 16 | Front desk direct overlapping PATCH → 403 with no conflict details disclosed; nothing changed | PASS |
| 17 | Front desk: no page errors | PASS |

Screenshots (`docs/reports/assets/2026-10-11-therapy-conflict/`): `01_conflict_warning`, `02_upcoming_overlaps_1280`,
`03_upcoming_overlaps_390`, `04_admin_conflict_dialog`, `05_frontdesk_readonly`.

## Observations / limits
- One duration for every planned slot (60 min). A per-request duration was not added (no new field in this slice).
- Overlap is checked for the same resident only; staff double-booking (one therapist, two residents) is not checked.
- The resident's "Coming up" panel does not show overlap warnings (a staff decision, not a resident one).
- Not deployed; `main` `880d10f`, production `d7ff96a`.
