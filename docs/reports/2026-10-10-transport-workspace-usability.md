# Transportation staff workspace usability

Date: 2026-10-10 (America/Chicago)

Branch: `agent/transport-workspace-workable`

Base: `integration/2026-09-27` at `0c266dbbb7aec3bcc6e754a6b0639ca8c097457a`

## Reported acceptance failure

The supplied browser screenshot showed `Demo - Pete Nash · Transportation` at
`/workspace`. The page identified itself as **Transportation workspace** and
showed the date navigation, Day/Week, My rides, All rides, Completed and History
controls. It did not show **New ride**, and the visible completed ride was not a
clear openable control. The only ride-level affordance was a small history icon.

This was current application behavior, not operator error:

- `TransportationCalendar.jsx` limited booking, changing, cancelling and
  assignment UI to owner, admin and front desk.
- The matching create/change/cancel, assignment-context and transportation
  resource read routes used `require_front_desk_or_admin`, so exposing only the
  frontend controls would still have failed for transportation staff.
- `TransportRunCard` did not provide a trip-details action; it exposed only the
  lifecycle and small per-rider action buttons.

## Implemented change

- Added `require_transport_coordinator`: owner/admin/front desk remain allowed,
  and staff whose department is `transportation` may coordinate rides.
- Applied that permission to ride create/change/cancel, assignment context and
  driver/vehicle reads. Driver and vehicle administration remains admin-only.
- Transportation staff now see **New ride** and may assign, change or cancel a
  trip from their workspace.
- The main ride summary is now a visible **Open trip details** button. The
  details dialog shows date, pickup/return, status, destination, driver, vehicle,
  capacity, riders, purposes and appointment text, with Change, Cancel and
  History actions where permitted.
- Transportation lifecycle receipts created from the transportation workspace
  now record `staff_ui`; only an actual front desk role records `front_desk`.

## Verification

- Frontend focused tests: **3 suites passed, 3 tests passed**.
  - transportation staff sees **New ride** and My rides/All rides.
  - the ride card exposes and invokes the open-details action.
  - the existing transportation calendar refresh test still passes with the
    details dialog present.
- Frontend production build: **Compiled successfully** (`335.75 kB` JavaScript,
  `13.75 kB` CSS, gzip sizes).
- Python compile check: passed for the changed backend modules and lifecycle test.
- `git diff --check`: passed.

The backend lifecycle test was extended to prove transportation staff can read
drivers/vehicles, create and change a ride, cancel it, and receive final
`transportation_changed` and `transportation_cancelled` receipts. It was not run
in this worktree because the backend test/runtime dependencies (including
FastAPI, Motor and the Mongo-backed test stack) were not installed or running.
That limitation is recorded rather than represented as acceptance.

## Remaining acceptance

On the integration development environment, sign in as a transportation staff
member and verify one bounded flow: create a trip, open its details from the
ride card, change it, cancel it, then inspect the final receipts. Separately use
an active trip to verify Departed and Ride completed remain available. Record
the runtime ref, browser evidence and receipt IDs.

No merge, deployment, service restart, production change, or audio/Hey Aria
work was performed.
