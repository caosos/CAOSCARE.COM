# Department dispatch made visible — careops-dept-dispatch-001 — 2026-10-12

## What was wrong
The owner saw Housekeeping work sitting unassigned and could not tell how work is dispatched. The admin queues (Nursing, Housekeeping, Kitchen) had an "Assign to…" list but said nothing about how requests arrive or who can take them. Production has one user, the owner, so every Assign list there is empty and nobody can claim department work; nothing on screen said so.

## What changed (frontend only)
`frontend/src/components/DepartmentDispatchNote.jsx`, shown on admin department queues (`DepartmentQueue` with `adminMode`):
- How work reaches the department: resident (Aria / room screen), front desk or staff requests are routed there and the department is notified; a staff member takes it with Claim, or an admin uses Assign to….
- Who works in the department (from the same `/staff/assignable` list the Assign menu uses).
- If nobody does: "No one works in {department} yet, so nobody can claim this work and the Assign list is empty. Add staff in Departments & staff → Users & access…".
- A failed roster load says it could not load, never "no one works here".

## Tests
- Frontend **83 suites / 612 tests** (new `departmentDispatchNote.test.jsx`: names listed, empty department, failed load not shown as empty). Build compiled. Backend unchanged.
- Browser (dev site, temporary labelled QA admin, removed afterwards), 1280 and 390 px: **8/8** — Housekeeping and Kitchen notes explain routing and name the staff, no page overflow, 0 failed API calls. The empty-department wording is covered by the component test only (every dev department has a demo member). Screenshots: `docs/reports/assets/2026-10-12-dept-dispatch/`.

## Limits
On production the note will say no one works in each department until real staff accounts exist with departments set. Not deployed.
