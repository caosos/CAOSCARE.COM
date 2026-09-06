# Resident Baseline / Deviation — Forensic Audit Report

**Purpose of this document.** A complete, review-ready record of everything discovered
during the resident-baseline / deviation investigation on branch
`claude/resident-baselines`, written so another architect or AI can review it and
so Michael can make two pending decisions **before any code is written**.

**Status of this work:** inventory only. **No code has been changed.** No decision
has been made. Nothing has been merged. This report is the only artifact produced.

- **Date:** 2026-09-06
- **Agent / tool:** Claude Code (Sonnet 5), CAOSCare Claude worktree
- **Branch / ref:** `claude/resident-baselines`
- **HEAD at investigation:** `d994331e44f60451be7f63748dd850f59239712a` (identical to `origin/main`)
- **Worktree:** `/home/caoscare-1/CAOSCARE-CLAUDE` (dedicated Claude worktree; clean)
- **Running backend on this host:** served from the **main checkout**
  `/home/caoscare-1/CAOSCARE.COM/backend` at the same commit; MongoDB up
  (`GET /api/health` → `{"ok":true,"db":"up"}`). The worktree's copy of the code is
  *not* the live process — this matters only for how integration tests get run later.

---

## 1. EXECUTIVE SUMMARY

### What was inspected

- `backend/models.py` (all 1555 lines) — every persisted model.
- Route modules most relevant to resident events, presses, sessions, telemetry,
  analytics, receipts: `alerts.py`, `alert_lifecycle_events.py`, `resident_activation.py`,
  `rf.py`, `rf_bridge_health.py`, `pendants.py`, `kiosks.py`, `realtime.py`,
  `realtime_room_lease.py`, `realtime_audio_config.py`, `realtime_diagnostics.py`,
  `realtime_memory_ingest.py`, `resident_conversations.py`, `resident_analytics.py`,
  `resident_patterns.py`, `insights.py`, `events.py`, `receipts.py`,
  `resident_assistance_config.py`, `resident_activation.py`.
- The RF bridge daemon `android-bridge/caos_rf_bridge.py` (press/frame emission path).
- Frontend voice pipeline: `frontend/src/lib/useRealtimeVoice.js`,
  `realtimeMessageHandler.js`; the analytics UI `frontend/src/pages/Insights.jsx`;
  frontend page/component inventory.
- `backend/server.py` (router registration), `backend/deps.py` (DB + auth),
  `backend/seed.py` (pilot residents).
- `backend/tests/test_resident_events.py` (Level 1 regression suite) and the test
  directory shape.
- `docs/PROJECT_STATE.md` (most recent entries) for the Level 1 history and the
  2026-09-06 "decouple ResidentEvent lifetime from Realtime session lifetime" fix.
- Full DB collection inventory (grep of every `db.<name>` reference in the backend).

### Overall current state

CAOSCare **already has most of the raw material** for personal baselines, spread
across several collections, plus **two partial precursor systems** that implement
pieces of the target idea:

- `resident_patterns.py` + `db.resident_button_patterns` — per-resident, per
  **hour-of-day** bucket statistics for **press count** and **open minutes**, with a
  real maturity gate (`pattern_min_events`, default 5 → "Not enough history" rather
  than a fabricated footnote). This is the directive's core idea already implemented
  for one metric in one context dimension.
- `insights.py` + `db.insights` + `Insights.jsx` — per-resident **last-7d-vs-prior-7d**
  deltas for a handful of alert-count metrics, with `{info,watch,concern}` severity, a
  sample-size confidence score, and explicit non-diagnostic UI language.

What is **missing** is the generalisation the directive asks for: a clean
**raw → derived-baseline → deviation** three-layer separation; contextual buckets
beyond hour-of-day; baseline **maturity states**; **frequency / duration / speech-level**
metrics as first-class; **multi-deviation composition**; a **"What Changed?"** triaged
view; and any **speech-level audio telemetry** at all.

### Biggest findings

1. **`press_count` currently counts RF radio frames, not human presses.** There is no
   frame-echo collapse anywhere in the pipeline (bridge, backend, or model), despite
   code comments in `rf.py` and `resident_activation.py` asserting that it "lives in
   `resident_activation.py` now." One physical pendant press produces ~8 RF frames
   (live-evidenced 2026-08-29, recorded in `rf.py`), each of which increments
   `Alert.press_count` and appends a `PressRecord` to `Alert.presses[]`. This is the
   single most consequential data-integrity issue for any press-frequency or
   press-count baseline. **(See §5.A.)**
2. **No speech-level telemetry exists.** No RMS, dBFS, noise floor, SNR, VAD
   confidence, or clipping is captured anywhere. On the OpenAI Realtime WebRTC path
   the raw mic audio never reaches our backend, and the browser hook runs no
   `AnalyserNode`. The **timing** half of the directive's metric #1 (response latency,
   speech/silence/conversation duration) *is* derivable from existing
   `db.realtime_diagnostics` timestamps with no new capture. **(See §5.B / §9.B.)**
3. **`Alert` is already a rich resident-event record.** `presses[]`, `event_log[]`,
   `response_seconds`, `duration_seconds`, `category`, `ai_summary`,
   `resident_stated_reason`, `aria_state`, `silence_after_invite`, `requested_staff`,
   `source_metadata`, and per-event receipts already exist. Frequency and duration
   baselines need essentially **zero new capture** — only aggregation.
4. **`db.rf_events` is a complete raw-radio evidence log.** Every frame (matched or
   not) is stored with full fingerprint, per-frame `rssi`, decoder evidence
   (`battery_ok`), match score, and both `captured_at` and `received_at`. This is a
   durable recomputation source.
5. **`db.events` (`CaosEvent`) is a designed generic telemetry substrate that is
   barely populated** — only `admin_aria.*` and `device.command` events are written;
   nothing for resident sessions, presses, or alert lifecycle.

### Biggest architectural opportunities

- Generalise `resident_patterns.py`'s bucket+maturity approach from "one metric, one
  context dimension" to "any metric, a fallback ladder of context buckets."
- Introduce an **append-only raw-observation layer** so baselines can be recomputed
  when the algorithm improves — neither existing precursor keeps raw data
  (`resident_button_patterns` overwrites; `insights` wipes on recompute).
- Reuse `insights.py`'s severity/confidence heuristic and `Insights.jsx`'s
  non-diagnostic UI rather than replacing them.
- Reuse `ResidentAssistanceConfig`'s per-facility, never-404-falls-back-to-defaults
  config pattern for baseline knobs.
- Derive the timing metrics from `db.realtime_diagnostics` now; add the audio-level
  metrics as nullable fields to be back-filled once client instrumentation exists.

### Biggest risks

- **Semantic change to `press_count`.** Fixing frame collapse changes what a
  long-standing field means and will break assertions in `test_resident_events.py`
  that encode "one API call = one press." The assistance-event invariant (one press
  opens/attaches to exactly one event, never suppressed or delayed) is *not* affected
  either way, but this still touches a Level 1 code path.
- **AGC undermines raw speech-level comparison.** `getUserMedia` is called with
  `autoGainControl: true` (and `echoCancellation`, `noiseSuppression`). Any RMS
  captured downstream of AGC is already level-normalised, so naive
  "resident is quieter" comparisons would be measuring AGC behaviour, not the
  resident. This must be handled deliberately (disable AGC for a measurement tap, or
  measure a pre-processing tap, or treat the metric as relative-only).
- **Over-segmentation on sparse data.** The pilot is ~3–5 residents. Hour-of-day
  buckets will almost never reach maturity; the fallback ladder and maturity states
  must be conservative or the dashboard will show noise as signal.
- **Parallel-workstream collisions.** `models.py`, `server.py`,
  `resident_activation.py`, `alerts.py`, and `useRealtimeVoice.js` are all
  high-traffic files that other CAOSCare work touches frequently. New work should
  favour new modules and one-line hooks. **(See §10.)**

---

## 2. EXISTING DATA / TELEMETRY INVENTORY

Legend for "reality":
**REAL** = fully implemented and in live use ·
**PARTIAL** = implemented but narrow / incomplete for baseline purposes ·
**DERIVABLE** = not stored as such, but reconstructable from stored data ·
**DISCONNECTED** = model/route exists but nothing populates or reads it for this purpose ·
**MISSING** = does not exist.

### 2.1 Residents — **REAL**

- **Model:** `Resident` — `backend/models.py:164`. Also `ClinicalThresholds` — `models.py:150`.
- **Collection:** `db.residents`.
- **Routes:** `backend/routes/residents.py` (CRUD/identity), `backend/routes/resident_analytics.py`
  (`/residents/{id}/movement`, `/stats`, `/briefing`), `backend/routes/resident_conversations.py`.
- **Fields useful here:** `resident_id`, `name`, `room`, `pendant_id`,
  `participation_level` (`room_only | pendant_enhanced | wearable_enhanced |
  family_connected | full`), `preferences`, `memory`, `preferred_name`,
  `clinical_thresholds` (per-resident vitals bands; `None` fields fall back to a
  generic default — **the existing precedent for per-resident, non-diagnostic tuning**).
- **Notes:** No `facility_id` on residents yet (multi-tenant is `Optional` everywhere;
  the pilot is single-tenant). Seed residents (`seed.py:169`): Margaret O'Brien/101,
  Frank Delgado/108, Evelyn Park/112, Raymond Chen/205, Dorothy Walsh/214,
  Harold Bennett/231. **The live DB has been customised** — `PROJECT_STATE.md`
  references "Helen Torres's Room 214" and a "43-press event," so live data differs
  from seed. The directive's "Helen — Room 214" example maps to live data, not seed.

### 2.2 Alert / ResidentEvent — **REAL** (rich)

- **Model:** `Alert` — `backend/models.py:283`. Embedded `PressRecord` — `models.py:272`.
  `AriaState` — `models.py:279`. `LiveLineState` — `models.py:280`.
- **Collection:** `db.alerts`.
- **Routes:** `backend/routes/alerts.py` (create/list/feed/acknowledge/resolve/close/stats/get),
  `backend/routes/alert_lifecycle_events.py` (`/{id}/aria-event`, `/{id}/live-line/ring|answer|no-answer`).
- **Creation / coalescing:** `backend/routes/resident_activation.py::record_resident_activation()`
  is the single entry point (called from `rf.py::rf_event`, `alerts.py::create_alert`).
  Resident-scoped: an open, unresolved event (`status ∈ {active, acknowledged}`,
  `resident_id` match — or `room` match when `resident_id` is `None`) absorbs the new
  press; otherwise a fresh `Alert` is opened.
- **Fields already captured per event:**
  - `presses: List[PressRecord]` — each `{at, device_id, source, rssi}`
  - `press_count` (see §5.A — currently frame-inflated)
  - `aria_state` (`dormant | active | muted_staff | dismissed`),
    `live_line_state` (`none | offered | ringing | connected | declined | no_answer`)
  - `event_log: List[dict]` — `{at, field, utterance|to}` transition history
  - `pattern_footnote` (set once at open, from `resident_patterns.footnote_for_resident_now()`)
  - `requested_staff`, `silence_after_invite`
  - `category` (`AlertCategory`: bathroom/fall/pain/medication/confusion/loneliness/comfort/mobility/other),
    `ai_summary`, `resident_stated_reason`
  - `response_seconds` — created → acknowledged (set in `alerts.py::acknowledge`)
  - `duration_seconds` — (acknowledged_at or created_at) → resolved
    (set in `alerts.py::resolve` / `close_alert`)
  - `conversation_turns` — **declared in the model, never written** (DISCONNECTED)
  - `created_at`, `acknowledged_at`, `resolved_at`, `outcome`, `close_notes`
  - `escalation_level` (lazy escalation in `alerts.py::alerts_feed`, thresholds 60/180/420s)
  - `activation_consumed_at` — kiosk-facing "has this incident produced its one Aria
    activation"; **separate from `status`**; reset to `None` on every coalesced press
  - `source_metadata` — `{rf_device_id, match_score, rssi, rf_severity}` for RF presses
  - `receipt_id` — points at the `db.receipts` row for this event
- **Close hook:** `alerts.py::_close_out(doc)` runs after `resolve`/`close_alert`:
  calls `resident_patterns.update_pattern_stats()` and `receipts.update_receipt_status(...
  "completed")`. **This is the natural place to also record a raw observation.**

### 2.3 Presses / `presses[]` — **PARTIAL** (semantics wrong; see §5.A)

- **Per-event:** `Alert.presses[]` (above). Every call into `record_resident_activation()`
  that coalesces does `$inc press_count` **+** `$push presses` **unconditionally**
  (`resident_activation.py:70-77`). No time-window or same-fingerprint debounce.
- **Per-device lifetime:** `RFDevice.press_count` (`models.py:1189`), `$inc`'d once per
  matched frame in `rf.py::rf_event` (`rf.py:452`). Also frame-inflated.
- **Legacy path:** `backend/routes/pendants.py` — a separate, older, frequency-keyed
  pendant scaffold. `pendants.py:143` counts `db.alerts` rows with the same
  `pendant_id`/`triggered_by:"pendant"` in a 60-second window to derive `press_count`
  and escalate to `emergency` at `>= 2`. **Not** wired through `record_resident_activation()`;
  flagged legacy/untouched in `resident_activation.py`'s docstring. `db.pendants`,
  `db.pendant_unknown`.

### 2.4 Raw RF events — **REAL** (complete raw log)

- **Model:** `RFEventIn` (inbound) — `models.py:1236`; `RFFingerprint` — `models.py:1166`;
  `RFDevice` — `models.py:1177`; `RFCapture` — `models.py:1198`.
- **Collection:** `db.rf_events` (raw log), `db.rf_devices` (paired), `db.rf_captures` (pairing windows).
- **Route:** `backend/routes/rf.py::rf_event` (`POST /api/rf/event`, HMAC-signed, monotonic-sequence replay guard).
- **Every frame is stored** (matched or unmatched) — `rf.py:424-433, 490`:
  `{kiosk_id, fingerprint{frequency_hz, modulation, bit_pattern_hex, bit_length, rssi,
  decoded{battery_ok,...}}, sequence, matched_device_id, match_score, captured_at,
  received_at, alert_id}`.
- **Signal data:** per-frame `rssi` is real since the bridge started running
  `rtl_433 -M level` (2026-09-06); `decoded.battery_ok` propagated to
  `RFDevice.low_battery`. `snr`/`noise` fields are present in some `rtl_433` records
  but not explicitly persisted as top-level fields (they'd be inside `fingerprint`
  only if the schema carried them — it does not; `RFFingerprint` has `rssi` and a
  free-form `decoded` dict).
- **Bridge:** `android-bridge/caos_rf_bridge.py::on_record` POSTs **one
  `/api/rf/event` per `rtl_433` JSON line** — no dedup, no throttle, no burst
  collapse (`caos_rf_bridge.py:472-495`).

### 2.5 Realtime sessions — **PARTIAL** (resident sessions not summarised)

- **Lease model:** `ResidentAriaLease` — `models.py:1546`. **Collection:** `db.resident_aria_leases`
  (unique index on `room`). **Route/logic:** `backend/routes/realtime_room_lease.py`
  (`claim_or_reuse_room_lease()`, `/realtime/room/{room}/activate|heartbeat|release|staff-present`).
  `STALE_SECONDS = 45`; client heartbeats every 20s (`useRealtimeVoice.js:390`).
  Fields: `room`, `resident_id`, `kiosk_id`, `session_id` (the frontend's own
  `rt_<rand>_<ts>`), `status` (`activating | active | ending`), `trigger_source`
  (`pendant | wake_word | handset | screen_talk | manual_kiosk`), `created_at`, `last_seen_at`.
- **Session mint:** `backend/routes/realtime.py::create_session` (`POST /api/realtime/session`) —
  builds companion instructions, injects `context` (resident_id, kiosk_id, room,
  alert_id, facility label/tz, and Level-1 timeouts). `create_aria_session` is the
  separate **operator** (Michael) path.
- **Operator session summary:** `AriaVoiceSession` — `models.py:1507`; `db.aria_voice_sessions`.
  **Scoped to `owner_user_id` — operator only, not residents.** There is no
  resident-session equivalent summary record.
- **Derivable per resident session:** start/end, duration, turn count — from
  `db.conversations` grouped by `session_id` (done at read time in
  `resident_conversations.py`). Trigger source — from `db.resident_aria_leases`.

### 2.6 Transcripts — **REAL**

- **Collection:** `db.conversations`. **Writer:** `backend/routes/realtime_memory_ingest.py::realtime_turn_ingest`
  (`POST /api/memory/realtime-turn`) — one doc **per turn, saved the instant it's
  known**, no pairing at the persistence layer. Fields: `{resident_id, session_id,
  role, content, source:"realtime", trusted (user turns only), room, kiosk_id,
  item_id, created_at}`.
- `trusted:false` marks a user turn that began while Aria's own audio was still
  playing (likely echo / VAD false-positive) — still stored for history, skipped for
  memory extraction.
- Also `db.chat_messages` (`ChatMessage` — `models.py:397`) — older text-chat path.
- Read/grouping: `resident_conversations.py` (`/residents/{id}/conversation-sessions`
  and `/{session_id}`), joining `db.receipts`, `db.staff_tasks`,
  `db.realtime_diagnostics`, and best-effort `db.device_commands` by room+time-window.

### 2.7 VAD / audio information — **PARTIAL** (timing only; no levels)

- **Config (static, not measurement):** `backend/routes/realtime_audio_config.py` —
  `DEFAULT_VAD = {type:"server_vad", threshold:0.5, prefix_padding_ms:300,
  silence_duration_ms:1000, create_response:true, interrupt_response:true}`;
  `DEFAULT_NOISE_REDUCTION = {type:"far_field"}`.
- **Event timing (REAL):** `db.realtime_diagnostics` — `backend/routes/realtime_diagnostics.py`
  (`POST /api/realtime-diagnostics/event`, no auth, fire-and-forget from
  `frontend/src/lib/realtimeMessageHandler.js`). Fields: `{session_id, event_type,
  assistant_speaking, text, response_id, meta, created_at}`.
  - Logged event types include: `speech_started`, `speech_stopped` (each with
    `assistantSpeaking`), `mic_track_settings` (see §2.8), plus `output_audio_buffer.*`
    playback lifecycle events, transcripts, `response.done`, etc.
- **DERIVABLE from the above, with no new capture:**
  - resident speech-segment duration = `speech_stopped.created_at − speech_started.created_at`
    (client also computes `lastSpeechSegmentMs` but does **not** send the number).
  - silence duration = gap between consecutive `speech_started` events.
  - Aria response latency = next `speech_started` after Aria's
    `output_audio_buffer.stopped`.
  - conversation duration = last turn `created_at` − first turn `created_at` (per `session_id`).
  - conversation turn count = count of `db.conversations` rows for the `session_id`.
  - "did the resident respond to the opening invite" = already captured explicitly as
    `Alert.silence_after_invite` (set by the 8s invite-silence timer in `useRealtimeVoice.js`).
- **MISSING entirely:** speech RMS / dBFS, noise floor (dBFS), signal-to-noise ratio,
  clipping percentage, per-turn VAD confidence value (only the boolean fact that VAD
  fired is observable, not its confidence score).

### 2.8 Microphone state — **PARTIAL** (identity + processing flags; no level/gain)

- **Per-session diagnostic (REAL):** `useRealtimeVoice.js:238-250` logs a
  `mic_track_settings` diagnostic event to `db.realtime_diagnostics` containing
  `MediaStreamTrack.getSettings()` output (`echoCancellation`, `noiseSuppression`,
  `autoGainControl`, `sampleRate`, `channelCount`, opaque `deviceId`/`groupId`),
  plus `track.label` and the `enumerateDevices()` list of audioinput labels.
- **`getUserMedia` constraints (REAL, important):** `useRealtimeVoice.js:222` requests
  `{echoCancellation:true, noiseSuppression:true, autoGainControl:true}`. **AGC is on**
  — see the risk note in §1 and §9.B.
- **MISSING:** OS/hardware input gain or input level (the Web platform does not expose
  it — the code comment at `useRealtimeVoice.js:230` explicitly says so), mic
  availability/failure as a first-class event, continuous (non-session) mic health.
- **RF receiver health (REAL but unrelated):** `db.rf_bridge_health` —
  `backend/routes/rf_bridge_health.py` — tracks the SDR bridge's last-poll liveness
  (`BRIDGE_ALIVE_WINDOW_SECONDS`), **not** the room microphone.

### 2.9 Room / device state — **REAL** (not obviously baseline-relevant yet)

- **Model:** `SmartDevice` — `models.py:629`; `db.smart_devices`. **Commands:**
  `db.device_commands`, written by `backend/routes/devices.py`; `CaosEvent` `device.command`
  rows written for admin/kiosk device actions (`devices.py:228,244`,
  `admin_assistant_device_executor.py:49,61`).
- `db.locations` (`LocationUpdate` — `models.py:377`) — zone/room pings; feeds
  `insights.py` mobility + bathroom-frequency metrics and `resident_analytics.py::movement`.
- `Zone.is_bathroom` / `is_restricted` (`models.py:242`).

### 2.10 Receipts — **REAL**

- **Model:** `Receipt` — `models.py:868`; `db.receipts`.
- **Helper:** `backend/routes/receipts.py::create_receipt()` / `update_receipt_status()`
  (in-process calls, not HTTP). A receipt **points at** a domain object
  (`related_object_type`/`related_object_id`), never duplicates its fields.
- For a resident event: `record_resident_activation()` creates a
  `resident_assistance_event` receipt at **open** time (so `created_at` is the real
  open time); `_close_out()` marks it `completed` with a `result` string.
- Fields: `action_type`, `source`, `resident_id`, `room`, `zone`,
  `conversation_session_id`, `requested_by`, `assigned_role`/`assigned_user`, `status`
  (`created|acknowledged|in_progress|completed|failed|cancelled`), `acknowledged_at`,
  `completed_at`, `result`, `failure_reason`, `follow_up_required`.

### 2.11 Staff responses — **REAL**

- On `Alert`: `acknowledged_by` (name), `acknowledged_at`, `resolved_by`,
  `resolved_at`, `outcome`, `close_notes`, `response_seconds`, `duration_seconds`,
  `escalation_level`.
- Staff-task / request bus: `StaffTask` — `models.py:752`; `db.staff_tasks` (also
  serves non-emergency resident requests). `re_request_count`, `acknowledged_*`,
  `duration_minutes`, `requested_for_date/time_label`.
- Paging: `db.pager_events`. Escalation config: `EscalationRule` — `models.py:1336`;
  `db.escalation_rules`; `backend/routes/escalation.py`.

### 2.12 Event close data — **REAL**

- `alerts.py::close_alert` (`POST /api/alerts/{id}/close`, body `AlertClose{outcome,
  close_notes, category}`) → sets `status:"resolved"`, `outcome`, `close_notes`,
  `category`, `duration_seconds`; then `_close_out()` (pattern stats + receipt
  completion); then fires `ai.classify_alert_background()` if `category`/`ai_summary`
  missing.
- `alerts.py::resolve` (`POST /api/alerts/{id}/resolve`) — lighter close, no
  outcome/category; still runs `_close_out()`. Noted in code as having no visible UI
  button today but still a valid completion path.

### 2.13 Dashboard / reporting data — **PARTIAL** (two precursors)

**A. `insights.py` + `db.insights` + `Insights.jsx` — the closest existing system.**
- **Model:** `Insight` — `models.py:489`. **Route:** `backend/routes/insights.py`
  (`POST /api/insights/compute` wipes `db.insights` and recomputes for every
  resident; `GET /api/insights`, `/resident/{id}`, `/summary`).
- **Metrics:** `help_requests_7d`, `nighttime_activity_7d` (22:00–06:00),
  `mobility_7d` (distinct zones/day), `bathroom_frequency_7d` — each **current 7d vs
  prior 7d**, per resident.
- **Severity:** `_severity_and_confidence()` — `|deviation| ≥ 1.0 → concern`,
  `≥ 0.5 → watch`, else `info`; `confidence = min(1.0, sample_size / 10)`.
  `_cap_deviation()` clamps display to ±999%.
- **UI:** `frontend/src/pages/Insights.jsx` (131 lines) — grouped by resident,
  severity-coloured, explicit "signals for staff awareness, not clinical diagnoses"
  copy, a manual "Recompute" button.
- **Gaps vs the directive:** universal thresholds (50%/100%), alert-count metrics
  only, no time-of-day context buckets, no baseline maturity states, no
  press-frequency/duration/speech metrics, no raw→derived→deviation layering, **wipes
  rather than versioning** (no raw retained), flat list (not a "what changed" triage).

**B. `resident_patterns.py` + `db.resident_button_patterns` — the other precursor.**
- **Model:** `ResidentButtonPattern` — `models.py:363`. **Route:** `backend/routes/resident_patterns.py`
  (`GET /api/resident-patterns/{resident_id}`).
- Per `(resident_id, bucket)` where `bucket` is **hour-of-day "0".."23"**:
  `n_events`, `typical_press_count_p50`, `typical_press_count_p90`,
  `typical_open_minutes_p50`, `common_reason_tags` (top-3 categories), `burst_user`
  (bool: `n_events ≥ min_events and p50 press count ≥ 3`), `last_updated`.
- `update_pattern_stats(resident_id, closed_alert)` — called **only** from
  `_close_out()` after an event resolves; recomputes that one bucket from **all**
  the resident's `status:"resolved"` alerts in that bucket. Percentiles via
  `statistics.quantiles(..., n=100, method="inclusive")`.
- `footnote_for_resident_now(resident_id)` — called at **open** time from
  `record_resident_activation()`; returns `None` (no footnote) if the current
  hour-bucket has `< pattern_min_events` (default 5) observations, else a string like
  `"This hour: usually 1-2 presses"`.
- **Maturity gate exists** (binary) and **read-only** (nothing here can suppress /
  delay / gate an activation — asserted by test and by construction).
- **Gaps vs the directive:** overwrites (no raw retained), one context dimension
  (hour only), two metrics (press count, open minutes), binary maturity (not
  insufficient/preliminary/establishing/established), no deviation output — it is a
  *typical-range footnote*, not a *change detector*.

**C. `resident_analytics.py` — read-only clinical aggregates.**
- `GET /residents/{id}/stats?days=30` — current window vs prior window, by category
  and severity, `avg_response_s` / `max_response_s` / `avg_duration_s`,
  `falls_during_call`, `unresolved`, plus last-10 events.
- `GET /residents/{id}/movement?hours=24`, `GET /residents/{id}/briefing` (TTS-ready).

**D. `events.py` + `db.events` (`CaosEvent`) — designed substrate, barely populated.**
- **Model:** `CaosEvent` — `models.py:903`. **Helper:** `events.py::log_event()`.
  **Query seam:** `GET /api/events` (admin) with a broad filter set;
  `GET /api/events/conversation/{id}`.
- **Only 10 call sites**, all `admin_aria.*` (`admin_assistant.py`) or `device.command`
  (`devices.py`, `admin_assistant_device_executor.py`). **Nothing** logs resident
  sessions, presses, or alert lifecycle here.

### 2.14 Configuration — **REAL**

- `ResidentAssistanceConfig` — `models.py:1357`; `db.resident_assistance_config`;
  `backend/routes/resident_assistance_config.py` (`GET`/`PUT`, **never 404 — falls
  back to defaults**, `get_effective_config()` used server-side by
  `realtime.py::create_session`). Existing knobs: `aria_companion_timeout_sec` (300),
  `invite_silence_sec` (8), `burst_press_threshold` (3), `pattern_min_events` (5),
  `live_line_enabled`, `live_line_ring_timeout_sec` (30), `house_news_menu_stale_hours` (36).
- Same pattern as `EscalationRule` / `backend/routes/escalation.py`.

### 2.15 Full DB collection inventory (backend grep)

```
alerts · aria_capabilities · aria_capability_receipts · aria_conversations ·
aria_memories · aria_voice_sessions · chat_messages · command · conversations ·
departments · device_commands · device_tokens · escalation_rules · events ·
facilities · family_contacts · family_portal_reads · haikus · hardware_devices ·
hardware_receipts · insights · kiosks · locations · med_ack · med_reminders ·
memories · menu_items · menu_uploads · notifications · pager_events · pendants ·
pendant_unknown · realtime_diagnostics · receipts · resident_aria_leases ·
resident_assistance_config · resident_button_patterns · residents · rf_captures ·
rf_devices · rf_events · roadmap · schedule_items · smart_devices · staff_tasks ·
task_templates · timers · transport_* · users · user_sessions · wearables · zones
```

---

## 3. CURRENT ARCHITECTURE MAP (actual code paths)

### 3.1 RF pendant press → resident event

```
Physical pendant press
  → pendant transmits ~8 RF frames over ~1–3 s  [rf.py:46 comment, live-evidenced 2026-08-29]
  → SDR (Nooelec NESDR) → rtl_433 -F json -M utc -M level  [caos_rf_bridge.py:333]
  → caos_rf_bridge.py::on_record fires ONCE PER rtl_433 JSON line
      → POST /api/rf/event  (one HTTP call per frame, no dedup/throttle)  [caos_rf_bridge.py:487]
  → rf.py::rf_event  [per frame]
      → HMAC verify + monotonic sequence replay guard  [rf.py:375-388]
      → match fingerprint vs enabled db.rf_devices on same freq (±50 kHz),
        Hamming similarity ≥ device.match_threshold  [rf.py:402-423]
      → if matched:
          $set telemetry (last_seen_at, last_rssi, low_battery) + $inc rf_devices.press_count  [rf.py:450-453]
          → record_resident_activation(resident_id, room, source="rf_pendant", ...)  [rf.py:464]
      → db.rf_events.insert_one(raw_event)   ← EVERY frame stored, matched or not  [rf.py:490]
```

### 3.2 `record_resident_activation()` — the coalescing core  [resident_activation.py:36]

```
press = PressRecord(device_id, source, rssi); press.at = now
if resident_id or room:
    open_alert = db.alerts.find_one(
        status ∈ {active, acknowledged}
        AND (resident_id == rid   OR   (room == room AND resident_id == None)),
        sort=created_at desc)
    if open_alert:                                  ← COALESCE PATH
        db.alerts.update_one(open_alert, {
            $inc: { press_count: 1 },               ← +1 PER FRAME (no debounce)
            $push: { presses: press_dict },         ← one record PER FRAME
            $set:  { activation_consumed_at: None } ← re-arms kiosk relaunch
        })
        return {..., coalesced: True}
# else OPEN PATH:
resident_name/room resolved; footnote = footnote_for_resident_now(resident_id)
alert = Alert(..., press_count=1, pattern_footnote=footnote, source_metadata=...)
create_receipt(action_type="resident_assistance_event", related_object=alert)  [best-effort]
db.alerts.insert_one(alert); return {..., coalesced: False}
```

### 3.3 Kiosk button press → resident event  [alerts.py:20]

```
POST /api/alerts  (public; body AlertCreate)
  → resolve kiosk → room/zone; resolve resident by room or id
  → latest db.locations ping may refine zone
  → record_resident_activation(source="kiosk_button", auto_voice=False, ...)
      (same coalescing as §3.2 — a kiosk press for a resident with an open
       RF-pendant event attaches to that SAME alert_id)
  → if freshly created and zone known: $set zone
  → notifications.notify_family_for_alert(doc)  [best-effort]
```

### 3.4 Open event → kiosk relaunch → Aria/session

```
Kiosk UI polls GET /api/kiosks/{kiosk_id}/active-emergency every few seconds  [kiosks.py:32]
  q = { auto_voice: True,
        status ∈ {active, acknowledged},
        activation_consumed_at: None,
        (zone == kiosk.zone OR room == kiosk.room)  unless kiosk.is_central }
  → returns most-recent matching alert (or null)

Kiosk, on a returned alert → starts Realtime voice:
  POST /api/realtime/session {voice, resident_id, kiosk_id, room, alert_id, trigger_source}  [realtime.py:209]
    → if room: claim_or_reuse_room_lease(room, ...)  [realtime_room_lease.py:38]
         - unique index on room; steal if status ∉ {activating,active} OR last_seen_at < now-45s
         - if NOT claimed → return {_caos:{lease}} with NO OpenAI call (loser opens no mic)  [realtime.py:229]
    → build companion instructions; POST OpenAI /realtime/client_secrets (ephemeral)
    → return session + _caos{ instructions, tools, turn_detection=DEFAULT_VAD,
        noise_reduction=far_field, temperature=0.6, lease, context{...timeouts} }
  Browser (useRealtimeVoice.js):
    → getUserMedia({echoCancellation, noiseSuppression, autoGainControl})  [useRealtimeVoice.js:222]
    → log mic_track_settings diagnostic  [useRealtimeVoice.js:243]
    → RTCPeerConnection; POST /api/realtime/negotiate with X-CAOS-Ephemeral-Key
        (SDP exchange authenticates with the EPHEMERAL key, sends no session config —
         see §5.E, a historical bug fixed 2026-08-09)  [realtime.py:297]
    → on connect: POST /api/alerts/{alert_id}/aria-event {event:"activated"}
    → lease heartbeat every 20 s  [useRealtimeVoice.js:390]
    → timers from context: companion timeout 300 s → stop("companion_timeout");
       invite-silence 8 s → POST aria-event {silence_after_invite}  [useRealtimeVoice.js:334-340]
    → per-turn: POST /api/memory/realtime-turn (db.conversations);
       POST /api/realtime-diagnostics/event (speech_started/stopped, etc.)
```

### 3.5 Repeat press while an event is already open

```
New frame/press → record_resident_activation → COALESCE PATH (§3.2):
  press_count += 1; presses[] += 1; activation_consumed_at := None
Effect on the kiosk poll (§3.4): because activation_consumed_at is back to None,
  active-emergency returns the alert again → Aria relaunches on the SAME alert_id
  (even if a prior session for this event already ran and ended).
The event is NEVER suppressed, delayed, cancelled, or auto-closed by any of this
  (assistance-event invariant — verified by test_resident_events.py).
```

### 3.6 Staff response → close → receipt → analytics opportunity

```
POST /api/alerts/{id}/acknowledge  → status:acknowledged, acknowledged_by/at,
                                     response_seconds = ack - created  [alerts.py:155]
POST /api/alerts/{id}/close {outcome, close_notes, category}   (or /resolve)  [alerts.py:231]
  → status:resolved, resolved_by/at, outcome, close_notes, category,
    duration_seconds = resolved - (acknowledged_at or created_at)
  → _close_out(doc):  [alerts.py:179]
       resident_patterns.update_pattern_stats(resident_id, doc)   ← recompute hour-bucket
       receipts.update_receipt_status("alert", alert_id, "completed", result=...)
  → ai.classify_alert_background(alert_id) if category/ai_summary missing  [async task]

                       ▲
                       └── PROPOSED new hook point: also
                           record_assistance_observation(doc) → recompute_baselines → evaluate_event
```

### 3.7 What is NOT connected

- No resident-session summary record is written on session end (only operator
  `AriaVoiceSession`).
- `Alert.conversation_turns` is never populated.
- `db.events` (`CaosEvent`) receives nothing from the resident path.
- No speech-level (RMS/SNR/...) sample is captured at any point.
- Nothing correlates a speech-level change with a concurrent mic/room change
  (there's no speech-level metric to correlate yet).

---

## 4. ALL GAPS FOUND (ranked)

### P0 — blocks a correct, trustworthy baseline

| # | Gap | Where | Why it matters |
|---|-----|-------|----------------|
| P0-1 | **No RF-frame → human-press collapse.** `press_count` and `presses[]` count radio frames (~8 per physical press). | `resident_activation.py:70-77`; `rf.py:452,464`; `caos_rf_bridge.py:487`; nothing debounces. | Every "presses per event", "presses per day", "burst spacing", "press frequency vs baseline" metric is built on an inflated count. The directive names this explicitly ("debounce the radio, not the person"). Also already affects the live `resident_button_patterns` p50/p90 and the `burst_user` flag, and `RFDevice.press_count`. |
| P0-2 | **No raw-observation layer.** Both precursors discard raw data — `resident_button_patterns` overwrites its bucket doc; `insights.compute` does `db.insights.delete_many({})`. | `resident_patterns.py:100`; `insights.py:222`. | The directive requires recomputation as algorithms improve, and "Do not save only a final score." Today a baseline cannot be recomputed except by re-deriving from `db.alerts` (works for press/duration) — and **cannot** be recomputed at all for anything not stored on the alert (e.g. future speech metrics). |

### P1 — required for the directive's stated behaviour

| # | Gap | Why it matters |
|---|-----|----------------|
| P1-1 | **No contextual buckets beyond hour-of-day.** Only `resident_patterns` buckets, and only by hour. | Directive wants morning/afternoon/evening/bedtime/overnight, with hour-of-day only "when enough data exists", plus weekday/weekend later, and a **fallback ladder** so sparse data uses a broader bucket. |
| P1-2 | **No baseline maturity states.** Only a binary `pattern_min_events` gate. | Directive wants insufficient / preliminary / establishing / established. Pilot is 3–5 residents — most narrow buckets never mature; the system must say so rather than imply confidence. |
| P1-3 | **No speech-level telemetry at all** (RMS, dBFS, noise floor, SNR, VAD confidence value, clipping). | Directive metric #1. Cannot compute "speech level 9 dB below Helen's afternoon baseline." Requires new client instrumentation — see §9.B. |
| P1-4 | **Cannot distinguish resident change from room/mic change.** No continuous mic gain/SNR/availability; per-session `mic_track_settings` captures identity + processing flags only, not level. | Directive: "If resident speech appears quieter but microphone gain or SNR also changed, that should be visible before interpreting it as resident behavior." |
| P1-5 | **No deviation/change output** — `resident_patterns` produces a typical-range footnote, `insights` produces window deltas with universal thresholds. Neither compares *this event* to *this resident's comparable history* and classifies it. | Directive core: "Compare the current observation/event to that resident's comparable historical behavior." |
| P1-6 | **No multi-deviation composition.** | Directive: "Multiple simultaneous deviations may deserve greater prominence." |
| P1-7 | **No "What Changed?" view.** `Insights.jsx` is a flat per-resident list. | Directive: "Michael does NOT want a wall of gauges." Wants "TODAY — N THINGS WORTH LOOKING AT". |
| P1-8 | **`Alert.conversation_turns` never written**; resident session duration not stored. | Directive duration metrics (conversation duration, Aria companion duration, time before dismissal/timeout). All derivable from `db.conversations` / `db.realtime_diagnostics` but not currently rolled up anywhere. |

### P2 — quality / completeness

| # | Gap | Why it matters |
|---|-----|----------------|
| P2-1 | Interaction-type baselines (common request types, requests per interaction) not modelled. | Directive "INTERACTION PATTERNS" section — explicitly "eventually", lower priority. |
| P2-2 | Frequency metrics beyond presses (Aria interactions/hour/day/week, time between interactions) not aggregated per resident. | Directive metric #2 ("Frequency is a first-class metric"). Data exists in `db.conversations` + `db.alerts`; no rollup. |
| P2-3 | `db.events` (`CaosEvent`) not used as the resident telemetry spine despite being designed for exactly this. | Either adopt it for resident events or accept a purpose-built observation collection; decide deliberately rather than by omission. |
| P2-4 | No `facility_id` on residents/alerts; baseline config would be facility-scoped while data is not. | Fine for a single-tenant pilot; note it so multi-tenant doesn't silently inherit one facility's config. |
| P2-5 | Legacy `pendants.py` path still live and uses its own 60-s-window `press_count` logic, divergent from `record_resident_activation`. | Not in the RF pilot path, but a second, inconsistent definition of "press count" exists in the codebase. |

### P3 — future / watch

| # | Gap |
|---|-----|
| P3-1 | Weekday/weekend and longer-horizon (monthly/seasonal) buckets — directive says "if history eventually supports it". |
| P3-2 | Pilot-wide / cross-resident trend reporting (directive "PILOT" and "DASHBOARD GOAL" tail). |
| P3-3 | Weekly trend report / daily exception report as scheduled artifacts (only on-demand compute exists today). |
| P3-4 | `rtl_433` `snr`/`noise` fields are available per-frame but not persisted as first-class fields on `RFFingerprint` (only `rssi` is). |

---

## 5. IMPORTANT BUGS / SEMANTIC PROBLEMS (documented, NOT fixed)

> None of these were changed. Evidence, affected files/functions, and potential
> consequences only.

### 5.A — Every matched RF frame increments `press_count`; a single human press inflates it; there is NO frame echo-collapse

- **Evidence — bridge emits one event per frame:**
  `android-bridge/caos_rf_bridge.py::on_record` (lines ~472–495) runs for every
  `rtl_433` JSON line and, in passive mode, calls
  `_post("/api/rf/event", {kiosk_id, fingerprint, sequence, captured_at})` with **no
  dedup, throttle, or burst window**.
- **Evidence — pendant sends multiple frames per press:** `rf.py:46-52` (comment):
  *"One physical button press on a real Interlogix-Security pendant produces ~8 RF
  frames within ~1-3s (live-evidenced 2026-08-29)."*
- **Evidence — backend increments unconditionally:**
  `rf.py::rf_event` → for each matched frame: `$inc rf_devices.press_count` (`rf.py:452`)
  and then `record_resident_activation(...)` (`rf.py:464`).
  `resident_activation.py::record_resident_activation` coalesce path (`rf.py`
  equivalent lines `resident_activation.py:70-77`):
  `{$inc: {press_count: 1}, $push: {presses: press_dict}, $set: {activation_consumed_at: None}}`
  — no check of the previous press's timestamp, device, or fingerprint.
- **Evidence — the claimed debounce does not exist:** `rf.py:46-52` and
  `resident_activation.py:1-25` both state frame-level coalescing "lives in
  `routes/resident_activation.py` now". A full read of `resident_activation.py`
  (163 lines) shows **no time-window / same-fingerprint / same-press debounce** — only
  resident-scoped *event* coalescing (does an open event exist for this resident).
  Repo-wide grep for `debounce|echo|collapse|last_press|frame_window` in
  `backend/routes/*.py` finds only comments and unrelated matches.
- **Consequence:**
  - `Alert.press_count` ≈ (physical presses × frames-per-press). A "5-press event" may
    be one physical press; a "43-press event" (per `PROJECT_STATE.md`) is very likely
    a handful of physical presses, not 43.
  - `Alert.presses[]` contains one `PressRecord` per frame, so per-press timestamps
    are frame timestamps — "burst spacing" between them is inter-frame spacing
    (~0.1–0.4 s), not inter-press spacing.
  - `resident_button_patterns.typical_press_count_p50/p90` and `burst_user` are
    computed from this inflated `press_count` (`resident_patterns.py:68,93-97`).
  - `RFDevice.press_count` (lifetime) is inflated identically.
  - Any future "presses per day / per week / per event" or "press frequency vs
    baseline" metric inherits the inflation.
- **Tension with the directive:** the directive **requires** the fix ("human
  `press_count` must represent actual physical presses after radio-frame echo
  collapse") **and** says "Do not change existing pendant/help semantics." Resolution
  (proposed, not adopted): `press_count` semantics *do* change (mandated); the
  *assistance-event* semantics (one press opens/attaches to exactly one event, never
  suppressed/delayed/cancelled/auto-closed) do **not** change. See §9.A.
- **Test coupling:** `backend/tests/test_resident_events.py` issues 5 sequential
  `POST /api/rf/event` calls (`_press()` helper) and asserts `press_count == 5` and
  `len(presses) == 5` ("every press must be preserved as a real record"). These
  assertions encode the current frame-per-press behaviour; a same-fingerprint,
  short-window collapse would collapse those 5 near-simultaneous localhost calls to 1.
  This is the same "the old test encoded the now-reversed behaviour" situation that
  retired `test_rf_activation_gating.py` during the Level 1 work.

### 5.B — No audio-heartbeat / speech-level signal (not a regression — a capability gap)

- **Evidence:** grep for `rms|dbfs|snr|noise_floor|clipping|createAnalyser|AnalyserNode`
  across `frontend/src` and `backend` finds **no amplitude computation**.
  `useRealtimeVoice.js` and `realtimeMessageHandler.js` handle
  `input_audio_buffer.speech_started` / `speech_stopped` (facts + `assistantSpeaking`
  + timestamps) and `output_audio_buffer.*` (playback lifecycle) but never sample the
  `MediaStream`.
- The only periodic client→server signal during a call is the **room-lease heartbeat**
  (`fetch(/realtime/room/{room}/heartbeat)` every 20 s, `useRealtimeVoice.js:387-390`);
  its sole purpose is lease liveness (`STALE_SECONDS = 45`, `realtime_room_lease.py:36`).
  It carries no audio data.
- **Consequence:** speech-level baselines cannot be computed from anything stored
  today. This is a *missing capability*, not a broken one.

### 5.C — Kiosk relaunch on a repeat press: correct-by-design, but worth stating plainly

- `active-emergency` returns any alert with `status ∈ {active,acknowledged}` **and**
  `activation_consumed_at == None` (`kiosks.py:52-59`). Every coalesced press resets
  `activation_consumed_at` to `None` (`resident_activation.py:75`). So **a repeat
  press on an already-open event re-arms the kiosk to relaunch Aria on the same
  `alert_id`**, even if a prior session for that event already ran and ended.
- This is intentional (directive: a repeat press must be able to reactivate Aria; a
  dead connection must not suppress relaunch). Documented here only because the user's
  checklist asks about "kiosk behavior when another press lands on an already-open
  event." **No defect** — but note the interaction with 5.A: because frames are not
  collapsed, the *first* physical press already produces ~8 coalesced presses, each
  resetting `activation_consumed_at`; harmless (idempotent set to `None`) but noisy.

### 5.D — `alert_id` / activation lifecycle: verified consistent

- One physical incident = one `alert_id` for its whole life. Repeat presses (or a
  different mapped source — RF + kiosk — for the same resident) attach to that
  `alert_id` (`resident_activation.py:60-79`; `test_resident_events.py` Acceptance 16).
- A press **after** a genuine staff `resolve`/`close` opens a **new** `alert_id`
  (`test_resident_events.py:165`).
- `activation_consumed_at` is set **only** by `alert_lifecycle_events.py::aria_event`
  for `event ∈ {dismissed, timeout}` and by `staff_present()`
  (`alert_lifecycle_events.py:56-59`). `realtime_room_lease.py::release()` no longer
  touches it (2026-09-06 fix — see 5.F). **No inconsistency found.**

### 5.E — Historical OpenAI "default-instructions" bug — already fixed, documented in code

- `realtime.py::negotiate` docstring (lines 297–320) records a **real, confirmed**
  past bug: the SDP-exchange endpoint used to authenticate with the server's own
  `OPENAI_API_KEY` and build a fresh generic `session_config` (model + default voice,
  **no instructions**) on every call, discarding the ephemeral session that
  `/session` had just minted with the real Aria instructions — so live calls ran on
  OpenAI's default instructions (generic "Hey" opener, no name knowledge).
- **Fix (2026-08-09):** the browser forwards the same ephemeral key via
  `X-CAOS-Ephemeral-Key`; `negotiate` authenticates the SDP exchange with **that**
  key and sends **no** session config, so the call continues the already-configured
  ephemeral session.
- **Status: fixed and in place.** Documented here because the user's checklist asks
  about "any OpenAI/default-instruction problem you discovered." No action needed.

### 5.F — Historical "dead connection suppressed relaunch" bug — already fixed (2026-09-06)

- `PROJECT_STATE.md` (last entry) and `alert_lifecycle_events.py:33-50`: `release()`
  used to mark `activation_consumed_at` on **every** session end, conflating "resident
  said goodbye" with "the connection died", so a resident cut off by a network drop
  sat with an open event that wouldn't auto-relaunch until a fresh physical press.
- **Fix:** only `aria_event {dismissed|timeout}` and `staff_present()` consume the
  activation now; `release()` only frees the room slot.
- **Status: fixed and verified** (`test_resident_events.py` — "a session that just
  DIED must not suppress relaunch"). Documented for completeness.

### 5.G — Historical VAD "phantom transcript" / playback-timing bug — already fixed

- `realtimeMessageHandler.js` (~line 225 comment) records a fixed bug where
  `assistantSpeakingRef` flipped `false` on `response.done` (generation complete)
  rather than on actual audio-playback completion, leaving the echo-detection window
  blind for multi-second replies. Fixed by tracking
  `output_audio_buffer.started/stopped/cleared` (real WebRTC/SIP server events).
- Related: `realtime_audio_config.py:18-24` — `far_field` noise reduction was added
  after phantom "Thank you." / "Cheers, bye." transcripts during genuine silence.
- **Status: fixed.** Relevant to baseline work only as a caveat: user turns flagged
  `trusted:false` (echo-suspect) exist in `db.conversations` and must be excluded from
  speech/interaction metrics, just as they're excluded from memory extraction.

---

## 6. BASELINE / OBSERVATION ARCHITECTURE — **PROPOSED, NOT YET APPROVED**

> Everything in this section is a proposal for review. No collection, model, route,
> or file listed here exists yet. Names are provisional.

### 6.1 Three layers

```
LAYER 1  RAW OBSERVATIONS      db.resident_observations   (append-only, never overwritten)
              │  one document per closed assistance event (voice-session observations added later)
              ▼
LAYER 2  DERIVED BASELINE      db.resident_baselines      (recomputable from Layer 1 alone)
              │  one document per (resident_id, metric, context_bucket)
              ▼
LAYER 3  CURRENT DEVIATION     db.resident_deviations     (dated, kept as history — not wiped)
              │  zero-or-more documents per closed event
              ▼
         "WHAT CHANGED?"  GET /api/whats-changed           (read-time aggregation over Layer 3)
```

### 6.2 Layer 1 — raw observations

- **Collection:** `db.resident_observations`. **Model:** `ResidentObservation` (proposed).
- **Written by:** a new best-effort call from `alerts.py::_close_out()` —
  `record_assistance_observation(alert_doc)` — alongside the existing pattern-stats and
  receipt-completion calls. Never blocks the staff response.
- **Proposed shape:**
  ```
  observation_id, schema_version=1,
  resident_id, room, facility_id (nullable),
  kind = "assistance_event"  ( | "voice_session" later ),
  occurred_at (ISO, = alert.created_at),
  context: { hour: 0..23, part_of_day: morning|afternoon|evening|bedtime|overnight,
             weekday: 0..6, is_weekend: bool },
  source_ref: { type: "alert", id: alert_id, receipt_id },
  metrics: {
    human_press_count, rf_frame_count, press_span_sec, max_burst_presses,
    time_to_first_ack_sec, event_open_sec,
    aria_response_latency_sec, resident_speech_sec, resident_silence_sec,
    conversation_sec, conversation_turns,
    responded_to_aria (bool), silence_after_invite (bool),
    speech_rms_dbfs, noise_floor_dbfs, snr_db, vad_confidence, clipping_pct,  # null until §9.B lands
    mic_available (bool), input_processing: {agc, ns, ec}                     # from mic_track_settings
  },
  category, resident_stated_reason, outcome,
  env: { rf_rssi_median, rf_snr_median }   # aggregated from db.rf_events for this alert_id
  ```
- **Nothing derived here.** Only measured/observed facts + enough context to
  **re-bucket** later. Timing metrics are read from `db.realtime_diagnostics` /
  `db.conversations` for the event's `session_id`; press metrics from
  `Alert.presses[]` (with `human_press_count` computed by collapsing frame
  timestamps — see §9.A option 2 — if frame-collapse is not done at source);
  `env` from `db.rf_events` filtered by `alert_id`.
- **Recomputation:** re-reading `db.resident_observations` fully reconstructs every
  baseline. For anything not yet stored (future audio metrics on historical events),
  the field stays `null` and back-fills only for events observed after instrumentation
  ships — this is why raw storage must start now.

### 6.3 Context bucketing — pure helper, one source of truth

- **Module:** `backend/routes/resident_baseline_context.py` (proposed, ~60 lines,
  no DB).
  - `context_bucket(dt) -> {"hour": h, "part_of_day": p, "weekday": w, "is_weekend": b}`
  - `part_of_day` boundaries (proposed, facility-local; tunable via config):
    overnight 00:00–05:59 · morning 06:00–11:59 · afternoon 12:00–16:59 ·
    evening 17:00–20:59 · bedtime 21:00–23:59.
  - `bucket_fallback_ladder(dt) -> ["h<HH>", "<part_of_day>", "all"]` — most specific
    first.
- Shared by the observation writer (to stamp context) and the baseline engine (to
  choose which baseline applies) so bucketing is defined once.

### 6.4 Layer 2 — derived personal baseline

- **Collection:** `db.resident_baselines`. **Model:** `ResidentBaseline` (proposed).
- **Module:** `backend/routes/resident_baselines.py` (proposed, ~150 lines).
  - `recompute_baselines(resident_id)` — for each metric × each bucket in the ladder,
    aggregate the resident's observations whose `context` matches; compute
    `n, p10, p50, p90, mean, stdev, mad`; assign maturity.
  - `get_baseline(resident_id, metric, dt)` — walk the fallback ladder; return the
    **most specific** baseline whose maturity ≥ a configured floor (default:
    `establishing`); if none qualifies, return the `all` baseline with its real
    maturity (which may be `insufficient` / `preliminary`).
- **Proposed shape:**
  ```
  resident_id, metric, context_bucket ("h14" | "afternoon" | "all"),
  n_observations, window_start, window_end,
  p10, p50, p90, mean, stdev, mad,
  maturity: insufficient (<3) | preliminary (3–6) | establishing (7–14) | established (15+),
  last_computed_at, schema_version=1
  ```
- **Recomputed:** after each new observation (incrementally, for that resident's
  affected buckets) **and** on demand (`POST /api/resident-baselines/{id}/recompute`),
  fully from Layer 1.
- **Sparse-data behaviour:** thresholds above are deliberately low for a 3–5 resident
  pilot but still refuse to treat 1–2 points as a norm. The fallback ladder means a
  brand-new resident's afternoon event is compared against their `all` baseline (or
  nothing) rather than an empty `h14` bucket. Buckets are only *populated* — never
  fabricated — so an unseen bucket simply has no document.

### 6.5 Layer 3 — deviation

- **Collection:** `db.resident_deviations` (dated; kept as history). **Module:**
  `backend/routes/resident_deviations.py` (proposed, ~190 lines).
- `evaluate_event(alert_doc) -> [Deviation]` — called from `_close_out()` **after**
  the observation is written and baselines recomputed.
- **Per metric:** fetch `get_baseline(resident_id, metric, occurred_at)`. If maturity
  < `preliminary` → emit at most an `informational` note (or nothing), never
  `notable`. Otherwise compute:
  - `ratio = value / p50` (guard p50==0),
  - `spread_score = (value − p50) / (p90 − p50)` when `p90 > p50`, else
    `(value − p50) / (mad or stdev or 1)`,
  - `abs_delta = value − p50`.
- **Classification (proposed, config-tunable):**
  - `informational` — `spread_score` within ~1, or immature baseline.
  - `notable` — `spread_score ≳ deviation_notable_ratio` (default ~2) in the
    direction that matters for that metric.
  - `prominent` — a single extreme metric, **or** `≥ deviation_prominent_count`
    (default 2) simultaneous `notable` deviations on the same event (this is where
    "multiple simultaneous deviations deserve greater prominence" is implemented —
    prominence is a property of the *event*, recorded on each contributing deviation).
- **Explainability:** every deviation carries a mechanical English `explanation` built
  from templates (e.g. `"5 presses in 112 s — above this resident's recent afternoon
  baseline (usual 1, p90 = 2)"`, `"event open 24 min — above the recent comparable
  baseline (usual 8 min)"`) and `evidence_refs = {observation_id, alert_id,
  baseline_id, rf_event_ids?}`. **Banned-phrase guard:** a fixed list
  (`weak, frail, sick, ill, declining, deteriorating, dementia, UTI, stroke,
  confused, unwell, ...`) must never appear in any `explanation`; enforced by a test.
- **Environment correlation:** if a speech-level metric is `notable` **and**
  (`snr_db` moved materially vs its own baseline **or** `mic_available` is false
  **or** `input_processing.agc` differs from the resident's usual), set
  `environment_correlated: true` and prepend a caveat to the `explanation`
  ("— note: room microphone SNR also changed over this period"). Until §9.B ships,
  speech metrics are `null`, so this branch is dormant but present.
- **Proposed shape:**
  ```
  deviation_id, created_at, resident_id, room, alert_id, observation_id,
  metric, value, baseline_context_bucket, baseline_maturity,
  p50, p90, ratio, spread_score, abs_delta, direction (above|below),
  classification (informational|notable|prominent),
  event_prominence (informational|notable|prominent),   # max across the event's deviations
  environment_correlated (bool),
  explanation (str), evidence_refs (obj), schema_version=1
  ```

### 6.6 Configuration — **PROPOSED**

- **Option A (proposed):** new `backend/routes/resident_baseline_config.py` with its
  own `ResidentBaselineConfig` model + `GET`/`PUT`, same never-404-falls-back pattern
  as `resident_assistance_config.py`. Keeps `models.py` (1555 lines, already over the
  300-line cap) untouched.
- **Knobs:** `part_of_day_boundaries`, `maturity_thresholds {preliminary:3,
  establishing:7, established:15}`, `baseline_maturity_floor_for_deviation:
  "establishing"`, `deviation_notable_ratio: 2.0`, `deviation_prominent_count: 2`,
  `frame_echo_collapse_sec: 2.0` (only used if §9.A option 1 is chosen),
  `observation_recompute_window_days` (0 = all history).
- **Alternative:** fold these onto `ResidentAssistanceConfig` (the natural home) and
  accept a small additive edit to `models.py` — see §10 for the trade-off.

### 6.7 What does NOT change

- `record_resident_activation()`, `_active_emergency`, the room lease, the
  assistance-event invariant. Layer 3 is **read-only with respect to events** — it
  cannot suppress, delay, cancel, or close an event, and nothing in the activation
  path imports or calls it. (A test asserts the import graph.)

---

## 7. DASHBOARD CONCEPT — "WHAT CHANGED?" — **PROPOSED, NOT YET APPROVED**

### 7.1 Data & endpoint

- `GET /api/whats-changed?window=today|7d` (proposed; lives in
  `resident_deviations.py` or a thin `backend/routes/whats_changed.py`, ~80 lines).
- Reads `db.resident_deviations` for the window; keeps only `classification ∈
  {notable, prominent}` (plus optionally the highest-signal `informational` per
  resident); groups by **resident** and separately surfaces **room/device** items
  (e.g. an `environment_correlated` cluster or a mic-availability drop) as their own
  rows, matching the directive's example (a "Room 214 — Microphone SNR degraded" row
  next to resident rows).
- Orders by `event_prominence` desc, then recency. Returns, per row:
  `{scope: "resident"|"room", resident_id?, name?, room, headline, sub_lines[],
  prominence, evidence: {alert_id, observation_id, deviation_ids[]}}`.

### 7.2 Presentation

- Header: **"TODAY — N THINGS WORTH LOOKING AT"**. Each row: name + room, a one-line
  headline, 1–3 mechanical sub-lines (each a deviation `explanation`), a prominence
  chip reusing `Insights.jsx`'s `SEV_META` colours (`concern`/`watch`/`info` →
  `prominent`/`notable`/`informational`).
- Row expands to the stored evidence: the contributing deviations with their p50/p90,
  the observation's raw metrics, and a link to the alert detail
  (`AlertDetailDialog.jsx` already exists).
- Explicit non-diagnostic banner, same wording family as the existing Insights page.
- The old flat insights list stays available as a secondary tab (no removal).

### 7.3 Frontend files — **PROPOSED**

- New: `frontend/src/pages/WhatChanged.jsx` (~200 lines), reusing
  `components/ui/{card,badge,button}` and the `api` client.
- Modified: `frontend/src/lib/adminTabGroups.js` (register the tab — small, and it's
  a registration list, not logic), and whichever router/switch renders admin tabs
  (`Admin.jsx`) — one route entry.
- Reuse: `AlertDetailDialog.jsx` for drill-down.

---

## 8. TEST PLAN — **PROPOSED**

Target file: `backend/tests/test_resident_baselines.py` (new). The context, baseline,
and deviation modules are pure/importable, so most tests run without HTTP; a few
integration checks hit the running backend the way `test_resident_events.py` does.

| # | Test | Asserts |
|---|------|---------|
| T1 | **Insufficient history** | A resident with 0–2 observations → baseline maturity `insufficient`; `evaluate_event` emits no `notable`/`prominent` deviation (informational at most), never a fabricated range. |
| T2 | **Contextual (time-of-day) baseline** | Afternoon observations do not affect a bedtime bucket; a bedtime event is compared only against bedtime/`all`, not afternoon. |
| T3 | **Fallback baseline** | A sparse `h14` bucket (n<threshold) → `get_baseline` falls back to `afternoon`; if that's also sparse → `all`. Returns the correct bucket label and maturity. |
| T4 | **Frequency deviation** | `human_press_count = 5` vs baseline p50 = 1, p90 = 2 → `notable`, `direction = above`, explanation contains the counts and the baseline range, no medical words. |
| T5 | **Duration deviation** | `event_open_sec` ≈ 24 min vs p50 ≈ 8 min → `notable`. |
| T6 | **Speech-level deviation** | `speech_rms_dbfs` 9 dB below comparable p50 → `notable`, phrasing is "below … recent comparable baseline", never "sounds weak/quiet-therefore-unwell". (Runs against synthetic observations; real capture is §9.B.) |
| T7 | **Multiple simultaneous deviations** | Two+ `notable` metrics on one event → `event_prominence = prominent`; one metric alone stays `notable` unless extreme. |
| T8 | **Environmental correlation** | Speech-level drop **with** a concurrent `snr_db` drop / `mic_available = false` → `environment_correlated = true` and the caveat text is present; speech drop **without** an env change → flag false. |
| T9 | **No medical phrasing** | Every `explanation` produced across a matrix of deviation inputs is checked against the banned-phrase list; also asserts no diagnosis/first-person-condition claims. |
| T10 | **Assistance-event invariant** | `resident_deviations` / `resident_baselines` / `resident_observations` modules are not imported by `resident_activation.py` / `alerts.py` create path / `kiosks.py` active-emergency; `evaluate_event` has no code path that writes `db.alerts` status/lifecycle fields. |
| T11 | **Recomputation from stored observations** | Populate `db.resident_observations`; `recompute_baselines`; snapshot `db.resident_baselines`; wipe baselines; recompute again → byte-identical (modulo `last_computed_at`). Then add one observation → only the affected buckets change. |
| T12 | **RF-frame vs human-press semantics** | Given a `presses[]` array with 8 records spanning 1.4 s at one device/source → `human_press_count = 1`, `rf_frame_count = 8`, `max_burst_presses` reflects the collapse; given 3 records spaced 40 s apart → `human_press_count = 3`. (Tests the collapse **calculator**, wherever it ends up living — see §9.A.) |
| T13 | **Maturity transitions** | n = 2 → `insufficient`; 4 → `preliminary`; 10 → `establishing`; 20 → `established`, at the configured thresholds. |
| T14 | **Deviation history is kept** | Two closes for the same resident on the same day → two dated `db.resident_deviations` sets, neither overwritten; `whats-changed` dedups to the most prominent per resident for display but the rows remain queryable. |

---

## 9. THE TWO DECISIONS — full write-up (NOT decided)

### 9.A — FRAME COLLAPSE

**Current behaviour (proven — see §5.A).** One physical pendant press → ~8 RF frames
→ ~8 `POST /api/rf/event` → `record_resident_activation` coalesce path runs ~8× →
`Alert.press_count += 8`, `Alert.presses[] += 8`, `RFDevice.press_count += 8`. No
debounce of any kind. `resident_button_patterns` p50/p90 and `burst_user` are built on
the inflated count.

**Why it matters.** The directive makes human-accurate press counting a named
requirement ("debounce the radio, not the person"; "human `press_count` must
represent actual physical presses after radio-frame echo collapse"). Every
press-frequency / presses-per-event / burst-spacing metric — and the live pattern
footnote residents' events already show — depends on it. It also collides with the
directive's "Do not change existing pendant/help semantics," so the path chosen
should be deliberate.

**Option 1 — Fix at the activation boundary, in this lane.**
- In `record_resident_activation()`, before `$inc`/`$push`: if the open event's last
  `presses[]` entry has the same `source` (and, for RF, matching
  `source_metadata.rf_device_id` / fingerprint) within `frame_echo_collapse_sec`
  (new config, default ~2 s), treat the new frame as an echo — do **not** increment
  `press_count`, do **not** append a new `PressRecord`; instead `$inc` a
  `frame_count` on the last press (or append to a separate `raw_frames[]`).
- Every raw frame still lands in `db.rf_events` unchanged — no evidence lost.
- `press_count` now means physical presses (the mandated semantics).
- **Cost:** ~20 changed lines in one existing 163-line file (stays well under the
  cap); update the 2 assertions in `test_resident_events.py` that currently assert
  `press_count == 5` / `len(presses) == 5` for 5 rapid API calls (space them >2 s
  apart, or give them distinct fingerprints, or assert the new collapsed semantics).
- **Risk:** touches a Level 1 code path and its regression test; a too-wide window
  could merge two genuinely fast presses (mitigated by a tight default + same-
  fingerprint requirement; genuine repeat presses on a PERS pendant are ≥1 s apart
  and often re-trigger identical payloads anyway — so also key on a minimum gap, not
  just fingerprint identity).

**Option 2 — Record both, change nothing live.**
- Leave `press_count` / `presses[]` / `RFDevice.press_count` exactly as they are
  (frame-inflated).
- Compute a derived `human_press_count` (and `rf_frame_count`, `press_span_sec`,
  `max_burst_presses`) **only in Layer 1**, at observation time, by collapsing
  `presses[]` timestamps (same-source, sub-window). Baseline math uses the derived
  value.
- **Cost:** zero change to the live path, zero test changes; one pure function
  (~30 lines) + its test (T12).
- **Risk:** the codebase keeps two meanings of "press count" indefinitely; staff
  reading `Alert.press_count` in the existing dashboard / `AlertDetailDialog` still
  see the inflated number; `resident_button_patterns` stays inflated unless separately
  addressed. The directive's requirement is met *for baselines* but not *for the
  event record itself*.

**Option 3 — Defer entirely.**
- Baselines use `rf_frame_count` as-is; press-frequency metrics are flagged
  low-confidence; a dedicated later lane fixes collapse at source (bridge and/or
  activation).
- **Cost:** least work now.
- **Risk:** ships a known-inflated first-class metric into a pilot whose explicit
  purpose is to learn which metrics are useful; the "43-press event" class of
  confusion persists.

**My recommendation (for review only — not acted on):** **Option 1**, with a
conservative default (`frame_echo_collapse_sec ≈ 2.0`, require same
source + same `rf_device_id`, and a minimum 800 ms gap to count as a new press),
plus keeping `rf_frame_count` on the alert so nothing is hidden. It's the only option
that makes the *event record itself* correct, which is what the directive asks for,
and the blast radius is one small file + two test assertions — the same kind of
"the old test encoded the now-corrected behaviour" update already done once in the
Level 1 work. If Michael wants zero risk to the Level 1 path this pass, **Option 2**
is the safe fallback and can be upgraded to Option 1 later without rework (the
collapse calculator is identical; only its call site moves).

### 9.B — AUDIO TELEMETRY

**What exists now (proven).**
- VAD **events** with timestamps and an `assistant_speaking` boolean, in
  `db.realtime_diagnostics` (`speech_started`, `speech_stopped`,
  `output_audio_buffer.*`).
- A per-session `mic_track_settings` diagnostic: `getSettings()` (`echoCancellation`,
  `noiseSuppression`, `autoGainControl`, `sampleRate`, `channelCount`, opaque
  `deviceId`), `track.label`, and the `enumerateDevices()` audioinput list.
- `getUserMedia` is requested with `echoCancellation: true`, `noiseSuppression: true`,
  **`autoGainControl: true`**.
- Per-frame **RF** `rssi` in `db.rf_events` (the pendant radio, not the room mic).
- **Derivable with no new capture:** Aria response latency, resident speech-segment
  duration, silence duration, conversation duration, turn count, "responded to
  invite?" (already stored as `silence_after_invite`).

**What does not exist.**
- Any amplitude/level measurement: speech **RMS / dBFS**, **noise floor (dBFS)**,
  **SNR (dB)**, **clipping %**.
- A numeric **VAD confidence** value (only the boolean that VAD fired).
- Continuous / non-session **microphone health** (availability, failure events,
  input gain — the last is not exposed by the Web platform at all).

**Why the raw audio isn't already available.** The resident voice path is
OpenAI Realtime over **WebRTC**: the browser peers **directly** with OpenAI; our
backend only mints the ephemeral token and relays the SDP (`realtime.py`). Audio
never transits our server, so level measurement must happen **in the browser** on the
local `MediaStream`, or not at all.

**What real speech-level capture would require.**
1. **Client instrumentation** in `frontend/src/lib/useRealtimeVoice.js`: create an
   `AudioContext` + `AnalyserNode` (and/or an `AudioWorkletNode` for accurate RMS) on
   the captured `MediaStream`, sampled every ~250–500 ms. Compute, per window:
   RMS→dBFS, a rolling noise-floor estimate (e.g. 10th-percentile of recent frames),
   SNR = speech_dBFS − noise_floor_dBFS, clip fraction (samples ≥ full-scale).
   Correlate windows with the existing `speech_started/stopped` events so only
   resident-speech windows feed the speech metric and only inter-speech windows feed
   the noise floor.
2. **AGC handling.** With `autoGainControl: true`, measured RMS is already
   level-normalised. Options: (a) open a **second, unprocessed** `getUserMedia`
   track (`autoGainControl:false, noiseSuppression:false, echoCancellation:false`)
   *only* for the measurement tap while the processed track feeds OpenAI; (b) keep
   AGC and treat the metric as **relative-only within a session** plus track
   `autoGainControl` state as a covariate; (c) accept the limitation and lean on SNR
   (a ratio, more robust to gain changes) rather than absolute dBFS. Decision needed.
3. **Ingest endpoint.** New `POST /api/room-audio/sample` (public, fire-and-forget,
   same trust tier as `realtime-diagnostics`) writing to `db.room_audio_samples`:
   `{session_id, resident_id, room, at, window_ms, speech_rms_dbfs, noise_floor_dbfs,
   snr_db, clipping_pct, agc, ns, ec, mic_available}`. Aggregated into the Layer 1
   observation at event close (median over the event).
4. **Room/mic-health surface.** Derive `mic_available` (track ended / muted /
   `getUserMedia` failure), noise-floor trend, and AGC-state changes per room →
   feeds the deviation engine's environment-correlation branch and the "Room 214 —
   microphone SNR degraded" dashboard row.

**Privacy / storage implications.** No raw audio, ever — only scalar levels per
window, consistent with `realtime_diagnostics`' existing "never raw audio" rule.
`db.room_audio_samples` would be higher-volume (a few writes/second during a call);
mitigations: only sample during active calls, write aggregates (e.g. 5 s rollups)
rather than every 250 ms window, TTL-index the raw samples (~30–90 days) and keep
only the per-event median in `db.resident_observations` long-term. Levels are not
content, but SNR/level trends are still resident-adjacent data and stay under the
same access controls as the rest of the resident record.

**What can be done now vs later.**
- **Now, no new capture:** all timing/frequency/duration metrics; the full
  three-layer architecture; the dashboard; every test except the *real-capture* part
  of T6/T8. Speech-level fields exist in the schema as `null`.
- **Later (its own lane):** the `AnalyserNode` sampler, the AGC decision, the
  `/api/room-audio/sample` endpoint, `db.room_audio_samples`, and activating the
  environment-correlation branch with real data.

**My recommendation (for review only — not acted on):** **timing now, audio-level as
a named follow-up lane.** The timing/frequency/duration metrics are the bulk of
directive metrics #2–#5 and need zero new capture or risk; shipping the three-layer
foundation with nullable speech fields lets audio-level work land later with no
rework. Bundling the client `AnalyserNode` + AGC decision + new endpoint into this
pass enlarges the change, touches the live voice hook, and forces the AGC design
question before there's a foundation to test it against.

---

## 10. FILE IMPACT MAP

### 10.1 Files already changed
**None.** This investigation made no code changes. `git status` is clean (see §11).
The only new file is this report.

### 10.2 New files currently PROPOSED (none created yet)

| Path | Purpose | Est. lines |
|------|---------|-----------|
| `backend/routes/resident_baseline_context.py` | pure bucketing helpers (`context_bucket`, `bucket_fallback_ladder`), no DB | ~60 |
| `backend/routes/resident_observations.py` | Layer 1 writer + admin read endpoint; `record_assistance_observation()` | ~130 |
| `backend/routes/resident_baselines.py` | Layer 2 `recompute_baselines()`, `get_baseline()`, read endpoint | ~150 |
| `backend/routes/resident_deviations.py` | Layer 3 `evaluate_event()`, `GET /resident-deviations`, `GET /whats-changed` | ~190 |
| `backend/routes/resident_baseline_config.py` | `ResidentBaselineConfig` model + `GET`/`PUT`, never-404 pattern | ~70 |
| `backend/tests/test_resident_baselines.py` | the §8 test plan | ~250 |
| `frontend/src/pages/WhatChanged.jsx` | "What Changed?" view | ~200 |
| *(follow-up lane only)* `backend/routes/room_audio.py` | `POST /api/room-audio/sample` ingest | ~70 |

All backend production files are within the 300-line cap as scoped.

### 10.3 Existing files likely to need modification (small, additive)

| Path | Change | Notes / risk |
|------|--------|--------------|
| `backend/routes/alerts.py` (359 lines) | +2 lines in `_close_out()` to call `record_assistance_observation()` → `recompute_baselines()` → `evaluate_event()`, best-effort/try-except like the existing calls there. | Already at the cap; **additive only, no growth of a responsibility** — but technically makes a >300-line file ~2 lines longer. Acceptable per the "additive hook" reading; flag for Michael. Alternative: put the 3-call sequence in a one-line `from routes.resident_observations import on_event_closed` and call that. |
| `backend/server.py` | +4–5 `include_router` lines + imports. | Registration boilerplate (config-like), exempt in spirit. Merge-conflict-prone (every new route touches it). |
| `backend/routes/resident_activation.py` (163 lines) | **Only if §9.A Option 1 is chosen:** ~20 lines for frame-echo collapse in the coalesce path. | Touches a Level 1 path. Stays well under the cap. |
| `backend/tests/test_resident_events.py` (298 lines) | **Only if §9.A Option 1:** update ~2 assertions that encode frame-per-press. | Same precedent as retiring `test_rf_activation_gating.py`. |
| `backend/models.py` (1555 lines) | **Avoid.** If config is folded into `ResidentAssistanceConfig` instead of a new file, ~6 additive field lines. | File is 5× the cap; AGENTS.md rule 8 says don't grow it. **Prefer the standalone `resident_baseline_config.py`.** |
| `frontend/src/lib/adminTabGroups.js` | +1 tab registration entry. | Small list file. |
| `frontend/src/pages/Admin.jsx` | +1 route/case for the new tab. | Small. |
| `frontend/src/lib/useRealtimeVoice.js` (410 lines) | **Only in the audio-telemetry follow-up lane**, not this pass. | High-traffic file; over the frontend soft target; other voice work touches it constantly. |

### 10.4 Files to AVOID (another workstream may touch them)

- `backend/routes/realtime*.py`, `frontend/src/lib/useRealtimeVoice.js`,
  `frontend/src/lib/realtimeMessageHandler.js` — active voice-pipeline area; the
  Level 1 live break-test pass (named as the next step in `PROJECT_STATE.md`) is
  expected to touch these. The baseline lane should not, except in the explicit
  audio-telemetry follow-up.
- `backend/routes/resident_activation.py`, `backend/routes/alerts.py`,
  `backend/routes/alert_lifecycle_events.py`, `backend/routes/kiosks.py` — the
  Level 1 assistance-event core; still being live-hardened. Touch only via the single
  agreed `_close_out()` hook (and, if chosen, the §9.A collapse edit) — nothing else.
- `backend/routes/rf.py` (530 lines) — RF intake; over the cap; recently changed for
  RSSI/`-M level`. The bridge (`android-bridge/caos_rf_bridge.py`) is also off-limits
  for this lane (frame collapse, if done, is done backend-side per §9.A Option 1).
- `backend/models.py` — see above.
- `backend/routes/insights.py` / `frontend/src/pages/Insights.jsx` — leave the
  existing system running; the new work sits alongside it, not on top of it.
- Anything under `backend/routes/transportation*`, `menu*`, `admin_assistant*` —
  unrelated, actively developed.

---

## 11. CURRENT GIT STATE

```
$ pwd
/home/caoscare-1/CAOSCARE-CLAUDE

$ git branch --show-current
claude/resident-baselines

$ git rev-parse HEAD
d994331e44f60451be7f63748dd850f59239712a

$ git rev-parse origin/main
d994331e44f60451be7f63748dd850f59239712a

$ git status --short
(empty — clean working tree at investigation time)

$ git status --porcelain
(empty)
```

Changed files: **none.**
Untracked files at investigation time: **none.**
After this report is written: one new untracked file,
`docs/RESIDENT_BASELINE_AUDIT_REPORT.md` (this document), which will be the **only**
thing committed.

---

## 12. PROVEN vs INFERRED vs PROPOSED

### 12.1 PROVEN FROM CURRENT CODE / DATA

- `Alert` (`models.py:283`) already stores `presses[]`, `press_count`, `event_log[]`,
  `response_seconds`, `duration_seconds`, `category`, `ai_summary`,
  `resident_stated_reason`, `aria_state`, `live_line_state`, `silence_after_invite`,
  `requested_staff`, `source_metadata`, `receipt_id`. `conversation_turns` is declared
  but never written.
- `record_resident_activation()` (`resident_activation.py:36`) is the single
  press-intake/coalescing point; its coalesce path does
  `{$inc:{press_count:1}, $push:{presses}, $set:{activation_consumed_at:None}}` with
  **no time/fingerprint debounce**.
- `caos_rf_bridge.py::on_record` POSTs **one `/api/rf/event` per `rtl_433` line**; no
  dedup/throttle. `rf.py` comment: one physical press ≈ 8 frames.
- Therefore **`press_count` and `presses[]` currently count RF frames, not physical
  presses**; `RFDevice.press_count` likewise; `resident_button_patterns` p50/p90 and
  `burst_user` are derived from the inflated count.
- **No frame echo-collapse exists** anywhere (bridge, `rf.py`, `resident_activation.py`,
  `pendants.py`), despite code comments claiming it "lives in `resident_activation.py`".
- Every RF frame (matched or not) is persisted to `db.rf_events` with full
  fingerprint, per-frame `rssi`, `decoded.battery_ok`, `match_score`, `captured_at`,
  `received_at`, `alert_id`.
- `_close_out()` (`alerts.py:179`) runs after `resolve`/`close_alert` and calls
  `resident_patterns.update_pattern_stats()` + `receipts.update_receipt_status(...
  "completed")` — a viable hook point.
- `resident_patterns.py` buckets **only by hour-of-day**, tracks **only** press-count
  percentiles + open-minutes p50 + reason tags + `burst_user`, **overwrites** the
  bucket doc, and gates footnotes on a **binary** `pattern_min_events` (default 5).
- `insights.py` compares **current 7d vs prior 7d** for alert-count metrics with
  **universal** 50%/100% thresholds, `confidence = min(1, sample/10)`, and
  **wipes `db.insights`** on every `compute`.
- No RMS/dBFS/noise-floor/SNR/clipping/VAD-confidence value is computed or stored
  anywhere; the resident audio path is WebRTC direct-to-OpenAI, so raw audio never
  reaches the backend.
- `db.realtime_diagnostics` stores `speech_started`/`speech_stopped` (with
  `assistant_speaking`) and `mic_track_settings` (`getSettings()` + device labels)
  with timestamps → speech/silence/latency/conversation durations are **derivable**;
  input **gain/level is not** (not exposed by the Web platform).
- `getUserMedia` uses `autoGainControl: true` (+ `echoCancellation`,
  `noiseSuppression`).
- `db.events` (`CaosEvent`) is populated only for `admin_aria.*` and `device.command`
  (10 call sites); nothing from the resident path.
- `ResidentAssistanceConfig` uses a per-facility, never-404-falls-back-to-defaults
  pattern (`resident_assistance_config.py`), mirroring `EscalationRule`.
- Historical bugs found **already fixed** and documented in code: the
  `negotiate` default-instructions bug (fixed 2026-08-09, `realtime.py:297`); the
  `release()`-consumes-activation-on-dead-connection bug (fixed 2026-09-06,
  `alert_lifecycle_events.py`, `PROJECT_STATE.md`); the
  `assistantSpeaking`-flips-on-`response.done` phantom-transcript bug (fixed,
  `realtimeMessageHandler.js`).
- `alert_id` lifecycle is consistent: one incident = one id for its life; repeat
  presses / second mapped source coalesce; a press after a genuine staff close opens
  a new id (`test_resident_events.py`).
- Working tree on `claude/resident-baselines` is clean; HEAD == `origin/main` ==
  `d994331`.
- DB collection inventory as listed in §2.15.

### 12.2 INFERRED BUT NOT YET PROVEN

- The live "43-press" Room 214 event (from `PROJECT_STATE.md`) is **almost certainly**
  frame-inflated (a handful of physical presses), given §5.A — but this was inferred
  from the mechanism, not verified against the actual `presses[]` timestamps in the
  live DB.
- `rtl_433 -M level` **may** also emit `snr`/`noise` per record; `RFFingerprint` only
  persists `rssi` (+ free-form `decoded`), so per-frame SNR is **probably** not stored
  — not confirmed by inspecting real `db.rf_events` documents.
- The 5 rapid `_press()` calls in `test_resident_events.py` **would** collapse under a
  ~2 s same-fingerprint window (they're sequential localhost POSTs, ~ms apart) — high
  confidence from reading the test, but not executed with a collapse in place.
- The exact `part_of_day` boundaries residents/staff would find natural
  (bedtime vs evening, overnight start) are a guess pending Michael's input.
- Whether opening a second unprocessed `getUserMedia` track for a measurement tap is
  reliable across the actual kiosk hardware/OS is unverified (no device test done).
- `AriaVoiceSession` appears operator-only from its `owner_user_id` field and call
  sites; a resident-session summary writer was **not** found, but the full realtime
  session-teardown path was not exhaustively traced.
- Pilot resident identities/behaviour profiles in the **live** DB were not read
  (residents endpoint is auth-gated); seed data was read instead.

### 12.3 PROPOSED / NEEDS MICHAEL'S DECISION

- **Decision A — frame collapse:** Option 1 (fix in `record_resident_activation`,
  update 2 tests), Option 2 (derive `human_press_count` in Layer 1 only, live path
  untouched), or Option 3 (defer). Report recommends Option 1, Option 2 as safe
  fallback. **Not acted on.**
- **Decision B — audio telemetry scope:** timing/derivable metrics now with nullable
  speech-level fields + audio-level as a named follow-up lane (recommended), **or**
  build the `AnalyserNode` sampler + AGC handling + `/api/room-audio/sample` +
  `db.room_audio_samples` in this same pass. **Not acted on.**
- The entire three-layer design in §6 (collections `db.resident_observations`,
  `db.resident_baselines`, `db.resident_deviations`; the five new backend modules;
  the config module vs folding into `ResidentAssistanceConfig`).
- Maturity thresholds (`insufficient <3`, `preliminary 3–6`, `establishing 7–14`,
  `established 15+`) and the `establishing` floor for emitting `notable` deviations.
- `part_of_day` bucket boundaries; whether weekday/weekend enters now or later.
- Deviation classification constants (`deviation_notable_ratio ≈ 2`,
  `deviation_prominent_count = 2`) and the exact `spread_score` formula.
- Whether `db.events` (`CaosEvent`) should be the resident telemetry spine instead of
  a purpose-built `db.resident_observations`.
- The "What Changed?" view (§7): new `WhatChanged.jsx` alongside the existing
  `Insights.jsx` (kept), tab registration, drill-down via `AlertDetailDialog.jsx`.
- The banned-phrase list contents for the no-medical-language guard.
- Whether the `_close_out()` hook adds 2 lines to `alerts.py` directly or via a
  single-import indirection.
- Data-retention policy for `db.room_audio_samples` (if Decision B includes it) —
  proposed TTL 30–90 days on raw windows, per-event median kept long-term.

---

*End of report. No code changed. No decision made. Awaiting review.*
