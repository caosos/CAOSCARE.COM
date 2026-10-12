# Therapy permission boundaries — 2026-10-12

Task `careops-therapy-permission-boundaries-001`. Synthetic data only; dev stack; no production change.

## Boundary the product supports
A Therapy request is **operational**: when, with whom (provider name), what kind (discipline), where, status.
There is no clinical store: no diagnosis, chart or therapy-note field. `PATCH /tasks/{id}` rejects unknown
fields (422), so `diagnosis`, `therapy_note`, `chart`, `clinical_notes` cannot be stored.
Staff notes are an operational update channel: the latest note is shown on the resident's screen and read
by Aria. The note dialog already says so.

## Role × action matrix (HTTP, `backend/tests/test_therapy_permission_boundaries.py`)
| Action on a Therapy request | Owner/admin | Front desk | Therapy staff | Other dept (nursing, housekeeping) | Resident / no login |
|---|---|---|---|---|---|
| Create | yes | yes (on the resident's behalf) | yes (work order pinned to Therapy) | create lands in own dept, never Therapy | room-bus request yes; work order 401; claiming front desk 401 |
| List / detail | yes | yes (reads all) | yes | not listed / 404 | 401 |
| Plan time, provider, discipline, location | yes | 403 | yes | 403 | 401 |
| Acknowledge / claim / start / note / complete | yes | 403 | yes | 403 | 401 |
| Cancel | yes | — | yes | — | 401 |
| Reopen | yes | — | — | 403 | — |
| Inspect | yes | — | 403 | — | — |
| Clinical fields (diagnosis, chart, therapy note) | 422 for all — not stored |
Resident view (`/tasks/resident-request/mine`, `/status`): only the resident-safe allow-list (no `assigned_to`,
`source`, `visibility_role`, `event_log`, `escalation_reason`); staff-only work orders and other rooms' requests
never appear.

## Gap found and repaired (the first one)
"Can't complete" (escalate) and supervisor review wrote their reason into `notes`, which the resident's screen
shows as the latest update. A staff-only reason (e.g. "needs a two-person assist") reached the resident.
Aria's spoken status already withheld it, so screen and voice disagreed.
Fix (`565cfa1`): the reason stays in `escalation_reason` / `review_note` and the history only; both dialogs now
say "Staff only: the resident and Aria do not see this". Staff still see the reason on the badge and in History.

## Evidence
- Backend gate 601 passed / 1 failed (the new test's own wrong body key, fixed) / 31 skipped; focused tests
  2/2 after the fix; related exception tests 9/9. Frontend 90 suites / 641; build compiled.
- Before the fix the new test failed with "the can't-complete reason reached the resident".
- Browser (headless Chrome, dev backend `565cfa1`, demo request `task_174c3cc487c1`, room DEMO):
  nurse at 390 px used Can't complete (dialog shows "Staff only"; no overflow); resident room screen at 390 px
  shows "Bringing a shoe horn." and not the reason (`02-resident-390.png`); Aria status has no reason;
  owner at 1280 sees the reason on the badge, review dialog says "Staff only"; after review the resident view
  shows neither text. Receipts: created → unassigned → in_progress → note_added → escalated → reviewed.
  Demo room reset afterwards. Screenshots in `assets/2026-10-12-therapy-permissions/`.
- No therapy staff login exists on the dev stack, so the Therapy column is API evidence only.

## Not changed
Completion notes, cancel reasons and reopen reasons remain resident-visible (operational outcome); their dialogs
do not yet say so. Front desk reads every request (existing design). Production `ff87c22` unchanged.
