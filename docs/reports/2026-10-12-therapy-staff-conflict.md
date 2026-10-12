# Therapy staff double-booking — 2026-10-12

Task `careops-therapy-staff-conflict-001`. Synthetic/demo data; dev stack; production unchanged.

## Gap found
The planned-window check (`routes/schedule_conflict.py`) only compared one resident's own planned work. The same
provider or the same assigned staff member could be booked for two residents at the same time with no warning.
A provider-only change on already planned work was not checked at all.

## Change (`b7f6048`)
- The check also reads other residents' open planned requests on that day **in the same department** that share
  the provider name (case and extra spaces ignored) or the assignee. Those come back as `kind: "staff"` with what
  they share; same-resident overlaps are `kind: "resident"`. Same 60-minute slot, same "not checked" honesty for
  unreadable times, linked rides still not counted as a second commitment.
- `PATCH /tasks/{id}` now runs the check (after authority) **before writing anything**, also when only the provider
  changes on planned work. 409 `schedule_conflict` unless `conflict_override: true`; the override is recorded on the
  schedule receipt, or on the details receipt for a provider-only change (`result conflict_override`,
  `provider_refs` = the other requests), and in the history text.
- Wording: "Overlaps Gait training (therapy) at 10:30 AM, room 214 — same provider Tess Ortiz PT."
- Resident views (`/resident-request/upcoming`, `/mine`, `/status`) carry no conflicts and nothing about other residents.
- No provider registry: provider is the existing free-text field.

## Evidence
- `backend/tests/test_therapy_staff_conflict.py`: different provider OK; same provider (different case) refused,
  nothing written; provider-only change refused; non-overlap saved; nursing/front desk 403; override receipt and
  history; details-only override receipt; same assignee across residents refused; staff Upcoming shows both sides;
  resident views clean; a recurring occurrence carries the provider and is checked, moving it leaves the series at
  its time; a linked ride follows an overridden reschedule and is not a conflict. Disabling the staff check makes
  the test fail.
- Backend gate 603 passed / 0 failed / 31 skipped. Frontend 90 suites / 642. Build compiled.
- Browser (headless Chrome, dev backend `b7f6048`, owner, two demo residents 3W01/3W02): Plan dialog → conflict dialog
  names the other resident's appointment, room and "same provider" (`01-conflict-dialog-1280.png`); nothing written
  before the choice; Save anyway → Upcoming shows the overlap (`02-upcoming-1280.png`); 390 px shows it with no
  overflow (`03-therapy-390.png`); no failed API calls; override receipt `task_schedule_updated`,
  `admin_override:owner`; resident view clean; nurse plan 403. Both demo requests cancelled afterwards.

## Limits
No therapy login on dev (therapy-staff path is API evidence). Assigning someone (claim/assign) does not itself warn
about a double-booking; Upcoming shows it afterwards. Matching is by exact provider text, so "T. Ortiz" and
"Tess Ortiz PT" are different.
