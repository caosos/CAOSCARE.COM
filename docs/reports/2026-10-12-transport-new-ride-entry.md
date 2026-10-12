# Transportation "New order" control — careops-transport-new-order-001 — 2026-10-12

## What was found
- No control called "New order" exists in the integration source or in the production source (`ff87c22`). The ride-entry control is **New ride** everywhere it exists.
- By role, before this change:
  - **Front desk** (`/front-desk`): New ride in the header and Ride per resident. Works.
  - **Transportation staff** (`/workspace` → calendar): New ride. Works.
  - **Owner/admin, Admin → Transport calendar**: New ride. Works.
  - **Owner/admin, Admin → Transportation** (the daily operations screen, where the unresolved count lives): **no way to start a ride** — only Book on rows that already exist, plus a legacy "Seed 2-week schedule" button. This is the screen the owner was looking at; the missing entry point is the reported unavailable control.
- So the control is legitimate, not a duplicate: it should be the same canonical New ride, shown on that screen too.

## What changed
- `frontend/src/pages/TransportationTab.jsx`: a **New ride** button that opens the existing `TransportRideForm` (the same form the calendar and front desk use) and refreshes the report after a save. No new form, endpoint or record type; it posts to `POST /transportation/staff/request` (transport coordinators only).

## Tests
- Backend gate **550 passed, 0 failed, 31 skipped** (new `backend/tests/test_transport_new_ride_entry.py`: anonymous 401, nurse 403 with nothing written, admin creates exactly one request with a `transportation_requested` origin receipt by that admin, it appears in the report's unresolved list and the calendar's pending rides).
- Frontend **79 suites / 598 tests** (new `transportationTabNewRide.test.jsx`; it fails on the old screen). Production build compiled.
- Browser (dev site localhost:3000 → :8092, headless Chrome, temporary labelled "Demo - QA Admin", removed afterwards): **10/10** — New ride visible at 1280 and 390 px with no horizontal overflow; one ride created through the form; origin receipt by the admin; the ride appears in the Unresolved list (count 11 → 12) and the Transport calendar's pending rides; 0 failed API calls. The test ride and its receipts were deleted afterwards. Screenshots: `docs/reports/assets/2026-10-12-transport-new-ride/`.

## Limits
- "Seed 2-week schedule" on the same screen is a legacy hourly-slot tool and still unexplained to an operator (owner punch-list item on unexplained controls); not changed here.
- Backend unchanged, so no dev restart was needed; the dev frontend serves the change. Not deployed; production `ff87c22`.
