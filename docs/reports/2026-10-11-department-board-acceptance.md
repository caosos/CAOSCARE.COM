# Department board — build + browser acceptance (owner review P1 Departments & staff) — 2026-10-11

Owner operator review (16:49 CDT, captured in the living checklist): Housekeeping showed open/completed/skipped counts
but no department roster, per-worker assignment, dispatch trail or usable completed history; Activities the same.
Acceptance set by the supervisor: department page shows members and roles, open/assigned/in-progress/done work by named
worker, dispatch/status timestamps, completed history and receipts; an authorized manager can assign/reassign, staff act
within scope. Taken by the coordinator as the compatible slice while the Transportation LIVE_VERIFY waits on production
data (#129 comments 6114212326 / 6114353106).

## What was built
- `backend/routes/department_board.py` (new, 104 lines): `GET /departments/{slug}/board` — one READ over the canonical
  records, no new store (ENGINEERING_CONTRACT decisions 10–12): `members` (users who act for the department via
  `staff_scope.members_query`; name/role only), `by_worker` (an Unassigned bucket, then every member with their open work,
  then any non-member assignee by name), each row with lifecycle (`task_lifecycle`), timestamps and `trail` (the task's own
  `event_log`: created with its source, assigned, acknowledged, started, notes, each with who and when and its receipt id),
  `history` (latest closed work with completed-by, time, duration, note and the receipt count from `db.receipts`), and
  `counts`. Readable by owner/admin and by anyone who acts for the department (its staff; front desk for Administration);
  others 403; unknown slug 404. Every action still goes through the task routes.
- Frontend: `DepartmentWorkspaceDialog.jsx` (Admin → Departments → a department) now renders the board — a plain-language
  purpose line, counts (open / unassigned / in progress / completed today), Members & roles, Open work by worker (each
  card: what, resident, lifecycle badge, the dispatch trail, Acknowledge / Claim / Start / Complete / Assign / Receipts),
  Completed & closed (who, when, duration, note, receipt count, full history). Sections in `DepartmentBoardSections.jsx`;
  wording in `lib/departmentBoard.js`. A 403 shows why instead of an empty department.

## Tests
- Backend gate (isolated port/DB, OpenAI/HA blank): **543 passed, 0 failed, 31 skipped** (+1 `test_department_board.py`:
  members exclude other departments and carry no email; Unassigned / named-worker grouping; trail entries with by-name and
  times; completed history with note, duration and ≥5 receipts; counts; housekeeping member reads and can act; nursing and
  front desk 403 on housekeeping; anonymous 401; front desk reads Administration with front-desk users as members; 404 on an
  unknown slug; a reassign through the canonical route moves the row between workers).
- Frontend **76 suites / 589** (new `departmentBoard.test.js`: wording, one board read renders members/groups/trail/counts/
  history, Claim and Start post to the canonical routes and re-read the board, a forbidden board shows the reason); `CI=true`
  build compiled.

## Setup (silent, isolated)
Scratch DB `caoscare_therapy_acc` (public demo data: 6 demo staff across departments incl. housekeeping `Demo - Rosa Vega`),
synthetic `Demo - QA Admin`; backend `:8135`, frontend `:3018`, headless Chrome; resident `Demo - Rosa Marchetti`. The dev
DB and the owner's browser were not touched.

## Result: 11 / 11 cases, 0 failed API calls
| # | Case | Result |
|---|---|---|
| 1 | Admin → Departments → Housekeeping: members and roles listed | PASS |
| 2 | Unassigned work and the housekeeper's claimed work grouped by named worker | PASS |
| 3 | Dispatch trail: "Created (front desk) · just now" → "Assigned to Demo - Rosa Vega by Demo - Rosa Vega · just now" | PASS |
| 4 | Acknowledge and Start from the board → lifecycle "in progress", trail gains "Started by …" | PASS |
| 5 | Complete with a note → Completed & closed shows "Completed by …", the note, and a receipt count equal to the record (5) | PASS |
| 6 | Admin assigns the unassigned request → it moves under the housekeeper | PASS |
| 7 | Admin desktop: no page errors | PASS |
| 8 | Housekeeper reads their own board and may act (`can_assign`) | PASS |
| 9 | Nurse: housekeeping board refused (403) | PASS |
| 10–11 | 390 px: dialog renders with no horizontal overflow (scrollWidth 390); no page errors | PASS |

Screenshots (`docs/reports/assets/2026-10-11-department-board/`): `01_board_1280`, `02_board_completed_history`, `03_board_390`.

## Observations / limits
- The board is the admin Departments dialog; department staff reach the same data through their workspace queue and can
  call the board endpoint, but no staff-side board screen was added in this slice.
- Reassignment through the Assign select was exercised by API (the select is a Radix popover); Claim/Acknowledge/Start/
  Complete were clicked in the browser.
- Activities shows the same board (department-generic); it will be empty until Activities staff and requests exist.
- Not deployed; production `ff87c22`.
