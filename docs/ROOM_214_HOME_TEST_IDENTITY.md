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

## Conversation style for Michael (Room 214 only, 2026-10-21)

- **Where it lives:** `routes/owner_room_context.py::owner_style_block`, inside the verified owner-room block. It is added only on a verified Room 214 mint, just before `## How this call opens`, and it explicitly overrides the shared persona's offer/next-step/fill-silence suggestions for Michael.
- **What it says:** answer what was asked; match detail to the task; no offers or menus; use his name rarely; an unfinished thought gets at most "Mm?"; "stop"/"chill" gets one or two words; follow a barge-in and a change of topic; silence is fine; one reply per turn; a goodbye that is quoted or said to dot/ChatGPT does not close the call.
- **Profile:** Michael's resident record is `aria_guidance_profile: concise_natural`, receipt `rcpt_73c488f7d8b6`. Before 2026-10-21 it was unset, so he got the default `supportive_guided` hand-holding profile, which contradicted the owner block's "skip hand-holding".
- **Unchanged:** the shared persona and every other resident's profile. Interruption is mechanical (server VAD cuts Aria's audio when he speaks) and is untouched. The local goodbye detector already ignores quoted and other-addressee goodbyes (`frontend/src/lib/__tests__/endIntentAddressee.test.js`).

### Update 2026-10-21 20:30 CDT (prepared 1b3c5c2)
The general adult-to-adult style now lives in the `concise_natural` profile (`backend/aria_guidance_profiles.py`
`CONCISE_STYLE`), which REPLACES the persona's style sections for that profile only; `supportive_guided`
residents get the persona word for word. `owner_room_context.owner_style_block` keeps only what is specific to
Michael (unfinished thoughts, barge-in, builder rule, goodbyes to other assistants) plus real WRONG/RIGHT examples.
Closing line Goodnight./Goodbye. and Hi/Hello/Hey wake greeting are Room 214 only (7679104, loaded).
