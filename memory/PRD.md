# CAOS Care — Product Requirements Document

## Original Problem Statement
CAOS Care is an AI-powered adjunct to existing 900 MHz Life-Alert-style pendant systems in senior living communities. Wall-mounted Android kiosks with plug-in USB RF receivers listen to each pendant's unique frequency → identifies that resident → pages staff → personalized AI companion speaks to the resident while help arrives. Staff dashboard + admin + family portal + geofencing + predictive insights + wearable ingest — all on top of the infrastructure the facility already owns.

## Architecture
- **Backend**: FastAPI + MongoDB (motor). 13 routers under `/api`: auth, residents, staff, kiosks/zones, alerts, locations, ai, pendants, wearables, roadmap, insights, notifications + family-contacts, device-tokens, family-portal.
- **Frontend**: React 19 + Tailwind + shadcn/ui. Outfit + Manrope fonts. Forest-green / bone-white / terracotta palette.
- **AI**: Claude Sonnet 4.5 per-resident personalization + OpenAI Whisper-1 STT + OpenAI tts-1 (sage voice). Single Emergent Universal LLM key.
- **Hardware**: Android tablet + USB RF receiver → bridge app → `POST /api/pendants/event`; wearable companion apps → `POST /api/wearables/event`; mesh sensors → `POST /api/locations`. All three can be HMAC-signed via the device-token system.
- **Notifications**: Twilio SMS + Resend email, log-only until keys in .env, activate automatically.

## Implemented (Feb 2026)

### Iteration 18 (Feb 2026) — Attribution discipline (no false "you mentioned it")
After a transcript caught CAOS volunteering "let's talk about your years teaching in Boston" out of nowhere AND then lying about the source ("you've mentioned it before") when Margaret challenged it. Root cause: Margaret's seed `memory` field literally said *"She loves when you ask about her years as a schoolteacher in Boston"* — the model read that as an instruction to bring it up, then couldn't distinguish seed knowledge from session knowledge.
- **Reframed seed as "Intake notes from family/staff"** in `_build_companion_instructions` — `r.get("preferences")` and `r.get("memory")` now render under a section explicitly labeled "(NOT from {name})" with rules: treat as private context only, never volunteer as topics, never claim the resident told you.
- **New `## Attribution discipline` block** — explicit rule that if asked "how do you know that?", CAOS must answer truthfully based on source: family intake → "your family shared that when you arrived"; previous session → "you mentioned it on a recent call" (only if real); current call → "you just told me a moment ago". NEVER fabricate "you mentioned it before."
- **Added Boston wrong/right example** to the memory-as-filler rule: silence falls → CAOS must NOT raise a pre-loaded topic; instead stays quiet or asks an open question that doesn't reference any seed fact.
- Verified: 7/7 prompt checks pass (intake reframing, NOT-from-Margaret marker, attribution section, Boston example present, never-claim-you-mentioned rule, family-source attribution, seed still accessible as context). Prompt size ~13.6k chars.

### Iteration 17 (Feb 2026) — Honest capability claims (no over-promising)
After a transcript caught CAOS promising "live news, sports, recipes" then failing when Margaret asked for today's news, fixed `_system_self_knowledge()` to ground its capability list in actual env config. With `PERPLEXITY_API_KEY` empty, the prompt now says "I don't have live web access — I can recall general knowledge, prayers, scripture, jokes" and instructs the AI to say "I don't have today's news with me, but I can tell you what I remember." Auto-flips to live-mode wording when the key is added. Added explicit `## NEVER over-promise` rule covering capabilities not in the toolset (calling family on video, sending texts, playing music): respond "That's not something I can do yet, but I'll let the team know you asked." Verified both states with programmatic checks.

### Iteration 16 (Feb 2026) — Self-aware CAOS + Realtime memory growth
After a live transcript showed CAOS dodging the question "what does CAOS stand for" with "something technical" AND nothing said over WebRTC voice ever reaching the memory store, two surgical fixes:
- **Platform self-knowledge block** in `realtime.py::_system_self_knowledge()` — every Realtime session now begins with the canonical brand stack (CARE = Compassionate Adaptive Resident Engagement; CAOS = Cognitive Adaptive Operating System; mission "Create A Resident Experience"), an inventory of every kiosk button (Call for Help / I need a little help / I just want to talk / Voice picker / A++ text / HC contrast / smart-room tiles), the hardware stack, and a plain-English capability list. Pulled from `/app/memory/PRD_HUB_v1.md` + Blueprint page so the source of truth is one file. CAOS can now answer "what does CAOS stand for", "what's that red button", "who made you", "what can you do" without dodging.
- **Realtime → memory pipeline wired** — new public `POST /api/memory/realtime-turn` endpoint persists each closed turn into `db.conversations` AND fires the existing Haiku 4.5 background extractor (`extract_and_store_memories`). Frontend `useRealtimeVoice.js` posts the pair the moment the assistant transcript closes (`response.audio_transcript.done`), pairing it with the buffered user transcript. Each session gets a stable `session_id` so future calls can replay context. Verified live: a single Realtime turn ("I love being out on the river or the lake") generated 2 new `facts`-bin memories ("Loves being out on the river or the lake", "Enjoys the sun on the water"). This is the single change that turns CAOS from "warm but static" into "grows warmer with every conversation."
- **Prompt size**: ~11.1k chars (was ~8k). Still well under the Realtime context budget.

### Iteration 15 (Feb 2026) — Listening discipline: name correction, end-call, memory-as-reference
After a live pilot transcript revealed CAOS still saying "Maggie" after the resident said "my name is Margaret, not Maggie", volunteering "Frank" as a non-sequitur memory filler, and refusing to hang up when asked to end the call, three surgical fixes:
- **`update_preferred_name` tool + `PATCH /api/residents/{id}/preferred-name`** (public, no auth — invoked mid-call). When the resident corrects what CAOS calls them, the model now persists the correction to the DB so it sticks across sessions. Validates 1-60 chars.
- **`end_call` tool** that actually tears down the WebRTC peer connection. Distinct from `mark_resting` (go quiet, stay connected): `end_call` plays one short goodbye via `response.create`, then `setTimeout(2500ms)` calls `stop()` + the parent's `onEndCall` callback so the kiosk returns to idle. Triggered by "end the call", "hang up", "goodbye", "I'm done", "that's all".
- **Prompt rewrite — "Memory is reference, not filler"**: explicit good-vs-bad example showing the model that bringing up Frank as a non-sequitur after a name correction is wrong. Memories now only surface when the resident's MOST RECENT words clearly invite them. Adds "fix it instantly" rule: any correction is accepted immediately with one short apology, never repeated.
- **Realtime session now ships 11 tools** (was 9): adds `update_preferred_name` + `end_call`.
- **Margaret's seed corrected**: `preferred_name` updated from "Maggie" to "Margaret" via the new endpoint to fix the demo data immediately.

### Iteration 14 (Feb 2026) — Companion superpowers: research, weather, time, timers, storyteller mode
- **Live web research tool** (`POST /api/research`) — Perplexity Sonar primary (live web + citations), Claude Sonnet 4.5 fallback (training-data, no web) when `PERPLEXITY_API_KEY` is empty. Tool-shaped for spoken delivery: 2-4 short sentences, no bullets, sources mentioned naturally ("the AP says…"). When the resident asks about current events, sports scores, recipes, history, prayers, anything — CAOS calls the tool instead of guessing. Both providers wrapped behind `research_topic(question) -> {answer, citations[], source}`.
- **Weather tool** (`GET /api/weather/current`) — Open-Meteo (no API key required) with free Open-Meteo geocoding so "what's the weather in Boston where my daughter lives?" actually resolves to Boston coords, not just relabels the facility's number. Returns a single spoken-friendly `narrative` line. Defaults to `FACILITY_LAT`/`FACILITY_LON`/`FACILITY_LABEL`/`FACILITY_TZ` from `.env` (currently Lancaster, PA — owner can change without code).
- **Time-of-day awareness** — `_facility_now()` injects `## Right now` block into every Realtime session prompt: weekday, date, local time, part-of-day. Fixes the "good morning at 7pm" bug. Frontend `get_current_time` tool synthesizes a fresh value client-side from the `facility_tz` context for long calls.
- **One-shot timers** (`/api/timers/*`) — public `POST /timers/public` (called by AI mid-call), public `GET /timers/due/by-room/{room}` polled by the kiosk every 60s (atomic find-and-mark-fired). Authed list/delete for admin. Validation: 0.1 ≤ minutes ≤ 720 (12h max).
- **Storyteller / Alexa+ prompt mode** — new prompt block: "Alexa reads canned answers. You are a companion." When tool returns research, CAOS re-tells in plain English ("So apparently…", "From what I'm reading…") rather than reciting. When the resident is bored, lonely, or in pain waiting for help, CAOS proactively offers stories, jokes, prayers, hymns, or family-memory conversation.
- **Realtime session now ships 9 tools** (was 5): `adjust_room_temperature`, `toggle_light`, `toggle_tv`, `call_for_help`, `mark_resting`, `get_current_time`, `get_weather`, `research_topic`, `set_timer`.
- **Tests**: 19/19 pytest in `iter11_test.py` — research with Claude fallback, weather with city-name geocode, timer fire-and-mark idempotency, all 9 tools present in session config, time anchor + storyteller block in instructions, full backend regressions (auth, residents, alerts, devices). Latency note: Claude fallback ~5-8s on cold call (acceptable for one-shot lookup; will drop to ~2s once Perplexity key lands).

### Iteration 13 (Feb 2026) — Realtime tools, anti-hallucination, VAD timing
- **OpenAI Realtime tool calling fully wired** — five function tools live in `routes/realtime.py::_build_tools()`: `adjust_room_temperature` (target_f 60-85, mode), `toggle_light` (on/off + optional brightness), `toggle_tv` (on/off + optional volume), `call_for_help` (severity assist/emergency, paged via `POST /api/alerts` with `triggered_by="ai_triage"`), `mark_resting` (resident-driven silence). Frontend `useRealtimeVoice.js` intercepts `response.function_call_arguments.done`, translates each tool's human args into the backend's `DeviceCommandInput.action` enum (`power | temperature | brightness | volume | …`), POSTs to `/api/devices/public/room/{room}/command`, then sends `conversation.item.create` (function_call_output) + `response.create` so CAOS speaks its short confirmation. Mismatches between tool names and the device-action enum were caught by the testing agent and fixed before ship.
- **Anti-hallucination prompt rewrite** — `_build_companion_instructions()` now carries a "Truth discipline" block forbidding invented memories, places, or shared history, plus an explicit empty-bin fallback ("No facts on file yet — ask gently and remember"). Hard name-discipline rule pins the resident's preferred name ("ALWAYS call them X — never any other variant") to fix the Margaret↔Maggie drift the pilot exposed. Empty-history residents now get an explicit "this is the start of your history together" instruction instead of fabricating one.
- **Server-side VAD tuned for senior speech** — `turn_detection.silence_duration_ms` raised 500 → **1000ms** (with 300ms prefix padding) so older voices can pause mid-thought without being interrupted. Sampling temperature locked to **0.6** (Realtime API floor) for maximum factuality.
- **Kiosk 401 fix** — new public endpoint `GET /api/alerts/public/{alert_id}/status` returns minimal `{alert_id, status, severity}` (no PII). Replaces the authed `GET /api/alerts/{id}` poll the kiosk was hitting unauthenticated. Legacy authed route still requires JWT.
- **Tests**: 14/14 pytest in `/app/backend/tests/iter10_test.py` — session config (5 tools, VAD 1000ms, temp 0.6, instructions guards), public alert lifecycle (active → resolved), full regression on auth + residents + alert feed/stats. Voice quality / VAD feel / function-call execution requires manual user verification (WebRTC audio not automatable).

### Iteration 12 (Feb 2026) — Owner tier + Blueprint + two-bin memory
- **Three-tier role hierarchy**: `owner` > `admin` > `staff`. `User.role` literal expanded; `/admin-login` now accepts both `owner` and `admin`. First Google sign-up is promoted to `owner` (was `admin`). Seeded accounts: `owner@caoscare.com / owner1234`, `admin@caoscare.com / admin1234` (now labelled "Admin Nurse"), `nurse@caoscare.com / nurse1234`.
- **Owner-only `/admin/blueprint` page** (`pages/Blueprint.jsx`): single-source vision document — philosophy, role tiers, memory architecture, live bulletin, hardware stack, AI layers, clinician registry, family/compliance, what's next. Owner sees a terracotta "Blueprint" button in the admin header; admins and staff do not. Attempts by non-owners to hit the route are redirected to `/admin`.
- **Memory two-bin model**: `ResidentMemory` gained `bin: "facts" | "events"`, `event_at`, and `archived` fields. `default_bin_for_category()` maps `family/preferences/health/history/daily_pattern/relationship → facts`, `concern/milestone/other → events`. Bin is auto-derived on create or extraction if not specified. Legacy rows migrated via `POST /api/memory/backfill-bins` (owner-only, idempotent) — 37 existing memories migrated in place.
- **Rolling window raised 40 → 500 turns**. Claude Sonnet 4.5 has plenty of context headroom; the previous cap was truncating rich conversations before the dehydration pipeline could extract them. Session-scoping still prevents cross-event bleed.
- **Hydration splits bins**: `build_memory_context()` now injects `PERSONAL FACTS (durable identity)` + `LIFE EVENTS (dated moments, newest first)` as two separate blocks in the system prompt, with up to 40 facts and 25 events.
- **Owner-only bulletin endpoint**: `GET /api/memory/bulletin/{resident_id}` returns `{resident, facts[], events[], conversation_turns, rolling_window}` — consumed by the Blueprint page's live bulletin column view.
- **Tests**: Owner login OK, admin gated out of `/admin/blueprint` + `/api/memory/bulletin/*` (403 / redirect), live bulletin renders 29 facts + 2 events for Dorothy Walsh.


### Iteration 11 (Feb 2026) — Voice briefing + kiosk accessibility
- **Nurse voice briefing** (`GET /api/residents/{id}/briefing`): returns structured payload (thresholds, active alert count, pinned memories, last zone, last seen) plus a pre-composed natural-language `narrative` line. Admin → Residents now has a **Brief** button per row that fetches the narrative, pipes it through the existing OpenAI TTS endpoint, and plays it in the browser. Useful for shift-change hand-offs — "Dorothy Walsh, room 204. Clinical bands: resting heart rate band 55 to 105, exertion ceiling 135, oxygen floor 92 percent. Note: chronic afib…"
- **Kiosk accessibility toggles** (per-kiosk, persisted via localStorage): (1) text-size cycle A / A+ / A++ scales the idle screen's hello / prompt / emergency / assist buttons, (2) high-contrast mode flips the entire kiosk to amber-on-black (#FFC857 on #000, WCAG-AAA) and swaps the emergency button to yellow-on-black for low-vision residents with cataracts or retinopathy.
- **Tests**: briefing narrative verified with and without thresholds; a11y CSS classes render correctly (baseline + A++/HC-on screenshots captured).

### Iteration 10 (Feb 2026) — Pilot-hardening: per-resident thresholds, admin-login split, Haiku extractor
- **Per-resident clinical thresholds**: New `ClinicalThresholds` sub-model on `Resident` with `hr_resting_min/max`, `hr_exertion_max`, `spo2_min`, `inactivity_minutes`, and `notes`. All fields optional, `ge/le` bounded. Admin → Residents → Edit dialog exposes a "Clinical thresholds" section (testids `res-hr-min`/`res-hr-max`/`res-hr-exert`/`res-spo2`/`res-inactivity`/`res-ct-notes`) with "NOT DIAGNOSTIC" caveat and plain-language helper copy. Blank-all persists as `null`.
- **Wearable event threshold re-evaluation** (`routes/wearables.py`): when `heart_rate` is present and the resident has thresholds, the backend re-maps the wearable-reported event. Generic `heart_rate_high` inside the resident's personal band → suppressed (returns `alert:null` + `suppressed_event` field). Silent `periodic_ping` above `hr_exertion_max` or outside the resting band → upgraded to `heart_rate_high`/`heart_rate_low` and flagged in the alert message. Residents without thresholds behave identically to before.
- **Separate `/admin-login` route**: New branded FastAPI endpoint `POST /api/auth/admin-login` + React page `/admin-login`. Admin happy path = 200 + JWT; staff credentials = 403 + clear "These are staff credentials" message (no lockout increment); wrong password = 401 + lockout increment. In-memory throttle: 5 failed attempts per `(ip, email)` within 15 min → 429 (IP read from `x-forwarded-for` first, then `request.client.host`). Constant-time bcrypt via dummy hash prevents user enumeration. Login page's demo credentials block updated to show only staff creds + a subtle "Administrator sign-in →" link. `AuthContext.loginAdmin()` added.
- **Memory extractor model swap**: `/api/memory/extract` and the background extraction task now use `claude-haiku-4-5-20251001` instead of Sonnet 4.5. Same structured-JSON output, a fraction of the per-turn cost. Verified live — two i5 family-category memories extracted from a test exchange.
- **Tests**: 14/14 new backend pytests (admin throttle, threshold re-map suppress/upgrade, Haiku live-call) + UI happy-path verified (admin redirect, threshold editor persistence).

### Iteration 9 (Feb 2026) — Python-backed lifelong memory server
Landing, Kiosk, Staff Dashboard, Admin, JWT + Google Auth, Claude chat + TTS/STT, location tracking, alert lifecycle.

### Iteration 2
Pendant registry + RF ingest, per-resident AI personalization (preferred_name/preferences/memory), escalation timers (60s/3m/7m), event close-out + timeline, roadmap tracker.

### Iteration 3
Wander / geofencing (restricted zones auto-alert), movement timeline per resident, Phase 4 insights (help_requests / nighttime_activity / mobility), family contacts + NotificationService (Twilio/Resend stubs), Android bridge Kotlin scaffold.

### Iteration 4 (this iteration)
- **Wearable support**: generic `POST /api/wearables/event` for smartwatch / earbuds / glasses / BLE beacons. Supports press / fall / heart_rate_high / heart_rate_low / inactivity / periodic_ping. Admin CRUD with pair-to-resident. Simulate-event dialog. Alerts tagged `triggered_by="wearable"`.
- **Bathroom-frequency drift** (Phase 4): zones have `is_bathroom` flag; insights add `bathroom_frequency_7d` metric comparing last 7d vs prior 7d bathroom-zone pings. Non-diagnostic phrasing. 2 bathroom zones seeded.
- **HMAC device-token auth**: admin creates named tokens with scopes (pendants.event / locations.ingest / wearables.event). Backend returns shared secret ONCE, stores bcrypt hash + keeps plaintext in in-memory SECRETS_CACHE for live HMAC verification. Field devices send `X-Device-Token` + `X-Device-Signature: HMAC-SHA256(secret, body)`. Soft-enforced by default; flip `DEVICE_AUTH_REQUIRED=true` to reject unsigned. Admin tab shows enforcement status + active/revoked counts + copyable token id + secret reveal dialog.
- **Family portal**: every `FamilyContact` gets a `portal_token`; public route `/family/{token}` renders a calm resident-status page (last seen, active calls, resolved 7d, recent alert summaries, optional haiku) with "I've checked in" ack button. Privacy-respectful: no medical detail, no chat content. Copy-link button in Admin → Family.
- **Roadmap shipped**: Phase 1 5/5 ✅, Phase 2 6/6 ✅, Phase 3 8/8 ✅, Phase 4 6/6 ✅, Cross-cutting 7/10 ✅. Only open items: Twilio/Resend keys pending, AI-vision glasses (future hardware), daily haiku digest generator (cron-style, not yet wired).
- **Tests**: 80/80 backend + 100% frontend. HMAC round-trip verified (valid sig → 200, invalid sig → 401).

### Iteration 9 (Feb 2026) — Python-backed lifelong memory server
- **db.conversations** — every chat turn logged per resident. Last 40 turns flattened into a transcript block in Claude's system prompt so the AI picks up mid-conversation across sessions, across days.
- **db.memories** — discrete learned facts. Fields: `text`, `category` (family/preferences/health/history/daily_pattern/concern/relationship/milestone/other), `importance` 1-5, `pinned`, `source` (extraction/chat/admin/staff/family), `times_referenced`, `last_referenced_at`. Pinned memories always in context.
- **Auto-extraction**: after each AI reply, `asyncio.create_task` fires a background Claude call that reads the exchange, proposes new memory rows, dedupes by prefix, stores with `source="extraction"`. Best-effort — never blocks the response.
- **Admin UI**: per-resident **Memory** button on ResidentsTab → `MemoryDialog` with two tabs. Memories tab: CRUD, pin/unpin, set importance via 5-dot widget, manual "Teach CAOS something" form. Conversation tab: full chronological transcript.
- **Verified across sessions**: turn 1 in session A teaches CAOS a fact → turn 2 in session B (same resident) recalls it. `memories_used` + `history_replayed` exposed in `/api/ai/chat` response.
- **Tests**: 13/13 backend + full frontend E2E, zero critical issues.

### Iteration 1
- **Hands-free voice conversation on every pendant press**: removed the ≥2-press requirement for `auto_voice`. Any pendant press (single, panic, or fall) and any wearable press/fall now sets `auto_voice=true` so the in-room kiosk opens a continuous voice conversation. Severity escalation (assist → emergency) still happens on 2+ presses in 60s.
- **Continuous voice loop** (`Kiosk.jsx`): AI speaks → short 880Hz beep cue → kiosk records up to 8s → Whisper STT → Claude reply → TTS → next iteration. Exits on (a) resident exit phrases like "I'm fine" / "never mind" / "that's all", (b) staff resolving the alert (kiosk detects via 4s polling, says "A caregiver is with you now — I'll step back."), or (c) Never mind button.
- **Kiosk-button press** also runs through the same continuous voice loop — no "Hold to talk" required for blind residents.
- **Visual indicator** for sighted users + audible beep before each listen for blind residents.
- **Tests**: 8/8 new backend, zero regressions.

### Iteration 6 (Feb 2026)
- **Daily haiku generator**: `POST /api/haiku/generate-today` (admin) runs Claude Sonnet 4.5 per resident using their preferences+memory → 3-line warm bedtime haiku stored in `db.haikus`. Idempotent per `{resident_id, day}`. Family portal already renders latest haiku. Admin → Family → "Generate tonight's haikus" button.
- **Pager RF emulation**: `/api/paging/event` (public, HMAC-optional) ingests from the facility's existing paging transmitter. Cap-code enrichment maps pendant_id → resident. `/api/paging/feed` (auth) returns last-30min events. Every staff tablet shows a live "Facility pages" card on the StaffDashboard rail; admin can also push `/api/paging/simulate`.
- **Medication reminder voice**: `MedReminder` CRUD with `time_hhmm` + days-of-week. Kiosk polls `/api/medications/due/by-room/{room}` every 60s when idle; speaks reminder at the exact minute, POSTs `/api/medications/ack/{reminder_id}` so it doesn't repeat within the day. Admin → Meds tab.
- **Floor-plan heatmap**: Admin → Map shows a simple 2-floor SVG with each resident as a dot at their most-recent mesh/pendant ping. Restricted zones in red. Refreshes every 5s. Ready to be swapped for a real CAD export per facility.
- **Tests**: 12/12 new backend + full frontend verification, zero issues. Cumulative ~100 backend tests green.

### Iteration 5 (Feb 2026)
- **Smart-room devices**: Full CRUD at Admin → Smart devices (BLE / WiFi / RF_433 / RF_915 / IR / Zigbee / Matter). Public kiosk endpoint `/api/devices/public/by-room/{room}` + `/api/devices/public/room/{room}/command`. Kiosk renders huge tap-on/tap-off buttons for lights / fan / heater / TV on the idle screen. Command queue for the per-room Android bridge to execute over BLE/WiFi/RF.
- **AI vision scaffold**: `/app/android-vision/` Kotlin app for Vuzix M400/M4000 (CameraX + OkHttp + MediaPlayer). Streams JPEG frames every 4s to `/api/vision/describe`, plays back TTS. Personalization via resident_id. Ready for hardware.
- **Panic-press → hands-free voice** (safety-critical): 2+ pendant presses within 60s (or a fall event) upgrades the alert to `severity=emergency` + `auto_voice=true`. Kiosk polls `/api/kiosks/{id}/active-emergency` every 3s. On hit, kiosk speaks *"I'm here, \<name\>. Help is on the way — tell me what's happening."*, opens mic automatically for a 6s window, streams to Whisper. Resident never has to touch the screen.
- **Central nurse-station kiosk**: Kiosks gain an `is_central` flag. Central kiosks listen for ANY facility-wide emergency (not just room/zone). Seeded 1 central station. Admin → Kiosks has a toggle.
- **Staff task management**: New `/api/tasks` routes + `StaffTask` / `StaffTaskTemplate` models. Admin creates daily templates (meds, meal, rounds, laundry, bathing, activity) → `POST /api/tasks/spawn-today` materializes one task per template per day. Staff taps Start → `in_progress` + `started_at`; taps Complete with optional notes → `completed` + `completed_at` + `duration_minutes` + `completed_by`. Audit trail = full. Admin → Tasks shows today's board + templates. StaffDashboard has "My tasks today" card with Start/Complete.
- **Backend test coverage**: panic-press detection + central kiosk query verified end-to-end via curl; task start→complete round-trip verified.

## Backlog

### P1
- Drop real Twilio + Resend keys into `backend/.env`
- Move admin-login throttle + SECRETS_CACHE to Redis (survive restart + multi-worker coordination)
- Memory consolidation / redaction endpoint ("forgetting" authority domain — dementia, consent revocation, staff departure)
- Rate-limit `/api/family-portal/{token}/summary` (60 req/min per token) — already shipped
- Unique index on `wearables.mac_address`
- Install Android bridge on a real tablet with a chosen RF receiver
- Enable `DEVICE_AUTH_REQUIRED=true` once all field devices are issued tokens

### P2
- HR trend charts per resident (Recharts) tied to `clinical_thresholds` bands
- Escalation loop: unacknowledged alert → on-call rotation → Twilio/Resend once keys land
- Photo upload per resident
- AI-vision glasses/earbuds — real-time walking guidance for low-vision residents
- Fall detection via pendant accelerometer
- Multi-language (Spanish first)
- Magnetic recliner-charger R&D for "wearables for everyone" (hardware — no code)

## Next Tasks
- Provide Twilio + Resend keys → notifications go live immediately
- Pick the AI-vision glasses hardware platform (Meta Ray-Bans / XREAL / Vuzix M400) when ready for P2
- Run a pilot at your first facility
