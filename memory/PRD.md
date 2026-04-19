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

### Iteration 1
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
- Build the actual daily-haiku generator (Claude cron)
- Move SECRETS_CACHE to Redis (survives server restart)
- Rate-limit `/api/family-portal/{token}/summary` (60 req/min per token)
- Unique index on `wearables.mac_address`
- Install Android bridge on a real tablet with a chosen RF receiver
- Enable `DEVICE_AUTH_REQUIRED=true` once all field devices are issued tokens

### P2
- AI-vision glasses/earbuds — real-time walking guidance for low-vision residents
- Floor-plan heatmap of live resident positions
- Fall detection via pendant accelerometer
- Multi-language (Spanish first)
- Medication reminders via kiosk voice

## Next Tasks
- Provide Twilio + Resend keys → notifications go live immediately
- Pick the AI-vision glasses hardware platform (Meta Ray-Bans / XREAL / Vuzix M400) when ready for P2
- Run a pilot at your first facility
