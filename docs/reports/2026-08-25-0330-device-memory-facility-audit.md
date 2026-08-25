# Device control + memory + facility-context audit

_Pre-implementation audit per Michael's directive. No code changed this
pass except one empirical test against real (mock-resident) data via the
existing public API, described and justified below — no schema/route/
prompt change made._

## Executive summary

Three separate, previously-undocumented root causes found, each precise
and each confirmed from source/data rather than inferred:

1. **A real facility record exists** (`Brookdale Senior Living
   Communities`, Conway AR address) in `db.facilities` — but the Realtime
   voice system **never reads `db.facilities` at all.** It reads two flat
   environment variables instead, one of which (`FACILITY_LABEL`) is still
   a leftover dev placeholder (`"the EliteDesk node"`). The Admin-configured
   facility and the voice system have never been wired together.
2. **The facility record itself has a data-entry bug**: its `timezone`
   field contains the literal text `"conway ar 72034"` — not a real
   timezone. This is a symptom of a deeper model gap: the `Facility` model
   has no structured city/state/zip/lat/lon fields at all, only a single
   free-text `address` string and an unvalidated `timezone` string.
3. **Resident-facing memory (write → extract → hydrate) is verified
   working end-to-end** by direct empirical test against a real mock
   resident. **Operator/Aria memory (Michael's own personal assistant) has
   no automatic extraction pipeline at all** — confirmed by grep: the only
   writes to `db.aria_memories` anywhere in the codebase are the manual
   CRUD endpoints. Anything said to operator-Aria is stored verbatim
   (`db.aria_conversations`) but never promoted to what a future session
   actually reads.

Device control has a real, not-yet-triggered truthfulness gap consistent
with what Michael described: the tool path can tell Aria "done" the moment
a command is *queued*, before any bridge tablet has executed or
acknowledged it — it just hasn't been visible yet because no bridge
tablet/real hardware exists for the mock rooms tested, so every command
in practice fails honestly at the "no device found" stage instead.

---

## A. Current device-control execution path

`adjust_room_temperature` / `toggle_light` / `toggle_tv` (Realtime tool
calls) → `frontend/src/lib/realtimeDeviceTools.js` → `POST
/api/devices/public/room/{room}/command` → `backend/routes/devices.py:
public_room_command()`:

1. Finds a `smart_devices` record in that room whose `capabilities`
   include the requested action.
2. Inserts a `device_commands` document with `status: "queued"`.
3. **Immediately, optimistically overwrites `smart_devices.state`** with
   the requested value — before any bridge tablet has picked up or
   executed the command (`devices.py:138-142`).
4. Returns the queued command doc with HTTP 200.

The frontend tool wrapper treats any HTTP-success response as `ok:true`
and has Aria speak a **completed-fact** confirmation ("set the room to 72
degrees," "turned the light on") — there is no code anywhere in this path
that waits for or checks delivery/acknowledgment before that confirmation
is spoken. **This is the exact fabrication risk Michael described**: a
successful HTTP response for queuing is currently sufficient to produce a
"done" statement.

This has not yet caused an observed false-success failure in the field,
specifically because no `smart_devices` are provisioned for any of the
mock rooms tested this session — `public_room_command` returns 404 ("No
devices in room X") every time, which the frontend correctly surfaces as
an honest failure ("I tried to adjust the temperature, but the system
couldn't reach the AC..."). The gap is latent, not yet triggered.

## B. Current device-state/readback path

A real command-lifecycle model already exists and is more complete than
the voice path currently uses:

- `GET /devices/queue/{room}` — a bridge tablet polls for pending commands,
  marks them `delivered`.
- `POST /devices/queue/{command_id}/ack` — the bridge reports back
  `executed` or `failed`, with a detail string, stamped `acked_at`.

**Nothing in the Realtime tool path calls or waits on this.** `state` on
`smart_devices` is written at *queue* time, not *ack* time, so it is not a
true readback — it currently means "the last command we asked for," not
"the last state a device confirmed." No bridge tablet process appears to
be running against this environment currently (consistent with every
device command in this session's forensic transcripts failing at the
"no device" stage, never reaching the ack stage at all).

## C. Current Realtime tools actually exposed

Confirmed by reading `realtime_tools.py` + `realtime_tools_operations.py`
in full — 20 tools total, all resident-facing:

`adjust_room_temperature`, `toggle_light`, `toggle_tv`, `call_for_help`,
`mark_resting`, `get_current_time`, `get_weather`, `research_topic`,
`set_timer`, `update_preferred_name`, `end_call`, `request_staff_help`,
`check_request_status`, `check_transportation_availability`,
`request_transportation`, `check_transportation_status`,
`change_transportation_request`, `cancel_transportation_request`,
`get_todays_schedule`, `get_menu`. The operator/Aria build
(`_build_aria_tools`, not read in full this pass) exposes a smaller,
separate set per its own docstring in `realtime.py`
(`request_staff_help`, `check_request_status`, `end_conversation`).

## D/E. Resident-memory write and hydration paths — verified working

Traced and **empirically tested end-to-end**, not just read: a real POST
to `/api/memory/realtime-turn` (user turn: *"My favorite ice cream is
butter pecan."*, on mock resident `res_d9129c7d1f46`/Harold, synthetic
session id) followed by the paired assistant-turn POST, which fires the
existing background extractor (`extract_and_store_memories()` in
`memory.py`). Confirmed in `db.memories` ~6 seconds later:

```
text: "My favorite ice cream is butter pecan."
category: "preferences", bin: "facts", source: "extraction"
```

Then called `_build_companion_instructions("res_d9129c7d1f46")` directly
— simulating a brand-new "session 2" — and confirmed the fact appears
verbatim under `## What you know about Harold (durable facts)` in the
freshly hydrated prompt. **The resident-facing memory pipeline works
correctly for the deterministic case Michael specified.**

Two real, narrower risks remain in this same path, both already evidenced
elsewhere this session:
- Extraction is silently skipped if the triggering user turn is
  classified `trusted:false` (`realtime_memory_ingest.py:83-84`) — a real
  risk given this session's own forensic work on trust misclassification,
  though the Room 403/408 comparison found this rare in practice.
- `extract_and_store_memories()` swallows all exceptions and logs a
  warning only (`memory.py:312-314`) — an OpenAI API error, rate limit, or
  malformed JSON response fails **silently**, with zero visibility to
  Michael or any UI. No retry, no alert, no receipt.

## D'/E'. Operator/Aria memory write and hydration paths — no extraction pipeline exists

`routes/aria_memory.py`'s `POST /aria/conversation-turn` (the endpoint
the operator Realtime session's frontend calls per turn, same pattern as
the resident path) does exactly one thing: inserts the raw turn into
`db.aria_conversations`. **It does not call any extraction function.**

`build_aria_context_block()` (what actually gets injected into a fresh
operator-Aria session's prompt) reads **only** `db.aria_memories`
(`bin: standing` / `bin: episodic`) — never `db.aria_conversations`.

Grepped the entire backend for every write to `db.aria_memories`: the
only two call sites are the manual `POST`/`PATCH /aria/memory` CRUD
endpoints in the same file. **There is no automatic path from "Michael
said something to Aria" to "a future session can recall it"** for the
operator build — a human (or an agent) has to manually create an
`AriaMemory` record for anything to be remembered.

Current state confirms this is not just a theoretical gap: `db.aria_memories`
and `db.aria_conversations` both currently hold **0 documents** — either
this path has never been used, or everything said through it has been
lost to date. **If Michael has been testing "does Aria remember what I
told her" via his own personal Aria session rather than as a mock
resident, this is the exact, complete explanation** — not a bug in an
existing pipeline, but a pipeline that was never built for this specific
build.

## F. Current facility-context source

Two flat environment variables, read once at module import
(`realtime_facility.py:12-13`): `FACILITY_LABEL`, `FACILITY_TZ`. **Neither
`realtime_facility.py` nor `realtime_companion_prompt.py` nor
`realtime.py` ever queries `db.facilities`.** The prompt's entire "Right
now" block is built from `_facility_now()`, which uses only these two env
vars plus the system clock.

## G. Current room-context source

`ctxRef.current` on the frontend (`{resident_id, kiosk_id, room}`), set at
session mint from the kiosk's own props and overridden by
`caos.context` from the backend mint response. `room` is a bare string
(e.g. `"404"`) with no link to any facility/community record — it's used
directly as a Mongo filter value (`db.smart_devices.find({"room": room})`,
`db.kiosks.find({"room": room})`) with no facility-scoping at all.

## H. Current facility city/state/timezone values (non-secret, safe to show)

- `.env`: `FACILITY_TZ=America/Chicago` (**correct** — matches Conway AR).
- `.env`: `FACILITY_LABEL=the EliteDesk node` (**a dev-machine placeholder,
  not a real facility name**).
- `.env`: no `FACILITY_LAT` / `FACILITY_LON` set at all — `weather.py`
  silently falls back to hardcoded defaults `(40.0379, -76.3055)`, which
  is a **Pennsylvania-area coordinate, not Conway, Arkansas**
  (~35.09, -92.44).
- `db.facilities` (1 record, real, Admin-created 2026-08-23): `name:
  "Brookdale Senior Living Communities"`, `address: "1160 Hogan lane"`,
  **`timezone: "conway ar 72034"`** (not a valid IANA zone — this is
  city/state/zip text that landed in the timezone field, almost certainly
  because the `Facility` model has no dedicated city/state/zip fields — it
  only has `name`/`timezone`/`address`/`phone`/`contact_email`/
  `on_call_phone`/`plan`). This record is **never read by the Realtime
  voice system** — confirmed by grep, `realtime_facility.py` has no
  `db.facilities` reference anywhere.

## I. Why current Aria can apparently fail to know Conway

Fully explained by F/H above, and **directly confirmed in this session's
own forensic transcripts**, not just inferred: in Room 404, the resident
had to tell Aria *"Conway, Arkansas"* himself before she'd acknowledge it
("I don't have that city information on hand..."); in Room 408, Aria never
volunteered a city name for weather at all, and the resident ultimately had
to state his full street address as if it were new information. This is
not intermittent — it is the necessary consequence of the voice system
never reading the one place (`db.facilities`) where Conway, Arkansas
actually is recorded, combined with `weather.py`'s coordinate default not
matching it either.

## J. Why earlier conversation facts apparently are not being recalled

Two separate, evidence-backed answers depending on which build was tested:

- **Resident-facing companion**: the pipeline works (see D/E) — a failure
  here is most likely either a turn getting misclassified `trusted:false`
  (skipping extraction silently) or a silent extraction-call failure
  (swallowed exception, no visibility). Neither was observed to actually
  occur in this pass's live test, but both are real, confirmed-possible
  failure points.
- **Operator/Aria (Michael's own assistant)**: recall cannot currently
  work at all for anything not manually entered — there is no extraction
  pipeline (see D'/E'). This is the stronger candidate if Michael has
  been testing via his own Aria conversation rather than as a resident.

---

## Smallest coherent implementation plan (not yet built)

In priority/dependency order, each independently shippable and testable:

1. **Wire `db.facilities` into the Realtime voice path.** Replace
   `realtime_facility.py`'s env-var-only `_facility_now()`/`FACILITY_LABEL`
   with a lookup against the single active `db.facilities` record (there is
   exactly one), falling back to the current env vars only if no facility
   record exists. Requires adding structured `city`/`state`/`country`/
   `lat`/`lon` fields to the `Facility` model (currently only `address`
   free text) — the smallest correct fix, not a rename of the broken
   `timezone` value. `weather.py`'s `DEFAULT_LAT`/`DEFAULT_LON` should read
   from that same facility record once it has real coordinates, not a
   second, disconnected `FACILITY_LAT`/`FACILITY_LON` env pair.
2. **Fix the existing facility record's `timezone` field** (currently
   `"conway ar 72034"`) once the model has a real place for that text to
   live, and add basic validation (a real IANA zone) so this can't recur
   silently.
3. **Give operator/Aria memory the same extraction pipeline resident
   memory already has** — call the existing, working `extract_and_store_memories`-
   equivalent pattern (a parallel function scoped to `db.aria_memories`/
   `owner_user_id`, reusing the same extractor-prompt shape) from
   `ingest_conversation_turn()`, the same way `realtime_memory_ingest.py`
   already does for residents. This is copying a proven, already-tested
   pattern, not inventing one.
4. **Close the device-truthfulness gap**: change
   `public_room_command`'s optimistic state write to only happen on ack
   (or add a distinct `pending_state` vs `state` field), and have the
   Realtime tool wrapper reflect "sent" language until a real ack exists
   — matching the GOOD/QUEUED/FAILED wording Michael specified. This can
   ship independently of whether a real bridge tablet exists yet; the
   simulation adapter Michael describes for Rooms/testing can exercise the
   exact same ack contract.
5. **Add silent-failure visibility** to `extract_and_store_memories()` —
   at minimum a diagnostic event/receipt on failure, not just a backend
   log line nobody watches live.

Each of 1-5 is independently under the 300-line file cap as scoped, touches
a small number of already-identified files, and can be tested against the
same mock residents/rooms already in use — no new simulation infrastructure
required to validate steps 1-3.

## What was and was not done this pass

- **Read-only** for devices/facilities/memory code paths.
- **One real write performed**: the deterministic memory test (steps
  described in D/E) against mock resident `res_d9129c7d1f46`, using the
  same public API the live kiosk uses — not a direct DB mutation, and
  clearly identifiable as test data (`source_session:
  "audit_test_1787626105"`) if it needs to be removed later.
- No device commands were sent to any real hardware (none exists in this
  environment).
- No SIM-7 files touched. No production code changed. No restart/deploy.
