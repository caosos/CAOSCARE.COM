# Nursing exception lifecycle (careops-nursing-exception-lifecycle-001), 2026-10-12

## Found
Reassignment (`assign`) and cancel-with-reason (`skip`) existed. Missing: a way for a nurse to say "I can't
complete this" without cancelling it or leaving it sitting with her, and a supervisor step.

## Built (code `d16b3c7`)
- `backend/routes/task_review.py`: `POST /tasks/{id}/escalate` (reason required; assignee, a member of the
  department, or admin) keeps the request open, puts it back to pending and unassigned, sets `needs_review`;
  receipt `task_escalated`. `POST /tasks/{id}/review` (owner/admin only; note required) clears the flag; receipt
  `task_reviewed`; 409 if nothing is waiting. Both through `task_lifecycle.transition`; `needs_review` added to the
  receipt before/after state.
- Aria status: "Staff weren't able to finish it, so a supervisor has been asked to look at it. It's still open."
- Routing exceptions: new class `needs_review` (listed first).
- Queue (`components/ExceptionReview.jsx`): "Can't complete" button + reason, amber badge with the reason,
  "Mark reviewed" for owner/admin; history shows both steps with their reasons.

## Evidence
- `backend/tests/test_nursing_exception_lifecycle.py`: start → refusals (no reason 422; maintenance and front desk
  403, nothing written) → escalate (open, unassigned, flagged, receipt before/after, authority assignee) → Aria
  status → routing exceptions → review (nurse 403 nothing written, empty note 422, admin ok, second review 409) →
  reassign → complete → history; one chain, every history entry has its receipt id. Removing the supervisor-only
  check makes it fail.
- Live (dev backend `d16b3c7`, demo room request task_134116c5c444, synthetic resident):
  1. Demo nurse, headless at 390 px: Claim → Start → Can't complete with reason; badge shown, no overflow, no
     "Mark reviewed" for the nurse, no failed API calls (`01-nurse-cant-complete-390.png`).
  2. Typed Aria call rt_8ektlnec_1791788248058: "It's still open, Sam. Staff weren't able to finish it, so a
     supervisor has been asked to look at it."
  3. Owner in Claude Chrome (desktop): Mark reviewed with a note; flag cleared (`02-owner-reviewed-desktop.jpg`).
  4. Nurse claimed again, started, completed with a note (API, as the nurse).
  Receipts on one workflow id: resident_request_created → task_assigned → task_in_progress → task_escalated
  (assignee) → task_reviewed (admin_override:owner) → task_assigned → task_in_progress → task_completed.

## Limits
- Supervisor = owner/admin; there is no department lead role.
- No automatic escalation of a request nobody picks up (alerts have one; tasks do not).

## Gates
Backend 592 passed / 0 failed / 31 skipped at `d16b3c7`; frontend 87 suites / 628; build compiled. Dev backend loaded `d16b3c7` (guarded restart). Production unchanged (`ff87c22`).

## Correction and live reassignment (02:10–02:30 CDT)
The first DONE overclaimed: the admin "Assign to" dropdown had not been used live. Trying it found a real defect:
in the admin Nursing tab the list closed before a choice landed (no request sent), because `Row`/`Section` were
components defined inside `DepartmentQueue` (a new type every render, so every card was rebuilt; confirmed in the
page: the card element was replaced within 6 s). Fixed in `1af968f` (plain render functions); regression test
`departmentQueueStableCards.test.js` fails on the old code. Frontend 88 suites / 629; build compiled.

Live, demo request task_789c03588ae8 (raised through a typed Aria call, synthetic resident):
- Owner in Claude Chrome assigned it to Demo - Nancy Reyes RN with the dropdown ("Done"; `03-owner-assigned-desktop.jpg`).
- Receipt `task_assigned`, actor MICHAEL CHAMBERS, authority `admin_override:owner`, before `null` → after the nurse;
  same workflow id as the origin.
- Maintenance staff trying to change the assignment: 403.
- The nurse sees it under "Assigned to me" at 390 and 1280, no overflow, no failed API calls (`04-nurse-sees-assigned-390.png`).
- Typed Aria rt_62sib2cc_1791789384982: "Staff have acknowledged it… work hasn't started yet."
- Note: only one nursing worker exists on the dev stack, so this was assign (Unassigned → nurse), not nurse → nurse.
  Before the fix, my headless test as the nurse assigned and unassigned the same request (two receipts in the chain).
