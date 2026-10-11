# Routing exceptions supervisor view — careops-routing-exceptions-001 — 2026-10-11

Dispatch (#129 comment 6115181807): a supervisor view over the canonical task / notification / receipt records that
filters undelivered, unassigned, overdue and failed-handoff requests; shows owner, age, latest action, exact delivery
state, retry/escalation state and receipt history; authorized list/detail/recovery APIs; counts reconciled to the records;
the current-operations classification preserved.

## What was built
- `backend/routes/routing_exceptions.py` (new, 156 lines), a read over open StaffTasks + `request_delivery` + receipts:
  - classes — **undelivered** (department not reached: notifications recorded only / none; never for simulated work),
    **unassigned**, **overdue** (real `due_at` past, or the planned date has passed), **failed handoff** (every notification
    attempt failed/bounced, or a refused lifecycle step `task_*_refused` on the request); a request can carry several;
  - each row: department, resident, owner, age, latest action (last `event_log` entry), delivery state + label,
    notification attempts, times asked, refused steps, receipt count, currency bucket;
  - `GET /ops/routing-exceptions?kind=&department=&include_review=` — admins see all; department staff see their own
    departments (front desk: Administration); others 403; current work by default, older records with `include_review`;
  - `GET /ops/routing-exceptions/{id}` — the row plus full receipts and notification records (404 outside scope);
  - `POST /ops/routing-exceptions/{id}/renotify` — re-sends the department notification through `notify_department`
    with a `department_renotified` receipt (before-state = delivery state); same authority rule as acting on the request.
    Assignment recovery uses the existing assign route.
- Frontend: Admin → Community → **Routing exceptions** (`RoutingExceptionsBoard.jsx`, `lib/routingExceptions.js`): class
  chips with server counts, an "Include older records" switch, rows with classes / owner / age / latest action / delivery /
  attempts / receipts, **Re-send** (only where the department was not reached) and **Open** (the request detail dialog).

## Tests
- Backend gate **548 passed, 0 failed, 31 skipped** (+1 `test_routing_exceptions.py`: one request per class plus a clean
  control; exact class sets; counts equal rows per class, per-kind filter and a direct record count; 422 on a bad kind;
  older record only with `include_review`; nursing/kitchen scoping, front desk sees neither, anonymous 401; detail with
  receipts and notifications, 404 across departments; re-notify receipted and adds a record, 403 from another department;
  assigning through the canonical route removes the unassigned class).
- Frontend **77 suites / 595** (new `routingExceptions.test.js`); build compiled.
- Browser (scratch stack): **11/11, 0 failed API calls** — chip counts equal the API; the undelivered + unassigned request
  shows both classes and "NOT notified"; the failed handoff shows its delivery state; the overdue request shows its owner
  and latest action; the Overdue filter lists only it; Re-send writes a receipt and a new notification record; Open shows
  the request detail with its delivery line; after the nurse claims it, Unassigned leaves the row but Not delivered stays;
  the nurse sees nursing exceptions only; 390 px clean. Screenshots: `docs/reports/assets/2026-10-11-routing-exceptions/`.

## Limits
- Without an email/SMS provider every routed request is "Not delivered" — truthfully; Re-send records a new attempt but
  cannot reach anyone until the provider is configured (RQ-005).
- "Overdue" uses due dates and planned dates only; there is no per-department response-time target.
- Not deployed; production `ff87c22`.
