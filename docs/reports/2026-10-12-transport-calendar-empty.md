# Transport calendar looked empty — careops-transport-calendar-001 — 2026-10-12

## What was wrong
- The calendar opens on today. When today had no rides it said only "Nothing scheduled", even when rides existed on other days.
- Most open ride requests are dated in the past (on the dev data, 10 of the 11 Unresolved). A request dated before today can never appear on a future calendar day, so the calendar looked empty while the Unresolved count was 11.
- The backend's default day used the UTC date, which is tomorrow after 7 pm Central.

## What changed
- `GET /transportation/calendar` returns `elsewhere`: the next three later dates with open rides (open runs plus unbooked requests), and `earlier_open_unbooked`, the number of open unbooked requests dated before today. "Unbooked" is the same rule as the Unresolved count: no run and no legacy hourly slot. For "My rides" it covers only the linked driver's runs. Default day is now the facility date.
- `frontend/src/components/TransportCalendarElsewhere.jsx`: under the calendar, "Next rides:" with one button per date (jumps the calendar there), and "N open ride requests are dated before today and will not show on any day here. They are listed under Transportation → Unresolved."

## Tests
- Backend gate **559 passed, 0 failed, 31 skipped** (new `backend/tests/test_transport_calendar_elsewhere.py`: next dates with counts, closed and legacy-slot requests not counted, completed runs not counted, facility-date default, nurse 403; it fails on the earlier code that counted legacy-slot bookings).
- Frontend **82 suites / 609 tests** (new `transportCalendarElsewhere.test.jsx`). Build compiled.
- Browser (dev site on `7a7cd92`, temporary labelled QA admin, removed afterwards), 1280 and 390 px: **14/14** — strip on an empty day, past-dated count, jump buttons move the calendar to a day that has a ride, no page overflow, 0 failed API calls. Dev counts agree: 10 dated before today + 1 later = 11 Unresolved. Screenshots: `docs/reports/assets/2026-10-12-transport-calendar/`.

## Limits
- The calendar's own day lists still treat a legacy-slot booking as pending (pre-existing; only the new summary was aligned).
- Not deployed; production `ff87c22`.
