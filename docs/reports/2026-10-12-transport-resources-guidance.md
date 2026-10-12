# Transport resources guidance — careops-transport-resources-001 — 2026-10-12

## What was wrong
Admin → Transport resources listed drivers, vehicles and a scheduling buffer with no explanation of what they are for, what to set up first, or whether rides can actually be booked. Production has 0 drivers and 0 vehicles, and nothing on screen said that this is why rides wait unbooked.

## What changed (frontend only)
- `frontend/src/components/TransportSetupGuide.jsx` at the top of the screen: what the screen is for, four setup steps (drivers + hours, link a login, vehicles + seat count, buffer), and a status line.
- `frontend/src/lib/transportation.js::transportSetupStatus` computes that line from the real driver/vehicle lists using the booking engine's own rules (`transportation_engine.py`): a new ride needs an enabled non-flex driver and an enabled vehicle; a vehicle is shared only when its seat count is set. It says "Ready to book rides…" or "Rides cannot be booked automatically yet. Still needed: …", and notes when sharing is off because no vehicle has a seat count.
- Driver add row wraps at narrow widths.

## Tests
- Frontend **81 suites / 607 tests** (`transportSetupStatus` cases in `transportation.test.js`: nothing configured, flex-only, seatless vehicle = single rider + sharing off, disabled resources). Build compiled. Backend unchanged.
- Browser (dev site, temporary labelled QA admin, removed afterwards), 1280 and 390 px: **8/8** — status matches the dev data (3 drivers, 3 vehicles → ready), steps shown, no page overflow, 0 failed API calls. Screenshots: `docs/reports/assets/2026-10-12-transport-resources/`.

## Limits
Not deployed; on production (0 drivers, 0 vehicles) the line will read "Rides cannot be booked automatically yet. Still needed: at least one driver; at least one enabled vehicle."
