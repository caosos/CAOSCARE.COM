# Activities work view and navigation — careops-activities-work-001 / careops-activities-nav-001 — 2026-10-12

## What was wrong
- Activities had no work view in Admin: no request queue, no owner, no dispatch.
- The activities calendar sat only under Communication & requests → "Schedule" ("Daily schedule"), outside anything called Activities.

## What changed (frontend only)
- Admin → Community gains an **Activities** tab holding the Activities request queue (the shared `DepartmentQueue`: dispatch note, Claim / Assign to…, history) plus the activities calendar. The calendar is the same `ScheduleTab` and the same records as Communication → Schedule; nothing is copied.
- The Operations overview's Activities card opens this tab.

## Tests
- Frontend **85 suites / 619 tests** (`adminTabGroups.test.js` and `opsOverview.test.js` extended). Build compiled.
- Browser (dev site, temporary QA admin, removed afterwards), 1280 and 390 px: **12/12** — overview Activities card opens the tab, dispatch note shown, calendar and its coverage note on the same tab, no page overflow, 0 failed API calls. On dev no one works in Activities, so the note reads "No one works in Activities yet… set their department to Activities" — the empty-department case seen in a real browser. Screenshots: `docs/reports/assets/2026-10-12-activities/`.

## Limits
Activities requests only exist once residents or staff route them to Activities; no Activities staff accounts exist on dev or production. Not deployed.
