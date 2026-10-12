# Clinician screen — careops-clinician-workspace-001 — 2026-10-12

## Audit
- Route: Admin → Residents & care → Clinician (`ClinicianTab.jsx`), so owner/admin only in the UI. There is no "clinician" role; the intended users are administrators and nursing leads.
- Its job: for one resident, how often they called for help, how fast staff answered, what the calls were about, against the previous period. Read-only analytics over `db.alerts`.
- Problems found:
  - no stated purpose ("Clinician Dashboard");
  - a failed load showed "No data for this resident yet";
  - event rows were dead ends;
  - the "AI summary" card was never filled (the stats endpoint has no narrative);
  - "Unresolved" mixed in weeks-old open test records with no flag;
  - `GET /residents/{id}/stats` was readable by any signed-in login, including kitchen staff.

## What changed
- `GET /residents/{id}/stats` (`backend/routes/resident_analytics.py`): owner/admin and nursing staff only (others 403, anonymous 401). Each window adds `unresolved_older`, the open records older than 72 h (same threshold as the Alerts board).
- Screen renamed "Resident care patterns". It states who it is for, what to do, and that it is not a medical record.
- Load states: no residents; loading; refused or failed load with the reason and Try again; no calls in the window.
- Each recent event opens the existing alert detail / close-out dialog. The stats refresh after a change.
- Open records older than 72 h are marked "older, needs review". The Unresolved card says how many are older than 3 days.
- The Summary card shows the existing briefing text (`GET /residents/{id}/briefing`, built from records, no AI call) with its own error state.
- Files: `ClinicianTab.jsx`, new `components/ClinicianRecentEvents.jsx`, new `lib/clinician.js`.

## Role matrix (resident stats)
| Role | Result |
|---|---|
| owner, admin | 200 |
| nursing staff | 200 |
| kitchen staff, front desk | 403 |
| anonymous | 401 |

## Tests
- Backend gate **566 passed, 0 failed, 31 skipped**. New `backend/tests/test_clinician_stats_access.py` covers the role matrix and the `unresolved_older` split.
- Frontend **84 suites / 614 tests**. New `clinicianTab.test.jsx` covers purpose, the older flag, the summary, an event opening the dialog, and a 403 shown as a reason rather than "no data". Build compiled.
- Browser and API on the dev backend `677e250`, with temporary labelled QA users that were removed afterwards: **14/14**.
  - The role matrix holds over HTTP.
  - At 1280 and 390 px: purpose and KPIs shown, summary filled.
  - Clicking an event of a resident with alerts (90-day window) opens the alert dialog.
  - No page overflow; 0 failed API calls.
  - Screenshots: `docs/reports/assets/2026-10-12-clinician/`.

## Limits
- Briefing still readable by any signed-in user (unchanged; used by other screens).
- The default resident is the first in the list.
- Not deployed.
