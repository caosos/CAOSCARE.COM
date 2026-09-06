# Level 1 Break-Test — Pendant → ResidentEvent → Aria

Branch: `claude/level1-breaktest` (base `d994331`, == `origin/main` at session start).
Lane: Level 1 pendant / ResidentEvent / Aria / recovery. Task notes kept here to
avoid cross-branch conflict on `docs/PROJECT_STATE.md` while the other worktree
edits baseline/deviation/dashboard files.

## Method

Forensic trace of the real Room 214 path against the committed code and the
live `caoscare` MongoDB (read-only), before any code change:

```
RF frame (rtl_433 JSON, android-bridge/caos_rf_bridge.py)
  -> POST /api/rf/event                    (backend/routes/rf.py::rf_event)
  -> record_resident_activation()          (backend/routes/resident_activation.py)
  -> Alert doc (press_count, presses[], activation_consumed_at)
  -> GET /api/kiosks/{id}/active-emergency (backend/routes/kiosks.py)
  -> Kiosk.jsx poll -> handleIncomingEmergency -> RealtimeChatScreen
  -> useRealtimeVoice.start(): claim room lease -> mint OpenAI session -> mic
  -> session end (dismiss / timeout / drop / crash)
  -> /realtime/room/{room}/release  (lease slot freed; activation NOT consumed)
  -> aria-event dismissed|timeout   (the ONLY session-end that consumes activation)
  -> next pendant press
```

## Evidence pulled (live `caoscare` DB, 2026-09-06)

- `rf_devices`: Room 214 pendant `rfd_6e8f06632b41` -> `res_81b72be1e8b5`
  (Helen Torres), `press_count` 108 (device telemetry, cumulative).
- `alerts` for Helen: newest open event `alert_ffa154faf699`,
  `status:"active"`, `activation_consumed_at:null`, `press_count:57`,
  `presses[]` length 14.
- `presses[]` on `alert_ffa154faf699` clusters into exactly **3 bursts**:
  - `20:54:58.168 / .692 / 20:54:59.216`  (3 frames, ~1.05 s span)
  - `21:59:22.297 / .821 / .842`           (3 frames, ~0.5 s span)
  - `22:04:50.812 … 22:04:53.956`          (8 frames, ~3.1 s span)
- `rf_events` for the same pendant (108 matched frames -> 14 press bursts):
  frame cadence inside one physical press is **~0.52 s**, one physical press
  produces **3–8 frames spanning up to ~3.2 s**. Gaps between distinct
  physical presses in the capture: minutes.
- `resident_aria_leases`: empty (no stuck lease). `alerts` `status:"active"`
  count: 333 (known stale test/dev debris, see PROJECT_STATE 2026-09-06).

## First proven failure boundary

### DEFECT 1 — RF echo/duplicate frames inflate `press_count` and `presses[]`
Invariants violated: **2** (one physical press = one increment) and **3**
(RF duplicate/echo must not inflate human `press_count`).

- `android-bridge/caos_rf_bridge.py` `on_record()` POSTs **every** rtl_433
  record to `/rf/event` with its own monotonic `sequence`. No frame-level
  de-duplication in the bridge.
- `rf.py::rf_event()` only rejects **non-monotonic** sequences (replay of an
  *old* seq). Each distinct echo frame of one press is a new, higher seq and
  passes.
- `resident_activation.py::record_resident_activation()` does an
  unconditional `$inc: press_count 1` + `$push: presses` on every call.
- Net: one physical press of the real Interlogix pendant = ~3–8 increments.
  `alert_ffa154faf699` = **3 physical presses recorded as 14 `presses[]`
  entries / `press_count` 57**.
- Both `rf.py` (lines ~46–52) and `resident_activation.py` (module
  docstring) **claim** "frame-level coalescing ... lives in
  routes/resident_activation.py now." It does not — doc/impl contradiction.
- Downstream corruption: `resident_patterns.py` marks any resident with
  `press_count >= 3` a `burst_user`; every RF-pendant event clears that bar
  from echo alone. (Analytics is the other worktree's lane — noted, not
  touched.)

Fix (this branch): a per-device sliding echo window in
`record_resident_activation()`. An `rf_pendant` frame that lands within
`RF_PRESS_DEBOUNCE_SECONDS` (default **3 s**, env-overridable) of the
**previous frame** from the same `device_id` on the same open event
(tracked as `Alert.last_rf_frame_at` / `last_rf_frame_device`, advanced on
every frame) is treated as an echo frame:
- still written to `db.rf_events` unconditionally by `rf.py` (evidence never
  dropped — invariant preserved),
- does **not** `$inc press_count`, does **not** `$push presses`, does **not**
  reset `activation_consumed_at` (only advances the last-frame marker).

Measuring from the previous frame (not the first) collapses the whole repeat
train no matter how long it runs (real trains span up to ~3.2 s). A frame
that arrives more than the window after the last frame is a genuine separate
press and increments normally (invariant 4). A help pendant cannot
physically distinguish "button held / re-fired" from "pressed twice fast",
so a sub-window re-press collapses too — the raw frames are all still in
`rf_events`. Kiosk-button presses are deliberate discrete taps with no echo
train and are **not** debounced (`source != "rf_pendant"` -> never echo).

### DEFECT 2 — a mounted kiosk never re-wakes Aria on a later press of the SAME open event
Invariant violated: **6** (a later pendant press must reactivate Aria on the
same open event).

- `Kiosk.jsx` remembers `seenEmergencyRef.current = a.alert_id` the first
  time it auto-wakes for an alert, and **never resets or versions it**.
- Before the 2026-09-06 Level 1 change, a press after `activation_consumed_at`
  was set minted a **new** `alert_id`, so `a.alert_id !== seen` stayed true
  and the kiosk re-woke. The Level 1 change made a later press **reactivate
  the same `alert_id`** (resident-scoped, status-based coalescing;
  `activation_consumed_at` reset to `null`). `active-emergency` now returns
  the **same** `alert_id` -> `a.alert_id !== seenEmergencyRef.current` is
  false -> `handleIncomingEmergency` never fires.
- Result: after one dismissed/ended session, an **already-open kiosk tab**
  in Room 214 is deaf to every subsequent pendant press until staff
  `resolve()` the event (which mints a new id). A kiosk that reloads is fine
  (ref resets on reload) — which is why this hid behind the reload-heavy
  hardware testing so far.
- Backend acceptance test `test_resident_events.py` step 7 asserts the
  **backend** returns the same alert again; it never exercises `Kiosk.jsx`'s
  `seenEmergencyRef`, so the gap was untested.

Fix (this branch): track `{ id, pressCount }` instead of a bare id, extracted
to a pure `frontend/src/lib/kioskEmergencyWake.js::evaluateEmergencyWake()`.
Re-wake when `alert_id` is new **or** `press_count` exceeds the last engaged
watermark. A genuine new press always bumps `press_count`, so reactivation is
detected; a bare re-poll of the same state, or the on-screen X-button ending
a call **without** consuming the activation, does not — so there is no
relaunch loop. While a session is running, the watermark is kept current so
presses made *during* the call don't trigger a spurious relaunch when it ends.

## Invariants checked and NOT changed (no proven defect)

- **1 (one resident = one open event)** — `record_resident_activation` is
  resident-scoped and picks the newest `active|acknowledged` alert. A
  theoretical TOCTOU (two first-frames both seeing "no open alert" and both
  `insert_one`) exists — `find_one` then `insert_one` is not atomic and
  20 ms doubled frames appear in the capture — but **no sub-second alert
  pair is present in the live data**, so it is unproven. Not fixed
  (unique-partial-index / upsert is more invasive than the directive's
  "fix only proven defects").
- **5 (ending/dismissing/crashing Aria must not close the event)** — held.
  `release()` no longer consumes; only `aria-event dismissed|timeout` and
  `staff-present` consume; `resolve()`/`close()` are the only close paths.
  Verified in code + existing tests.
- **7 (one room, one Aria audio owner)** — `resident_aria_leases` unique
  index on `room` + atomic `find_one_and_update` claim. One narrow race:
  a `stop()` that lands during the final `await pc.setRemoteDescription`
  in `useRealtimeVoice.start()` can commit an orphan peer connection after
  the lease was released. Narrow, no evidence, self-heals via 45 s lease
  staleness. Documented, not fixed.
- **8 (browser/kiosk failure recovers)** — kiosk reload re-reads the open,
  unconsumed event and re-engages. Improved by Defect 2 fix for the
  no-reload case.
- **9 (mic failure must not destroy the event)** — held. `start()`'s catch
  block releases the lease but never calls `stop()` and never posts an
  aria-event, so `activation_consumed_at` stays `null`.
- **10 (no stale/delayed activation without a new trigger)** — with the
  5-minute `created_at` cutoff removed from `active-emergency`, an open
  unconsumed event has **no upper age bound**: a kiosk tab opened hours
  later will auto-wake for it. Pre-existing behavior (old code also woke),
  and arguably correct for a genuinely unresolved event, but it is a real
  product tension with invariant 10. **Flagged for Michael** — not changed
  unilaterally.
- **11 (room lease ownership auditable)** — `GET /realtime/room/{room}/status`
  exists; staleness self-heal + explicit `release`/`staff-present` are all
  logged to `event_log`. Adequate.
- **12 (facility assistance semantics preserved)** — kiosk `create_alert`
  still fans out family notifications and still produces an alert; RF
  severities still map to `AlertSeverity`. No regression from the two fixes.

## Physical tests still requiring Michael + real Room 214 hardware

Not physically proven (no agent can prove these — Michael must press the real
pendant and observe):

1. **Defect 1 fix, real pendant**: one physical press of `rfd_6e8f06632b41`
   -> exactly **+1** `press_count` on the open event (not +3..+8). Press
   again after ~5 s -> **+1** more. Check `alerts.find({alert_id})`.
2. **Defect 2 fix, mounted kiosk**: with the Room 214 kiosk tab already open
   and idle, press the pendant (Aria wakes), end the conversation, wait,
   press again -> Aria must re-wake on the **same** `alert_id`, no reload.
3. **Invariant 5, live voice**: start a session, kill the browser tab
   mid-conversation -> event stays `active`, `activation_consumed_at` null;
   a fresh kiosk load re-engages the same event.
4. **Invariant 9, live**: deny the mic at the OS prompt -> event stays open,
   room lease frees within 45 s, next press still works.
5. Companion 300 s timeout / 8 s invite-silence / `request_live_staff`
   routing question through real OpenAI Realtime audio (carried over from
   PROJECT_STATE 2026-09-06 "not yet tested").

## Change log (this branch)

- `backend/routes/resident_activation.py` — RF echo-frame window in
  `record_resident_activation()`.
- `frontend/src/lib/kioskEmergencyWake.js` — new, pure wake decision.
- `frontend/src/pages/Kiosk.jsx` — poll uses `evaluateEmergencyWake()`;
  `seenEmergencyRef` now `{ id, pressCount }`.
- `backend/tests/test_resident_events.py` — reactivation sequence updated for
  the echo window; new `_run_rf_echo_debounce` scenario.
- `frontend/src/lib/__tests__/kioskEmergencyWake.test.js` — new.
