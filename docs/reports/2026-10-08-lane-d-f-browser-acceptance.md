# RQ-015 — Lane D + Lane F browser acceptance (2026-10-08)

Tip tested: `integration/2026-09-27` `4d39d4b` (includes RQ-011 and RQ-012). Worker branch `bounded/accept-d-f`.

## Environment (isolated, torn down afterwards)
- Throwaway DB `caoscare_accept_df`, a copy of `caoscare_public_demo` (demo residents/staff only). Demo passwords were reset in the copy; the DB was dropped afterwards.
- Backend from this worktree on `:8088`; `OPENAI_API_KEY`, `RESEND_API_KEY`, Twilio and Home Assistant variables blank, so **no provider could be called**.
- Frontend dev server on `:3013`, proxied to `:8088`. Driven with headless Chrome over CDP (a small throwaway script, not committed), desktop 1280 px and phone 390 px.
- Setup done by API as the demo owner: an `activities` department and one Activities staff user (the demo seed has no Activities department).
- `:3000`, `:8092` and other worktrees were not touched.

## What works (observed in the browser unless stated)
**Kitchen** (demo user, lands on `/workspace`, "Kitchen workspace" with Requests and Menu tabs)
- Menu tab for an empty date says "No menu items for this date yet" and `/api/menu/public/today` returns `[]`: an honest empty answer.
- "Paste a menu" → "Add as draft": the received batch shows 6 items with the original text and a parse warning. **Public menu stays `[]`** while it is a draft.
- "Publish menu": the public endpoint (what Aria reads) now returns the 6 items, lunch and dinner.
- Correction: editing an item and "Save and publish" changes the public item at once; editing and "Save as draft" removes it from the public menu and leaves the other items.
**Activities** (demo user, "Activities workspace", Requests and Schedule tabs)
- "Paste a calendar" → drafts for two dates, 6 entries; the staff-hours line is marked "not shown to residents". **Public schedule for 2026-10-08 is unchanged while they are drafts.**
- "Publish calendar": the public list for the date is in clock order (untimed announcement first, then 9:30, 10:00, 2:00 PM, 3:00 PM) and the staff-hours line is absent. The next day's entries appear as well.
- Seeded, staff-created rows for the same date stay (an ingest never replaces staff-typed rows, as designed).
**Housekeeping** (demo user, shared request queue)
- Request raised through the resident request bus: Acknowledge, Claim, Start, Note, Complete (with a closing note), then History. Each step is its own timeline entry with name and time; the closing note is kept separately from the progress note; 6 receipts shown.
- The resident-facing status text follows each step: "no one has picked it up yet" → "Staff have seen it" → "<name> has taken it on — work hasn't started yet" → "is working on it now" (+ latest note with time) → no current request, and the completed request appears in history. No "on the way" claim anywhere.
**Communications (owner → Communication & requests → Email & notifications)**
- Provider cards read "Resend email - not configured" and "Twilio SMS - not configured", with the line that without a provider notifications are only recorded.
- Housekeeping requests produced notifications routed to department staff with status `logged`, shown as "Recorded only - not sent"; each is linked to its task. A request from the synthetic demo-room resident produced status `simulated` and `simulated: true, scope demo_room`.
- "Send test" with an address: toast and log row both "Recorded only - not sent". Nothing was shown as sent or delivered.
- Approved inbound senders: both lanes say "No approved senders - all email quarantined"; "No inbound email has been received."
- Phones & calls: empty-state text only ("No extensions configured", "No calls recorded"). Telephony remains unproven (no Asterisk/ATA/trunk here).
**Phone width (390 px)**: Kitchen Menu tab, Activities Schedule tab and Housekeeping queue have no horizontal overflow (scrollWidth equals clientWidth). No console errors on any page.
**Aria answer path**: the public menu and schedule endpoints Aria's tools read return the published, resident-facing rows only (see above). The tool wording is covered by `communityServices.test.js` (passes). A spoken question was not asked.

## Defects found
1. **FIXED — `simulated` notification status had no label and no filter.** The log showed the raw word "simulated" while other states had plain labels, and the status filter could not select it. Added the label "Simulated - not sent to anyone" and the filter entry (`frontend/src/lib/notificationDelivery.js`, `CommunicationsTab.jsx`) with a test in `notificationDelivery.test.js`. Verified in the browser after the fix.
2. **Reported — notification body says "Room: unknown" when a request is filed with a resident id but no room.** `backend/routes/resident_requests.py` lines ~202 and ~246 use `data.room` only, and the stored task also has no room in that case (so room-based dedup and `resident-request/mine` by room miss it). Aria's tool and the kiosk send the room, so this affects API callers (front desk path, tests, SIM) rather than the voice path. Small fix, but in the shared request service (`resident_requests.py` is at 400 lines): look the room up from the resident record. Left to the shared-core owner.
3. **Reported — menu paste parser, cosmetic.** Input "green beans. Vegetarian: Stuffed peppers." is kept as one item with the trailing period, and a trailing "." stays on the last dish of each meal. A mid-line "Vegetarian:" is not understood. Also, a lunch-and-dinner-only menu shows the warning "No section found for: breakfast", which reads like a fault. The parser is in `menu_ingest.py`, which another worker owns. Staff can fix the item in the edit dialog.
4. **Reported — Activities department is not seeded.** The demo seed has no `activities` department, so the Activities workspace cannot be reached until an admin adds one (documented in the lane notes).

## Not tested
Real inbound email, real provider delivery, Telnyx/Asterisk calling, a spoken Aria menu or schedule question, and transportation. No provider key is available in this stack.
