# Front desk callback phone and best time (careops-frontdesk-callback-contact-fields-001, 2026-10-12)

Status: IMPLEMENTED / TESTED / DEV_ACCEPTED.

## Contract (same StaffTask, no callback entity)
| Field | Set by | Validation | Edited via | Seen by | Receipt |
|---|---|---|---|---|---|
| `callback_phone` | front desk entry (`source: front_desk`) only; public resident bus refused 422 | digits, spaces, `+-().` only; 7–15 digits; stored `+<digits>` (10 digits → +1) | `PATCH /tasks/{id}` → existing details step (authority as any lifecycle step; other departments 403) | staff who can read the request (front desk, admin, Administration); **not** in the resident view or Aria (allowlist) | creation: `resident_request_created`; edits: `task_details_updated` (history shows "ending 1234") |
| `callback_window` | same | ≤ 80 chars, trimmed | same | same | same |
Nothing records or claims that a call happened.

## Repair (`400b5b3`)
Failing before: `backend/tests/test_callback_contact_fields.py` (invalid phone accepted, fields ignored). Backend: `models.normalize_callback_phone`, fields on `StaffTask`/`StaffTaskUpdate`/`ResidentRequestInput`, public-bus refusal, details step masks the number in history. Frontend: New request form fields (staff-only note), `CallbackContactEditor` in the request detail (staff-only label; read-only for viewers who cannot edit).

## Gates
Backend 617 passed / 0 failed / 31 skipped; frontend 94 suites / 648; build compiled.

## Dev browser 8/8 (front desk Dana Frost, demo resident 3W03), 0 failed API calls besides the deliberate 422
Invalid phone "12" refused with "Callback phone needs 7 to 15 digits.", nothing created; "(555) 010-4321" + "after 2 pm" saved as `+15550104321`; Needs attention → Open shows the staff-only Call back section; window edited → `task_details_updated` `acts_for:administration`; 390 px usable, no overflow; resident status endpoint carries neither field; nurse edit 403; no call receipt. Cleanup: request, 2 receipts, 2 logged notifications removed.
