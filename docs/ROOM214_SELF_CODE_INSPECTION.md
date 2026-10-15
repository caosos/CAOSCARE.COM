# Room 214 Aria — read-only self-code inspection

**Status 2026-10-15:** IMPLEMENTED + TESTED (PR #169 → integration `1f60a58`), LOADED on dev `:8092` and the Room 214 page (`main.b13c2b0d.js`), PHYSICALLY VERIFIED and OWNER ACCEPTED live (session `rt_lnrab36x_1792103482825`, 17:31 CDT; receipts on PR #169). Not PRODUCTION DEPLOYED (production `06e7e2b` predates it).

**Owner feature (Michael, 2026-10-15).** The Aria instance serving **Room 214
only** may read the CAOSCARE source relevant to herself, so she can answer
"look at your own code and tell me how your memory works" from the actual
implementation instead of guessing. Knowledge access only: no write, edit,
delete, git, shell, restart, process, network or database mutation path
exists in this capability.

This is **not** a platform-wide Aria capability. It is unavailable to other
resident rooms, simulated/demo rooms, the owner `/aria` build, Admin Aria,
desktop Aria, telephone Aria, other agents and plain API callers.

## Where it lives

| Piece | File |
|---|---|
| Identity gate (who may call) | `backend/routes/self_code_identity.py` |
| Allow-list, path rules, bounded read/search, revision truth | `backend/routes/self_code_source.py` |
| Endpoints `POST /api/aria/self-code/{inspect,search,read}` + receipts | `backend/routes/self_code_inspection.py` |
| Tool schemas + the one prompt block, declared only at a Room 214 mint | `backend/routes/self_code_tools.py` |
| Mint wiring (tools/prompt appended only when `is_room214_mint`) | `backend/routes/realtime_resident_session.py::_mint` |
| Browser relay for the three tools | `frontend/src/lib/realtimeSelfCodeTools.js` (dispatched from `realtimeMessageHandler.js`) |
| Page build embeds its revision (`REACT_APP_BUILD_SHA`) | `room-node/aria_wake/ctl.sh` |
| Tests | `backend/tests/test_room214_self_code_gate.py`, `backend/tests/test_room214_self_code_session.py`, `frontend/src/lib/__tests__/selfCodeDispatch.test.js` |

## Identity gate (fail closed)

Nothing caller-supplied is trusted: not `room`, `resident_id`, `kiosk_id`, a
URL parameter or a tool argument. On **every** call the backend proves:

1. **Canonical record** — exactly one non-demo kiosk with `room == "214"` in
   `db.kiosks`, and the resident it speaks for (`resident_for_kiosk`, pinned
   resident first) exists and is not `synthetic`.
2. **Live lease** — `db.resident_aria_leases` holds a live, fresh
   (`STALE_SECONDS`) lease for the request's `session_id`. Leases are written
   only by `claim_or_reuse_room_lease()` at session mint, never by a client.
3. **Lease == canonical** — lease room is `214`, lease kiosk is the canonical
   kiosk, lease resident is the canonical resident, and the request's
   `resident_id` equals the lease's.
4. **Origin** — the request arrived from the Room 214 node's own page proxy
   (`room-node/aria_wake/serve_built.js`, loopback → backend on the same
   host). `CAOSCARE_SELF_INSPECT_ORIGINS` (default `127.0.0.1,::1`).

Any failure → HTTP 403 with a reason code (`no_live_session`,
`not_room_214`, `kiosk_mismatch`, `resident_mismatch`,
`resident_claim_mismatch`, `origin_not_room_node`,
`no_canonical_room_record`, `disabled`) and a refusal receipt.

Owner `/aria`, Admin Aria, telephone Aria and API callers hold no resident
room lease, so they fail at step 2 regardless of any token they present. A
Room 215 session fails at step 3 even when it sends `room=214`. The demo
kiosk is excluded at step 1 (`public_demo`), simulated residents by
`synthetic`.

Kill switch: `CAOSCARE_SELF_INSPECT=off` on the backend disables the
capability everywhere (tools are not declared, calls are refused).

**Residual, stated plainly:** the resident session mint (`POST
/api/realtime/session`) is a public kiosk endpoint, so the lease is the same
server-side room identity the whole resident path already relies on. The
origin check adds the requirement that the call come through the Room 214
node itself. If the backend is ever moved off the room node (central server
architecture), the origin proof must be replaced by an equivalent one before
this capability is enabled there.

## What she can read

Fixed allow-list of repo-relative globs (`APPROVED_GLOBS` in
`self_code_source.py`): `backend/routes/realtime*.py`,
`backend/routes/aria_*.py`, the session/lease/identity modules, memory and
research routes, device adapters, `backend/routes/self_code_*.py` (this
capability), `room-node/aria_wake/*.py` + README + `serve_built.js`, the
Room page Realtime libraries (`frontend/src/lib/realtime*.js`,
`useRealtimeVoice.js`, wake/duck/end/claim helpers, `pages/Kiosk.jsx`), and
the Aria/room architecture docs (`CAOSCARE_PRODUCT_BASELINE`,
`ARIA_LANE_ONBOARDING`, `ARIA_CONVERSATION_SUBSTRATE`,
`ARIA_SUBSTRATE_IMPLEMENTATION_PLAN`, `ROOM_AUDIO_ARCHITECTURE`,
`ARIA_WAKE_WORD_ARCHITECTURE`, this file, `AGENTS.md`).

Hard denies, checked before any read: anything off the allow-list
(`.env*`, keys, credentials, Mongo strings, DB files, `/proc`, `/etc`,
other homes, `node_modules`), absolute paths, `..`, backslashes, NUL,
symlinks anywhere in the path (resolved path must equal the checkout path),
names that look like a secret store, binary files, files over 512 KB.
Reads: at most 120 lines / 12 000 chars per call. Search: literal,
case-insensitive, 25 matches, 5 per file. Lines that look like credentials
are redacted defensively.

## Runtime truth

Every result carries `inspected_sha` (the checkout's `git rev-parse HEAD`,
read-only, fixed argv), `loaded_backend_sha` (`CAOSCARE_RUNTIME_SHA`, set by
`scripts/restart_dev_backend.sh` / the EliteDesk deploy workflow),
`backend_match` (True / False / `null` = unknown), the page's own build
revision (`loaded_frontend_sha_reported_by_page`, embedded at build by
`ctl.sh`) and `frontend_match`, plus `local_modifications` on reads. The
prompt block tells Aria to say "I checked the code I'm currently running"
**only** on a match, and otherwise "I found that in the repository, but it
is not the version currently running in Room 214."

## Receipts

One `db.receipts` document per attempt (`action_type: self_code_inspection`,
`source: aria_voice`), allowed or refused: session id, tool, requested
file/query/range, inspected SHA, loaded SHA, match flags, origin, trigger
source, allowed/refused with reason, actor = unverified room claim with
authority `room214_lease_verified` when proven. Receipts never contain
source text.

## Live Room 214 acceptance script (Michael)

1. "Hey Aria." — "Aria, look at your own code and tell me how you remember
   our conversations." PASS: she calls `inspect_own_code` then
   `search_own_code`/`read_own_code` (receipts show it), names the files
   (expected: `backend/routes/aria_life_memory.py`,
   `aria_memory.py`, `realtime_companion_memory.py`,
   `realtime_memory_ingest.py`), explains summaries + life story + facts, and
   states whether the inspected revision matches the running one.
2. "Can you change your own code?" PASS: No — read-only, no tool or
   authority to modify.
3. Evidence: `db.receipts.find({action_type:"self_code_inspection"})` for
   the session, and `docs/PROJECT_STATE.md` entry with the loaded SHA.
