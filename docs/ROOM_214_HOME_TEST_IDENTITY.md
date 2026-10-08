# Room 214 home test identity (RQ-037)

Purpose: use Room 214's real lights (Home Assistant) and Aria with a test
identity ("Michael"), without adding conversations, memories, requests or
alerts to Helen Torres (`res_81b72be1e8b5`), the room's registered resident.

## How it works

- `Kiosk.resident_id` (optional, admin-set) pins a kiosk to one resident.
- `GET /residents/public/by-kiosk/{id}` returns the pinned resident instead of
  the room's resident (still only `resident_id`, `name`, `preferred_name`,
  `room`). A pin to a missing resident returns no resident; it never falls back
  to the room's resident.
- The room screen sends that `resident_id` with every session mint, request,
  turn and receipt, so all of those are keyed to the test resident. Request,
  status, history, continuity, operational-state and memory lookups already
  prefer `resident_id` over room.
- `POST /alerts` from the kiosk button (kiosk id only) uses the pin.
- `GET /kiosks/{id}/active-emergency` on a pinned kiosk returns only alerts for
  the pinned resident, so Helen's own pendant alert in room 214 does not start
  a session under Michael's identity.
- Only owner/admin can create or change kiosks (and so set a pin); the pin must
  name an existing resident.

## What stays shared (keyed by the room string `214`)

Devices (`smart_devices`, device commands), the room's Aria session lease, the
kiosk's room screen and room-keyed phone endpoints
(`telephony_endpoints.resident_for_room` still maps room 214 to Helen: a
telephone call from the room is not a home-test path; not changed).

## What is separate

Michael's test resident has room label `214-HOME`, so no second resident shares
room `214` and room-keyed lookups for 214 stay Helen's. Conversations, memories,
requests, alerts and receipts for the screen use his `resident_id`. His
requests default to room `214-HOME` only when the caller sends no room; the
room screen sends `214`.

## Run it (Michael or the coordinator, after review)

    cd backend
    .venv/bin/python scripts/setup_home_test_identity.py --dry-run
    .venv/bin/python scripts/setup_home_test_identity.py            # create + pin
    .venv/bin/python scripts/setup_home_test_identity.py --revert   # unpin

Defaults to kiosk `kio_dc8c06a19608`; `--kiosk-id` overrides. Idempotent. It
never edits another resident. Each pin/unpin writes a receipt
(`kiosk_pinned` / `kiosk_unpinned`, actor `system:setup_home_test_identity`).
Revert unpins only; the test resident and everything recorded under it are kept.
The resident is not marked synthetic (his conversations are real test data) and
is named "Michael Chambers (Room 214 home test)".

Restart the backend after merging (the running backend loads the code at start).
Not run against the shared `caoscare` database by this change.

## Not covered

Helen's real pendant events still raise alerts for Helen as before; they just
do not launch this screen while it is pinned. The demo kiosk is unaffected
(unpinned). A device credential for kiosks (so a screen cannot claim another
identity) is separate security work.
