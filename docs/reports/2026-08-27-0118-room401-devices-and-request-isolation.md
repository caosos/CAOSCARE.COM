# Room 401 device layer + resident-request isolation — forensics and implementation

2026-08-27, Claude Code, EliteDesk primary worktree, `main`.

## Why

Michael asked for a post-outage continuation: inspect Room 401's actual recent
voice conversation, build a real mock room-device layer so Aria's device
tools stop 404ing, investigate a suspected cross-resident maintenance-request
data-isolation bug, and wire in daily announcements. Audit-before-code per
`AGENTS.md`; findings below are all from direct inspection of live Mongo data
and the actual running backend, not assumption.

## 1. Room 401 forensics — what was actually broken

Real session `rt_f2lx9y4s_1787791872323` (resident `res_0d3ef4252ae2`,
"Ellie" Whitfield, 2026-08-26 evening) was read in full. Facility context
(Conway, AR / weather / time) all worked correctly — that's the already-
shipped Step 1+2 work holding up. Every device interaction failed:

- `db.smart_devices` had **zero documents in the entire database** — no room,
  ever, had a real device record. `adjust_room_temperature` and `toggle_tv`
  both 404'd ("No devices in room 401").
- When the temperature tool failed, Aria (per her own instructions to be
  helpful) fell back to filing a maintenance ticket. `resident_requests.py`'s
  duplicate-detection key is `(category, resident_id-or-room, status open)` —
  it has no concept of *which* problem is open, only that some maintenance
  ticket is. Room 401 already had an **unrelated** open ticket ("reading lamp
  flickering," `task_80d1502aa830`, from 2026-08-23 seed data). The AC
  complaint silently bumped that lamp ticket's `re_request_count`, and Aria
  told Ellie: *"there's already a maintenance request in progress for the
  AC."* That's false — the open ticket was about the lamp. **Confirmed, real
  bug**, and the same pattern (fabricated/misattributed "already in progress"
  language) appears in every other room's conversation sampled (403, 404,
  408, and the TEST-1xx/2xx rooms) — always because `adjust_room_temperature`
  had nothing to talk to.

## 2. The reported cross-resident isolation bug — direct empirical result

Michael's framing was that a Room 401 maintenance request was being
presented as belonging to *other* residents/rooms. I checked this directly,
not by reasoning about the code:

- Read every room's `conversations` for any mention of "maintenance"/"lamp"
  across the whole database (403, 404, 408, TEST-1xx/2xx, 401) — every
  fabricated "already a request in progress" line traced back to **that same
  resident's own** open ticket (404's sink, 408's faucet, 403's fan, 401's
  lamp). No cross-resident content ever appeared.
- Traced `resident_requests.py` (`create_resident_request`,
  `resident_request_status`), `realtime_companion_prompt.py` +
  `realtime_companion_memory.py` (prompt hydration — no staff-task data is
  ever injected there, only `db.memories`), `resident_conversations.py`
  (admin session/task viewer), and the Kiosk/FamilyPortal frontends for any
  "latest request" or unscoped query. Every one filters by `resident_id`,
  falling back to `room`, falling back to `conversation_session_id` — never a
  bare "most recent" query.
- Wrote a live, deterministic test (`tests/test_room_device_isolation.py`,
  `TestRequestIsolation`) that creates real requests for Rooms 401 and 403
  through the actual public API, re-requests from 401, and confirms 403 and
  408 never see 401's task_id or get affected by 401's re-request. **7/7
  pass** against the running backend.

**Conclusion, stated plainly: cross-resident/cross-room isolation is intact.**
What actually happened, and what Michael heard, was the same-resident
cross-*issue* conflation described in §1 — a different, real, now-fixed bug,
not the one originally suspected. I'm reporting this distinction directly
rather than inventing a cross-resident fix for a defect that isn't there.

## 3. What was built

### Mock room-device layer
- `models.py`: `DeviceProtocol` gained `"mock"`. A mock-protocol device is
  identical in every other respect (same `SmartDevice`/`DeviceCommandInput`
  shape, same capabilities) so swapping a room to real hardware later
  (wifi/zigbee/HA/MQTT) needs no tool-schema or conversational change.
- `devices.py`: commands against a `protocol: "mock"` device execute
  **synchronously** (`status: "executed"`, real `acked_at`) instead of
  sitting `"queued"` for a bridge tablet that will never poll for it — the
  real hardware/bridge path (`queue`/`ack`) is unchanged.
- New `get_room_status` read tool (`realtime_device_tools.py`, split out of
  `realtime_tools.py` to stay under the 300-line cap) — Aria previously had
  *no way* to answer "what's the temperature in here" without guessing.
  Dispatches through the existing `/devices/public/by-room/{room}` endpoint,
  no new backend route needed.
- `scripts/seed_mock_devices.py`: seeded one thermostat + one TV per resident
  room (17 rooms), individualized starting temperature per room, via the
  real `POST /devices` + `POST /devices/{id}/command` endpoints (not direct
  DB writes) — same convention as `seed_mock_residents.py`.

### Real bug found and fixed while building this: device-selection ambiguity
`public_room_command` picked the first device whose `capabilities` matched
the requested `action`. A room with both a thermostat and a TV both expose
`"power"` — "turn the TV on" was silently landing on the thermostat (first
in sort order) instead. **Confirmed live**: a raw `power` command against
Room 401 changed the thermostat, not the TV. Fixed by adding an optional
`kind` field to `DeviceCommandInput`; the frontend (`realtimeDeviceTools.js`,
and the three pre-existing call sites in `Kiosk.jsx` — auto-mute-on-call,
restore-on-hangup, and the manual device-button panel, which had the exact
same latent bug) now passes `kind` on every write. An ambiguous command with
no `kind` and >1 candidate device now fails with a 400, not a silent
misroute.

### Duplicate-request truthfulness fix
`create_resident_request`'s duplicate-merge response now returns
`existing_summary` (what the *actual* open ticket is about) and `same_issue`
(whether it matches what was just asked). `realtimeOperationsTools.js` and
the `request_staff_help` tool description were updated so Aria reports the
existing ticket's real subject instead of implying it matches the new
complaint — directly fixes the false "maintenance request in progress for
the AC" line from §1. Verified live against a scratch TEST-101 request:
`same_issue: false`, `existing_summary: "the reading lamp is flickering"`,
and the resulting spoken message now names the lamp, not the AC.

### Daily announcements
Inspected `ScheduleItem`/`schedule.py` before building anything new: the
model already has a `facility_note` category, two weeks of future seed data
already include `facility_note` entries, and `get_todays_schedule` already
answers "what's going on today" from whatever's on file for the facility's
current date — **already fully working**, confirmed live in the Room 401
transcript itself. The only gap was that *today* had no `facility_note`
entries. `scripts/seed_demo_announcements.py` fills that one gap through the
same `POST /schedule` endpoint the Admin UI uses — no new domain, no new
tool, per "extend, don't duplicate."

## 4. Room 401 replay — before/after, live evidence

Ran the actual production `realtimeDeviceTools.js`/`executeDeviceTool`
dispatch (not a reimplementation) against the running backend for the exact
moments that failed in the real transcript:

| Ask | Before (real transcript) | After (verified live just now) |
|---|---|---|
| "What's the temperature in here?" | *(tool didn't exist)* | `get_room_status` → *"the TV is off; the thermostat is set to 72 degrees."* |
| "Turn it down two degrees" | *"there's already a maintenance request in progress for the AC"* (false) | `adjust_room_temperature(70)` → *"set the room to 70 degrees."* — confirmed via `get_room_status` |
| "Turn the TV on" | *"I couldn't reach the TV right now"* (404) | `toggle_tv(on)` → *"turned the TV on."* — confirmed via `get_room_status`, thermostat unaffected |

Room 401's device state was reset to baseline (TV off, 72°) after testing.

## 5. Isolation test results

`backend/tests/test_room_device_isolation.py`, run against the live backend:

```
TestRequestIsolation::test_room_401_and_403_requests_are_independent   PASS
TestRequestIsolation::test_room_408_has_no_request_in_clear_category   PASS
TestRequestIsolation::test_conversation_session_scoped_to_own_resident PASS
TestMockDeviceIsolation::test_rooms_have_distinct_seeded_state         PASS
TestMockDeviceIsolation::test_thermostat_change_is_room_scoped         PASS
TestMockDeviceIsolation::test_tv_power_is_room_scoped_and_disambiguated_by_kind  PASS
TestMockDeviceIsolation::test_ambiguous_command_without_kind_rejected_not_misrouted  PASS
7 passed
```

Uses real service/tool boundaries (public HTTP endpoints), not direct Mongo
writes.

## 6. What's still mocked / not fully verified

- Every room's device is `protocol: "mock"` — no real bridge tablet/hardware
  exists anywhere yet; this was true before this work and remains true.
  Swapping a room to real hardware needs a real device record with a real
  protocol, no conversational/tool change.
- This was verified through the exact production tool-dispatch code path
  (`executeDeviceTool`) against a live backend, but **not** through an actual
  browser/microphone session — no live voice call was placed during this
  work. Michael should still do one live acceptance pass.
- `check_request_status` (as opposed to `create_resident_request`) was not
  given the same `existing_summary`/`same_issue` treatment — it only ever
  returns one record it already knows the category of, so the same
  misattribution risk doesn't apply there, but it wasn't independently
  re-verified this pass.
- Pre-existing, unrelated: running the full `tests/` suite surfaced ~20
  failures / 99 errors, all traced to stale hardcoded credentials
  (`admin@caoscare.com`/`nurse@caoscare.com`, which don't exist in this DB —
  only the real owner account and one staff test account do) and two
  hardcoded stale expectations (`Lancaster, PA` weather default from before
  the Conway facility fix; devices seeded for old numeric rooms "101"/"108"
  that were never part of this environment). Confirmed by direct inspection
  that none of this was caused by today's changes — it's existing test debt,
  out of scope to fix here.
- `backend/models.py` (1359 lines) and `frontend/src/pages/Kiosk.jsx` (589
  lines) are both pre-existing, already-flagged violations of the 300-line
  cap (see `docs/reports/INDEX.md`'s Architecture debt section, dated
  2026-08-21/25: "do not run that broad split concurrently with active
  implementation lanes"). Both were edited today with small, additive,
  non-restructuring diffs (a Literal value + one optional field in
  `models.py`; three one-line call-site fixes for the device-kind bug in
  `Kiosk.jsx`) rather than made worse or refactored broadly.

## Files changed

```
backend/models.py                              (1359 lines, pre-existing cap violation, +16/-2 net)
backend/routes/devices.py                       192 lines
backend/routes/realtime_tools.py                220 lines
backend/routes/realtime_device_tools.py         109 lines (new)
backend/routes/realtime_tools_operations.py     226 lines
backend/routes/realtime_companion_prompt.py     245 lines
backend/routes/resident_requests.py             217 lines
backend/scripts/seed_mock_devices.py             86 lines (new)
backend/scripts/seed_demo_announcements.py       67 lines (new)
backend/tests/test_room_device_isolation.py     197 lines (new)
frontend/src/lib/realtimeDeviceTools.js         192 lines
frontend/src/lib/realtimeOperationsTools.js     219 lines
frontend/src/pages/Kiosk.jsx                    589 lines (pre-existing cap violation, +6/-6 net)
```

## Next safe step

Michael runs one real live voice call at Room 401 (or any seeded room) and
confirms the temperature/TV asks and a fresh maintenance request sound
right end-to-end through an actual microphone — everything above was proven
through the real HTTP/tool-dispatch boundary but not through an actual
WebRTC session. After that, the next unclaimed item from the original
device/memory/facility audit is step 3: give operator/Aria memory the same
automatic extraction pipeline resident memory already has.
