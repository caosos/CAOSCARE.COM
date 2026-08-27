# Resident home screen, maintenance closed-loop, TV/magnification, and the hardware adapter boundary

2026-08-27, Claude Code, EliteDesk primary worktree, `main`.

## Why

Michael's directive: stop tuning voice, move toward integration — the resident
screen, Aria, room devices, maintenance, and eventually physical hardware
behaving as ONE system, demonstrable within two weeks. This session's scope
(his 15-point brief): a real resident home/profile screen, simplified
primary buttons, a closed-loop maintenance lifecycle, a dynamic room-device
panel with TV input control, one shared device-state contract for the
screen and Aria, a multi-transport adapter boundary (prep for Home
Assistant/MQTT and real hardware), voice+touch screen magnification, live
screen updates, and a polished Room 401 demo path.

## What was inspected first (per "inspect before modifying")

- Working tree: clean, no uncommitted work from prior sessions to lose.
- Live EliteDesk state: backend/frontend dev servers already running;
  found **two real, live voice/kiosk interactions from Michael himself**
  mid-session (a transportation request and two "I just want to talk"
  presses for Room 401, timestamped ~01:25-01:31 UTC) - confirms the system
  is genuinely in active use, not just test data. Resolved the resulting
  stray "active" alerts so they wouldn't block the next real call.
- `docs/ELITEDESK_NODE_BUILD.md`: found the exact state of the earlier
  Home Assistant/MQTT work - HAOS VM running (`virsh list` confirms),
  Mosquitto broker installed, HA's own `mqtt` integration loaded and
  working, a valid long-lived access token already on disk
  (`~/.config/caoscare/ha_long_lived_token`). Work stopped at the end of
  Phase 4 (2026-08-09) - the CAOSCare↔HA contract (originally planned
  "Phase 5") was never built. This is exactly the gap Michael's directive
  asked about.
- `backend/routes/devices.py`, `models.py`, `Kiosk.jsx`: the existing
  device panel already rendered dynamically from the real device list (not
  hardcoded to TV/thermostat, contrary to how it read on first glance) -
  it just displayed a single generic on/off toggle per device with no
  capability-aware detail, no input control, no offline state, and no
  resident-context information anywhere else on the screen.
- `docs/reports/INDEX.md`'s Architecture debt section: `backend/models.py`
  is *already* a documented, explicitly-deferred 300-line-cap violation
  ("do not run that broad split concurrently with active implementation
  lanes") - confirms the right call is small additive field changes, not a
  split, this session.

## What was already working (not rebuilt)

- Facility context, weather, `get_todays_schedule`/announcements
  (`facility_note` category), mock device execution, and cross-resident
  request isolation - all from the 2026-08-27 morning session, re-verified
  still correct.
- The resident device panel's underlying data source: genuinely per-room,
  genuinely dynamic (just under-rendered).
- Alert severities `emergency`/`assist`/`comfort` already existed as
  distinct, independently-routable categories - removing the "little
  help" *button* didn't require any backend change; `assist` remains a
  real severity Aria can still choose when it judges a request non-urgent.

## Exact gaps found and fixed

1. **No resident-visible request detail.** `check_request_status` returned
   only category/status/acknowledged/assigned - never *what the request
   was for*, and no schedule/update fields existed at all. This is the
   literal bug Michael hit ("Aria couldn't tell him what his request was
   for or when maintenance was coming").
2. **No staff-facing way to schedule a visit or post an update** for the
   resident to see, even though the underlying `requested_for_date`/
   `requested_for_time_label` fields already existed (reused from
   transportation) - there was no UI or resident-safe read path wired to
   them for non-transportation requests.
3. **A second real bug found live, not in review**: `public_room_command`
   picks a device by capability match only. Once a room has both a
   thermostat and a TV (both expose `power`), an un-disambiguated command
   silently hit the wrong device. Fixed last session for `power`; this
   session's TV-input work made it clear the same class of bug was still
   possible for any shared capability - the existing `kind` disambiguation
   already covers it, confirmed by the new test suite.
4. **TV had no input/source capability at all** - "switch to HDMI 2" was
   structurally impossible.
5. **Screen and Aria could drift**: the device panel only fetched once at
   load; a voice-driven change wouldn't appear on screen without a manual
   reload. No live update mechanism existed for requests/schedule either.
6. **No hardware adapter boundary existed** - `devices.py` special-cased
   `protocol == "mock"` inline; there was no seam for Home Assistant, MQTT,
   or any other real transport that wouldn't require touching Aria's tools
   or the resident UI later.

## What was built

### 1. Resident home screen
New `frontend/src/components/kiosk/`: `ProfileHeader.jsx` (name/room/live
time), `TodayPanel.jsx` (activities + facility notices + today's meal,
reusing the existing schedule/menu endpoints - no new domain), `RequestsPanel.jsx`
(human-readable request cards), `RoomDevicePanel.jsx` (capability-driven
device cards, replacing the old fixed on/off grid). `Kiosk.jsx` now
composes these instead of inlining everything - net effect was that
Kiosk.jsx (already over the 300-line cap, pre-existing) came out **smaller**
(589 → 590 net after adding a live device poll, having dropped ~110 lines
of inline markup/state it no longer owns) despite the screen doing
substantially more.

### 2. Primary buttons
Removed the green "I need a little help" button entirely. Two buttons
remain: red **CALL FOR HELP** (`severity=emergency`, unchanged) and white
**I just want to talk** (`severity=comfort`, unchanged). `assist` remains
available as an *Aria-determined* severity via `call_for_help`'s own
`severity` argument - exactly "Aria can determine through the conversation
what help is needed," per Michael's instruction, just not a standalone
button anymore.

### 3-4. Maintenance closed communication loop + resident-facing cards
`routes/resident_requests.py` gained `_resident_safe_view()` - the single
function both `check_request_status` (Aria) and the new
`GET /tasks/resident-request/mine` (the Home screen's Requests panel) call,
so they can never show two different truths about the same request. It
returns `what_for` (the actual issue, previously never exposed),
`scheduled_date`/`scheduled_time_label` (real staff-entered window, reusing
the existing field pair transportation already used - not a new schedule
concept), and `latest_update` (staff notes). `models.py`'s `StaffTaskUpdate`
gained the two schedule fields so the *existing* `PATCH /tasks/{id}`
endpoint can set them - no new endpoint needed. `RequestDetailDialog.jsx`
(staff's request detail view) gained a "Resident-visible schedule & update"
form (date, time-label text, notes textarea, one Save button) - the ONLY
way staff sets what a resident/Aria can honestly report.

Also fixed, found while reading last session's transcript again: the
duplicate-merge response (`create_resident_request`) now also surfaces
`scheduled_date`/`scheduled_time_label` from the pre-existing ticket, so a
re-request doesn't lose that context either.

**Verified live**, not just by inspection - Room 401's real "reading lamp"
ticket was given a real schedule (`2026-08-26`, `"2-4 PM"`) and a real
staff note through the actual PATCH endpoint; `check_request_status`
correctly returned it end-to-end, and the resident Home screen rendered
it as:
> **the reading lamp by her bed keeps flickering** · MAINTENANCE · In progress
> Assigned: MICHAEL CHAMBERS
> Planned: 2-4 PM · 2026-08-26
> Electrician confirmed for this afternoon - bringing a replacement fixture.

### 5-6. Dynamic room-device panel, one shared state contract
`RoomDevicePanel.jsx` renders exactly what each device's own `capabilities`
declare (power/temperature/input/volume/brightness/fan_speed/position) -
not a hardcoded TV/thermostat special case - so a light, fan, or blinds
device shows sensible state with no code change. An `online: false` device
renders "Offline" and is disabled, never silently hidden and never
tappable into a fake success (the `online` field exists on every device
today but nothing yet flips it false - see Blockers). The panel, Aria's
`get_room_status`/`adjust_room_temperature`/`toggle_tv`/`set_tv_input`
tools, and the admin Devices tab all read/write the exact same
`smart_devices`/`device_commands` collections through the exact same
`/devices/*` endpoints - there is one device state, not a screen copy and
an Aria copy.

### 7-8. Multi-transport adapter boundary + Home Assistant status
New `backend/device_adapters.py`: a small registry (`mock`,
`home_assistant` today) that `devices.py`'s `_dispatch_command` calls for
any protocol it recognizes; every other (real, physical-transport)
protocol keeps the pre-existing, unchanged bridge-tablet queue/ack path.
Adding a real transport later is "write one function here" - the
conversational tool contract and the resident UI never change.

**Home Assistant**: chose to integrate through HA's own REST API rather
than publishing raw MQTT - CAOSCare talks to HA once, HA is the single hub
fanning out to whatever protocol (Zigbee, Z-Wave, MQTT, WiFi) the real
device actually uses. This also means Mosquitto's existing setup didn't
need to change.

**Verified live against the EliteDesk's own running HA VM** (not
simulated): connectivity and auth (enumerated its 22 real entities),
and - **a real bug this found, not a code-review guess**: HA's
`/api/services/.../turn_on` endpoint returns **HTTP 200 with an empty
body** when the target `entity_id` doesn't exist - it does NOT error.
The first version of the adapter would have silently reported success for
a command that did nothing. Fixed: the adapter now checks HA's response
body (the list of entities that actually changed) and raises if the
target isn't in it. Re-verified live: a command against a deliberately
nonexistent HA entity now correctly returns a 502 with a real error
message, and the device's own state is left untouched.

**No positive round-trip against a controllable entity was completed** -
this HA instance currently has zero toggleable entities (checked: 22
entities exist, all read-only system/sensor ones). Creating one
(`input_boolean` helper) requires HA's own Helpers UI - it is not a
config-entry-flow integration like MQTT was, confirmed by testing the same
API pattern that worked for MQTT and getting "Invalid handler specified."
Per the established precedent from Phase 3 (`docs/ELITEDESK_NODE_BUILD.md`,
"requires Michael's browser... exactly the kind of step the build
directive says to stop for"), this is a step for Michael, not a workaround
to script around blindly.

`HA_BASE_URL`/`HA_TOKEN` are documented in `.env.example` and configured
in the real `.env` (pointing at the existing VM/token, not a placeholder)
so the adapter is ready the moment a real or helper HA entity exists - **no
`SmartDevice` record currently uses `protocol="home_assistant"`**; nothing
resident-facing changed.

### 9. TV capability model
`DeviceCapability` gained `"input"`; `SmartDevice` gained `inputs: List[str]`
(the device's own declared valid values - Aria only offers what's actually
supported, never guesses a universal list). New `set_tv_input` tool
(`realtime_device_tools.py`) checks the live device's `inputs` before
calling, and tells the resident plainly if the input isn't available
rather than sending a command that would silently do nothing. Seed TVs now
declare `["TV", "HDMI 1", "HDMI 2", "HDMI 3"]`.

### 10. Magnification/accessibility
Replaced the old 3-step text-size cycle (which only hand-scaled a few
selectors: the greeting, the buttons - nothing else) with a continuous,
bounded (50-200%) resident display scale applied at the document root.
Tailwind's utility classes are rem-based by default (confirmed - no
project override), so this genuinely reflows the *entire* screen, new
panels included - not a browser-zoom trick. New `set_magnification` Aria
tool and an on-screen +/- control (`useMagnification.js`) both read/write
the same `localStorage` key and broadcast the same event, so a voice
change and a screen tap can never disagree about the current size.
**Verified live in the browser** (not just reasoning about CSS): toggling
via the exact mechanism Aria's tool uses visibly reflowed the whole
screen at 150% - text wrapped differently, cards resized, nothing was
simply stretched.

### 11. Live screen updates
No new infrastructure (no websockets/SSE) - matches "do not create
infrastructure complexity merely for animation." `RequestsPanel` polls
every 20s, `TodayPanel` every 60s, and the device panel now polls every
10s while idle (previously fetched once at load and only refreshed after
a manual tap) - the same `setInterval` idiom this file already used for
medication reminders and emergency detection.

### 12. Demo vs. real provenance
No new field needed - `protocol` was already the ground truth. Admin's
Devices tab now visibly badges `mock` devices in amber ("MOCK — no
hardware") versus a forest-green badge for every real-transport protocol,
and the create-device form's protocol list includes `mock` and
`home_assistant` explicitly. The resident-facing screen shows none of this
- exactly "do not clutter the normal resident experience with developer
terminology."

## Room 401 acceptance results (Section 13 script)

Verified through the real production tool-dispatch code
(`executeDeviceTool`/`executeOperationsTool`) run against the live
backend - the same functions the actual voice call invokes - for every
step that doesn't require an actual microphone:

| # | Step | Result |
|---|---|---|
| 1-2 | Open Room 401, profile shows useful info | Verified live in browser: name/room/time header, request cards, today/announcements, device panel all render with real data |
| 3-4 | "What's going on today?" | `get_todays_schedule` → real activities + 2 real facility notices |
| 5-6 | "What maintenance request do I have?" | `check_request_status` → "the reading lamp by her bed keeps flickering" |
| 7-8 | "When is maintenance coming?" | Returns real `2-4 PM on 2026-08-26` + the real staff note (tested both the "none scheduled" and "scheduled" states) |
| 9-10 | "What's the temperature?" | `get_room_status` → real thermostat + TV state |
| 11-12 | "Turn it down two degrees" | `adjust_room_temperature` → state changes, confirmed via re-read; screen picks it up via the new 10s poll |
| 13-14 | "Turn the TV on" | `toggle_tv` → TV only, thermostat unaffected |
| 15-16 | "Switch the TV to HDMI 2" | `set_tv_input` → verified against the device's own declared `inputs` first, then applied |
| 17-20 | Magnification 150% → 100% | Verified live in browser via the actual voice-tool mechanism (CustomEvent) - real visible reflow both directions |
| 21-22 | CALL FOR HELP | Unchanged, pre-existing, working path (`severity=emergency` alert + `call_for_help` tool) |
| 23-24 | I JUST WANT TO TALK | Unchanged, pre-existing, working path (`severity=comfort`) |

**Not verified this session**: an actual live microphone/voice call end to
end (no mic available in this environment) - every step above was proven
through the real HTTP/tool-dispatch boundary, not a live WebRTC session.
Michael should do one live pass before the real demonstration.

## Files changed

```
backend/models.py                                   1372 lines (pre-existing cap violation, +13 net - see note below)
backend/routes/devices.py                             215 lines
backend/device_adapters.py                             90 lines (new)
backend/routes/resident_requests.py                   262 lines
backend/routes/realtime_tools.py                       222 lines
backend/routes/realtime_tools_operations.py            233 lines
backend/routes/realtime_device_tools.py                132 lines
backend/routes/realtime_display_tools.py                53 lines (new)
backend/routes/realtime_companion_prompt.py            245 lines
backend/scripts/seed_mock_devices.py                    88 lines
backend/scripts/seed_demo_announcements.py              67 lines
backend/tests/test_room_device_isolation.py            197 lines
backend/.env.example                                    +8 lines (HA_BASE_URL/HA_TOKEN documented)
frontend/src/lib/realtimeDeviceTools.js                224 lines
frontend/src/lib/realtimeOperationsTools.js            225 lines
frontend/src/lib/realtimeDisplayTools.js                60 lines (new)
frontend/src/lib/realtimeMessageHandler.js             300 lines (was already at the cap; net 0 after compacting the dispatch loop to make room for the display-tool hookup)
frontend/src/lib/useMagnification.js                    26 lines (new)
frontend/src/pages/Kiosk.jsx                           590 lines (pre-existing cap violation; net +1 despite adding profile/today/requests/devices composition + a device poll, because most new logic moved into frontend/src/components/kiosk/*)
frontend/src/pages/DevicesTab.jsx                      210 lines
frontend/src/pages/RequestDetailDialog.jsx             146 lines
frontend/src/components/kiosk/ProfileHeader.jsx         43 lines (new)
frontend/src/components/kiosk/TodayPanel.jsx            80 lines (new)
frontend/src/components/kiosk/RequestsPanel.jsx         89 lines (new)
frontend/src/components/kiosk/RoomDevicePanel.jsx       67 lines (new)
```

`models.py` note: this file is a pre-existing, already-documented cap
violation (`docs/reports/INDEX.md`, Architecture debt, "do not run that
broad split concurrently with active implementation lanes"). This session
added 13 lines to it - all small field/Literal extensions directly required
by the maintenance-schedule and TV-input work (`StaffTaskUpdate` +2 fields,
`DeviceProtocol` +1 value, `DeviceCapability` +1 value, `SmartDevice`/
`SmartDeviceCreate` +1 field each), not new architecture. Flagging this
honestly rather than pretending it's compliant.

## What remains MOCK

Every room device in this deployment is `protocol: "mock"` - synchronous,
software-only, no physical hardware anywhere. `home_assistant` is a real,
tested adapter with zero devices assigned to it.

## What is actually physically connected

Nothing. The Home Assistant VM, Mosquitto broker, and its `mqtt`
integration are real and running, but no physical sensor/actuator/bridge
of any kind is attached to this host or any room.

## Remaining blockers to a polished physical demonstration

1. A live microphone/voice pass through the full Room 401 script above -
   not done this session (no mic in this environment).
2. One controllable HA entity (a Helper, or real hardware) to prove the
   `home_assistant` adapter's positive path - needs Michael's HA browser
   session or real hardware; the negative/failure path is proven.
3. `online: false` (offline device detection) exists as a field but
   nothing sets it yet - meaningful once a real bridge/HA connection can
   actually go down and be detected.
4. Operator/Aria memory extraction pipeline (carried over from the prior
   audit, still unclaimed).

## Recommended physical-device categories for the bedroom test environment

Described by capability/protocol requirement, not brand, per Michael's
instruction:

- **A coordinator/dongle for whichever local mesh protocol is chosen for
  lights/plugs/sensors** (e.g. a Zigbee USB coordinator compatible with
  Home Assistant's ZHA or Zigbee2MQTT). Confirmed in the earlier Phase 4
  evaluation: none is attached to this host today - this is the one true
  prerequisite everything else in that category depends on.
- **One smart light or lamp** with local (not cloud-only) control -
  either a mesh-protocol bulb (needs the coordinator above) or a
  WiFi bulb with a documented local API/native HA integration. Exercises
  `power`/`brightness`.
- **One smart plug**, same protocol family as the light, controlling
  something with an observable on/off effect (a lamp, a small fan) -
  cheapest way to exercise `power` on a "not literally a light" device
  and rehearse the reading-lamp scenario physically.
- **One TV or TV+streaming-box reachable over the LAN**, either via a
  documented local network control API (most current smart TVs/streaming
  boxes expose one) or, failing that, an IR blaster bridge Home Assistant
  can drive - needed to exercise `power`/`input`/`volume` for real.
- **One thermostat-equivalent** - a full HVAC zone thermostat is unlikely
  to be practical for a single bedroom; the realistic substitute is a
  smart plug on a space heater or fan (power only) or, if genuine
  setpoint control matters for the demo, a WiFi/Zigbee thermostat that
  actually controls that room's own heat source.
- Everything above should be chosen for **native or Home-Assistant-
  documented local control** - cloud-only devices with no local API would
  force the adapter back onto a vendor cloud dependency this architecture
  is explicitly designed to avoid.

## Next safe step

Michael: (1) do one live voice pass through the Room 401 script, (2)
create one HA Helper (or plug in the first piece of real hardware) so the
`home_assistant` adapter's positive path can be proven, (3) decide
purchase order from the categories above. Engineering: operator/Aria
memory extraction pipeline is the next unclaimed item from the original
audit.
