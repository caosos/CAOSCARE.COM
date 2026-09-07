# Level 1 break-test checkpoint — 2026-09-06

Agent: Codex on EliteDesk. Inspected `main` / local `origin/main` at
`d994331`. This is a partial break-test checkpoint, not a LIVE PASS or a
claim that automatic voice recovery works end to end.

## Preserved scope

The seven pre-existing uncommitted climate files were fingerprinted before
edits and verified unchanged. No production, nginx, HA/network, device
mapping, running backend, or frontend service changes were made. No real
alert was resolved, deleted, or rewritten. No files were staged or committed.
The backend process is running without `--reload`; the source fixes below
are not loaded into that process.

## Implementation traced

`android-bridge/caos_rf_bridge.py::on_record` sends each decoded frame to
`routes/rf.py::rf_event`. Matching selects the RF device's resident/room.
`resident_activation.py` creates/coalesces an Alert as the resident event.
`kiosks.py::active_emergency_for_kiosk` supplies pending activation to the
kiosk poll. `Kiosk.jsx` mounts `RealtimeChatScreen`, which calls
`useRealtimeVoice`. `/realtime/session` claims the Mongo room lease before
minting voice credentials. WebRTC media connects from browser to provider.
Lease release does not close or consume the event; explicit lifecycle
`dismissed`/`timeout` consumes activation. Staff resolution closes the event.

## Evidence and exact failure boundaries

Read-only local health returned `{"ok":true,"db":"up"}`. Room 214 had nine
open historical events, one paired enabled RF device, and no lease in the
snapshots. Historical duplicates were preserved. These counts do not prove
nine separate current human requests.

The real pendant burst received at 22:04:50–22:04:53 UTC contained eight
frames on one existing event. Its counter moved from 49 to 57. No new
realtime diagnostics appeared in the inspected interval. Michael confirmed
availability for a physical test; his explicit confirmation of one press
and what the kiosk audibly/displayedly did is still pending. The decoded
frames inspected contain switch/battery state but no physical press counter
or release marker. Do not equate frame count with human press count.

Real Mongo, isolated ASGI-route reproduction (database
`caos_level1_break_a8b656740a`, evidence retained):

| Check | Baseline result | Failure boundary / limit |
|---|---|---|
| 12 simultaneous first activations | 12 open events | Separate find and insert, no uniqueness constraint |
| Eight identical-frame submissions | One event, press_count 8, eight raw records | Every matched frame increments count; no burst filter |
| Other room, absent zone | Foreign event returned | Poll uses same-zone OR same-room, including null zone |
| 12 simultaneous room claims | Exactly one winner | Atomic lease claim works in this test |
| Stale session release | Rejected | Session ID protects current owner's release |
| Released lease history | No lease record remains | Release deletes the lease; this collection is not an audit history |
| Old dismissal after a new press | New activation consumed | Lifecycle endpoint has no session/activation generation fence |

Source-verified frontend gaps (not yet browser fault-injection results):

- Kiosk `seenEmergencyRef` remembers only alert_id and is never reset; a
  later press on that same event does not pass the mounted kiosk's gate.
- Connection-failure listeners only log terminal reasons. They do not
  tear down media or initiate recovery; heartbeats can continue.
- Heartbeat responses/errors are ignored. A rejected former owner is not
  stopped, so database singleton ownership alone does not prove one audio owner.
- UI End call uses `ui_end_call_button`, absent from the dismissal mapping.
- `/session` does not validate alert activation state/generation before
  claiming/minting. Delayed stale launch prevention is unproven.

## Bounded fixes prepared, not activated in the running backend

1. `backend/routes/resident_activation.py`: partial unique index on a new
   `open_event_key` for active/acknowledged events, retries losing creators,
   atomically appends a press only while the selected event remains open.
   Only the winning insertion creates its receipt. Existing duplicate
   history remains intact; the latest open legacy event adopts the key on
   its next press. This prevents new duplicates through this path; it does
   not retroactively satisfy one-open-event across historical data or
   migrate unrelated legacy event producers.
2. `backend/routes/kiosks.py`: room-assigned kiosks poll their room only;
   explicitly configured zone-only and central kiosks retain their scope;
   unassigned kiosks do not match null/empty identities.

`backend/tests/test_level1_concurrency_isolation.py` passed (one test with
multiple real-Mongo scenarios): 24 concurrent presses produce one event,
24 preserved press records, and one receipt; a post-dismissal press reuses
the event; after resolution 12 concurrent presses open one new event;
legacy duplicate records remain intact; foreign room/shared-zone and
null-zone routing are rejected; explicit zone-only/central routing remains;
12 lease contenders have one winner and stale release is rejected.
Evidence database: `caos_level1_test_4588857959bc` (retained).
A separate post-fix ASGI rerun also verified one event for 12 contenders
and no foreign-room result (`caos_level1_break_cf1d82428d`). Remaining
baseline failures were still reproduced; they were not silently fixed.

Production-code line counts: resident_activation.py 209; kiosks.py 142.
`git diff --check` passed. Existing live-backend regression suites were not
rerun because they target the old running process and create synthetic
fixtures in its care database; they would not validate these source edits.

## Exact remaining live acceptance sequence

1. Confirm one physical press and the observed kiosk result for the
   captured baseline burst. Correlate press, event, lease, and session IDs.
2. After fixing/qualifying RF burst grouping, press once, hold, and press
   repeatedly at measured separations. Preserve every raw frame; establish
   which rapid presses the protocol can actually distinguish.
3. Press during active Aria: same event, correct human-press accounting,
   one audio owner, and no queued second conversation after dismissal.
4. End using the button, then spoken dismissal; wait beyond the 45-second
   lease interval. No stale launch. Another physical press must activate
   Aria on the same unresolved event in the same mounted kiosk.
5. Crash/close a kiosk tab, reopen it, and induce peer/data-channel failure:
   event stays open and a valid recovery can acquire ownership without
   requiring a duplicate incident. Repeat with another endpoint competing.
6. Deny/unplug/restore the mic, and isolate only the test browser's backend
   connectivity while media may remain connected. Verify the old endpoint
   stops audio before a replacement owns the room; do not change HA/network.
7. Deliver delayed old dismissal, heartbeat, release, and session-start
   requests after a newer activation. None may consume, release, or launch
   on behalf of the newer activation.
8. Verify configured silence/companion timers through actual speech and
   silence, staff-present behavior, and staff escalation. Real Twilio
   remains unavailable without configuration; do not invent a live-call pass.
9. Recheck Desk Lamp/Overhead Light by device_id, and room isolation, while
   preserving all event, session, lease-transition, and receipt evidence.

## Public website

A read-only web-tool open of `https://caoscare.com` failed with a
non-retryable safe-open error. Website content remains pending source
review from this tool; this does not establish that the site itself is down.

## Next safe step

Collect Michael's kiosk observation; then reproduce and fix the remaining
RF/session/frontend boundaries in isolation before activating changes on
the local test system. No LIVE PASS, production deployment, or cleanup of
historical resident events is authorized by this checkpoint.
