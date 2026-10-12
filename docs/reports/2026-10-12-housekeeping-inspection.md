# Inspection of completed housekeeping work (careops-housekeeping-inspection-001), 2026-10-12

## Inspected first
Completed requests could be reopened with a reason (`task_actions.reopen`, receipted), but nothing recorded an
inspection (pass) and nothing tied a reopen to an inspection.

## Built (`a38d6d1`, `0ae2dac`)
- `POST /tasks/{id}/inspect` (`task_review.inspect`), owner/admin only, completed requests only:
  - **pass** → `inspection_result: passed`, receipt `task_inspected`; the request stays completed; passing again
    changes nothing;
  - **return** (note required) → the SAME request reopened through the existing receipted reopen (assignee kept,
    "Returned after inspection: …" as its note), then receipt `task_inspection_returned`.
  `inspection_result` rides in the receipts' before/after state.
- Queue: "Inspect" on completed rows for owner/admin (Pass / Return for correction dialog), "Inspected: passed
  (name)" on closed rows, "Returned after inspection: …" on the returned card (the duplicate note line is hidden,
  `0ae2dac`); history label "Inspection by …".

## Evidence
- `backend/tests/test_housekeeping_inspection.py`: open request 409; housekeeper 403; return without a reason 422;
  return reopens the same request with its assignee and Aria's status quotes the reason; corrected completion;
  pass; second pass no-op (one `task_inspected`); one workflow id; inspection receipts by admin_override.
  Removing the supervisor-only check fails it.
- Live (dev backend `a38d6d1`; demo room linens job task_636c8e374136, entered by the front desk earlier):
  housekeeper claimed/started/completed it → owner in Claude Chrome Inspect → Return "pillowcases not changed" →
  the same request back under "Assigned, not started" for the housekeeper with the reason (`01`) → housekeeper
  inspecting: 403 → housekeeper at 390 px saw the returned card, no overflow, no failed API calls (`03`) → Aria
  rt_jzd1fvsk_1791796144287: "…The latest note says it was returned after inspection…" → housekeeper completed the
  correction → owner Pass → "Inspected: passed (MICHAEL CHAMBERS)", Inspect button gone (`02`).
  Chain (one workflow id): created (front_desk_entry) → schedule_updated → assigned → in_progress → completed →
  reopened (owner) → inspection_returned (owner) → in_progress → completed → inspected (owner); no history entry
  without a receipt id.

## Gates
Backend 596 passed / 0 failed / 31 skipped at `a38d6d1`; frontend 89 suites / 636; build compiled (after `0ae2dac`,
frontend only). Production unchanged (`ff87c22`).

## Notes
`DepartmentQueue.jsx` is now 435 lines (over the ~400 split signal); the new behaviour sits in
`components/InspectionControls.jsx` and `ExceptionReview.jsx`, but the queue itself should be split next time it
grows (card rendering and the closed list are natural pieces).
