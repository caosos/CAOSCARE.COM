# Kitchen and Transportation in the operations navigation — careops-ops-nav-kitchen-001 / careops-ops-nav-transport-001 — 2026-10-12

## What was wrong
- The Admin **Community** group (Operations overview and the department workspaces) listed Nursing, Maintenance and Housekeeping only. Kitchen had no requests queue in Admin at all; Transportation's four tabs sat under "Communication & requests".
- The Operations overview's department cards (Kitchen and Transportation included) were numbers with no way in.

## What changed (frontend only)
- `frontend/src/lib/adminTabGroups.js`: Community now has **Kitchen** and the four Transportation tabs (Transportation, Transport calendar, Ride log, Transport resources); they left Communication & requests, so no tab is in two groups. Tab values and `/admin?tab=` links are unchanged.
- `frontend/src/pages/Admin.jsx`: Kitchen tab = the shared `DepartmentQueue` for `kitchen` (same as Housekeeping).
- `frontend/src/pages/OperationsOverview.jsx` + `lib/opsOverview.js::departmentTab`: each department card's name opens that department's Admin workspace tab, or Departments (the shared board) for departments without one.

## Tests
- Frontend **80 suites / 601 tests** (new `lib/__tests__/adminTabGroups.test.js`: Community holds every department workspace, no duplicate tab values; `departmentTab` cases in `opsOverview.test.js`). Production build compiled. Backend unchanged.
- Browser (dev site, headless Chrome, temporary labelled "Demo - QA Admin", removed afterwards), 1280 and 390 px: **12/12** — Kitchen and Transportation tabs in Community; Kitchen card → "Kitchen requests" queue; Transportation card → Transportation screen; Therapy card → Departments; no horizontal overflow; 0 failed API calls. Screenshots: `docs/reports/assets/2026-10-12-ops-nav/`.

## Limits
Not deployed; production `ff87c22`. The Kitchen admin tab is the request queue; the menu stays under Communication & requests → Menu.
