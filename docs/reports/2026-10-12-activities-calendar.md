# Activities calendar end to end — careops-activities-calendar-001 — 2026-10-12

## Cause of the empty schedule
Published activities end on 2026-10-03 on dev; production has no current published activities. The Daily schedule now names the last published day (coverage note, `4b270ef`).

## Fixed here
When the schedule (or menu) failed to load, the table still said "Nothing scheduled for this date yet" (or "No menu items for this date yet"). Both `ScheduleTab.jsx` and `MenuTab.jsx` now show "Could not load the … for this date. This does not mean it is empty." with Try again, and show the empty message only after a successful empty load.

## Trace (dev backend `4b270ef`, temporary Activities QA user, labeled activity)
1. Before: Aria's `get_todays_schedule` request (`GET /schedule/public/today`) had nothing for today. The Activities workspace Schedule tab said "no activities for today".
2. The Activities user pasted "3:30 PM Demo watercolor class … - Sunroom". It was saved as a **draft** and was not visible to Aria.
3. Publish calendar: Aria's request returned `3:30 PM · Demo watercolor class … · Sunroom · activity`. Receipts recorded: `schedule_content_uploaded`, `schedule_content_published`. The staff schedule listed it as published.
4. The resident room screen (`/kiosk/demo`, separate build reading the dev backend) showed the activity and its time at 1280 and 390 px.

**Result: 10/10. 0 failed API calls.** The labeled row, its receipts and the QA user were removed afterwards. Screenshots: `docs/reports/assets/2026-10-12-activities-calendar/`.

Schedule rows have no "owner" field. The place comes from the text after " - "; the publisher is in the receipt.

## Tests
- Frontend **86 suites / 621 tests**. New `menuScheduleLoadError.test.jsx`: for both screens, failure is not shown as empty, and Try again recovers. Build compiled.
- Backend unchanged; last gate 567 / 0 / 31 on `4b270ef`.

## Limits
Production activities still need publishing by Activities staff or Michael. Not deployed.
