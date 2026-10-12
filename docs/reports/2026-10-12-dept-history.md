# Department history in the queues — careops-dept-history-001 — 2026-10-12

## What was wrong
Admin department queues showed counts of open work. Finished work was hidden in a collapsed "Recently completed" list that left out cancelled requests, the closing note and time spent.

## What changed (frontend only)
- `lib/maintenance.js`: a `closed` bucket (completed and cancelled, newest first, same 20-item cap) and `closedLabel()` ("Completed by Carl · 25 min", "Cancelled by Ann").
- `DepartmentQueue.jsx`: "Recently closed (N)" replaces "Recently completed". It is open by default in admin queues. Each row shows the outcome, who closed it, when, time spent, and the closing note; History and Reopen are unchanged.
- The full per-department history with completer, duration, note and receipt counts remains on the department board (Admin → Departments → a department), built earlier.

## Tests
- Frontend **85 suites / 619 tests** (closed bucket order and label cases in `maintenance.test.js`). Build compiled. Backend unchanged.
- Browser (dev site, temporary QA admin, removed afterwards), 1280 and 390 px, Nursing / Maintenance / Housekeeping: **10/10**. Each history is open and shows outcome and closer, including a cancelled Housekeeping request with its note. No page overflow, 0 failed API calls. Screenshots: `docs/reports/assets/2026-10-12-dept-history/`.

## Limits
Shows the last 20 closed requests returned by the task list; older history is on the department board and in reports. Not deployed.
