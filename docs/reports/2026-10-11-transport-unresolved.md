# Transportation "Unresolved" count — careops-transport-unresolved-001 — 2026-10-11

Dispatch (#129 comment 6115882770): reproduce the owner-reported "11 unresolved"; make the count open a canonical filtered
list; every row opens the real record (owner, status, next action, receipt trail); reconcile the count to the records;
prove authorization, empty/error states, desktop/390 px; no copied store.

## Reproduction
Admin → Transportation ("daily operations") showed **Unresolved 11** on the dev stack: the dev database holds exactly 11
open transportation requests with no booked run or slot. Problems found: the tile was not clickable; the count covers open
rides on **any date** while the screen is framed as one day; the "Waiting / unbooked" list showed only room and date and no
row could be opened; a failed load left the page on "Loading…" forever; any signed-in user (e.g. nursing) could read the
whole transport report.

## What changed
- `backend/routes/transportation_report.py`: access now `require_transport_coordinator` (owner/admin, front desk,
  transportation staff; others 403). Open-ride rows (waiting/unbooked, upcoming, follow-ups) carry resident, room, purpose,
  date + time label, status, booked, owner, times asked, age, source, next action ("Book a pickup…", or "Resident has asked
  N times…") and the current/older classification. `total_unresolved` is the length of that same list;
  `unresolved_scope` says it is "Open ride requests with no booked pickup, on any date".
- `frontend/src/pages/TransportationTab.jsx` + new `components/TransportUnresolvedList.jsx`: the Unresolved tile ("· any
  date") opens the list behind the count; each row shows who/what/when/owner/status/next action, keeps the Book action and
  **Open**s the real request (`RequestDetailDialog`: status, owner, receipt timeline); the current-state names are clickable
  too; empty list says so; a 403 or failed load shows the reason with Try again (a refresh failure keeps the last report and
  says so).
- Found and fixed on the way (gate failed after 7 pm Central): `department_board.py` counted "completed today" by the UTC
  date string; now the facility-local date (`ops_overview_util.local_date`).

## Tests
- Backend gate **549 passed, 0 failed, 31 skipped** (+1 `test_transport_unresolved.py`: count = list = canonical record
  count; row fields and next actions; follow-up listed; front desk and transportation staff 200, nursing 403, anonymous 401;
  a row's record detail opens with its receipts). The earlier run's single failure was the department-board date bug above.
- Frontend **78 suites / 597** (new `transportUnresolved.test.js`: tile opens the rows, row opens the record, empty and
  forbidden states); build compiled.
- Browser (scratch stack): **8/8, 0 failed API calls** — API count = canonical records (2 = 2 there); tile shows it with
  "any date"; the list has exactly that many rows; the new ride's row shows resident, purpose, date/time, "no owner" and the
  next action; Open shows the real record with status, owner and timeline; nursing 403 / front desk 200; 390 px clean.
  Screenshots: `docs/reports/assets/2026-10-11-transport-unresolved/`.

## Limits
- "Any date" includes old open requests (the dev database's 11 are mostly mock, 34–63 days old, marked "older" in the list);
  closing them is an owner review action (Older, needs review / legacy close).
- Not deployed; production `ff87c22`.
