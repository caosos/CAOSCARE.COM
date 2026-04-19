# CAOS Care — Product Requirements Document

## Original Problem Statement
CAOS Care is an AI-powered adjunct to existing 900 MHz Life-Alert-style pendant systems in senior living communities. Today those pendants only track to the room. CAOS Care adds a wall-mounted Android tablet kiosk per room, a plug-in USB RF receiver that listens for pendant presses (each pendant = its own frequency → identifies a specific resident), a personalized AI companion for that resident, a staff dashboard, geofencing/wander alerts across the building-wide mesh, predictive insights, and family notifications — all on top of the infrastructure the facility already owns.

## Architecture
- **Backend**: FastAPI + MongoDB (motor). Routers under `/api`: `auth`, `residents`, `staff`, `kiosks`+`zones`, `alerts`, `locations`, `ai`, `pendants`, `roadmap`, `insights`, `notifications` + `family-contacts`.
- **Frontend**: React 19 + Tailwind + shadcn/ui. Outfit + Manrope fonts. Forest-green / bone-white / terracotta palette.
- **AI**: Claude Sonnet 4.5 (per-resident personalized system prompt with preferred_name + preferences + memory), OpenAI Whisper-1 STT, OpenAI tts-1 (voice: sage). Single Emergent Universal LLM key.
- **Hardware hook**: Android tablet + USB RF receiver → bridge app POSTs `/api/pendants/event` with `{frequency_mhz, event_type, zone, signal_strength, battery_percent}`. Backend looks up pendant → identifies resident → creates alert.
- **Notifications**: `NotificationService` with Twilio (SMS) + Resend (email) providers. Logs-only until keys are set in `.env`; activates automatically when they are.

## Implemented

### Iteration 1
Landing, Kiosk, Staff Dashboard, Admin, JWT + Google Auth, Claude chat + TTS/STT voice, location tracking, alert lifecycle, seed data.

### Iteration 2
Pendant registry + RF event ingest, per-resident AI personalization (preferred_name/preferences/memory/participation_level), escalation timers (60s → Lv1, 3m → Lv2, 7m → Lv3), event close-out with outcome + timeline, phase-build roadmap tracker (34 items).

### Iteration 3 (this iteration)
- **Geofencing**: zones have `is_restricted` flag; a restricted-zone entry auto-creates a `triggered_by="geofence"` alert (with duplicate-suppression via prev-zone check). 2 restricted zones seeded ("Staff Only — Medication Room", "Outside — Parking Lot").
- **Wander / elopement alerting**: same path as geofencing; alerts fan out to family contacts with `wander` in their notify_on list.
- **Movement timeline**: `GET /api/residents/{id}/movement?hours=N` returns zone-visit history with consecutive same-zone pings collapsed. UI: MovementDialog on each resident row (24h / 3d / 7d windows).
- **Pattern insights / Phase 4 seed**: `POST /api/insights/compute` rolls up per-resident `help_requests_7d`, `nighttime_activity_7d` (22:00–06:00), `mobility_7d` (distinct zones), comparing last 7 days to prior 7 days. Each observation has severity (info/watch/concern), confidence (scales with sample size), and capped deviation %. 13 insights auto-computed from seed data.
- **Family contacts + notifications**: `FamilyContact` per resident with notify_on scopes (emergency / assist / wander / daily_summary). Alert creation auto-fans out via SMS (Twilio) + Email (Resend); providers are stubs that log until keys are set in `backend/.env`. Admin "Family" tab manages contacts, shows provider status, shows notification log, supports "Send test".
- **Staff dashboard**: 5th tile "Pattern flags" linking to Insights.
- **Android bridge app scaffold** at `/app/android-bridge/` — Kotlin + usb-serial-for-android + OkHttp. Generic: any USB-serial device emitting JSON lines works (Arduino+RFM69, CP210x, FTDI, CH340). README + PROTOCOL.md + Gradle Kotlin DSL included.
- **Tests**: 62/62 backend + 100% frontend passing.

## Roadmap snapshot (from Admin → Roadmap tab, 34 items)
- Phase 1 (Core Pilot): 5/5 ✅
- Phase 2 (Workflow Visibility): 6/6 ✅
- Phase 3 (Location & Mobility): 7/8 ✅ (wearables still open)
- Phase 4 (Predictive Insight): 5/6 ✅ (bathroom-frequency drift still open)
- Cross-cutting infra: 6/10 (Android bridge / Twilio / Resend are in_progress awaiting hardware + keys; HMAC + family portal + vision glasses + in_progress)

## Backlog

### P1
- Wire real Twilio keys (SID / Auth Token / From number) → notifications go live
- Wire real Resend key → family email activates
- HMAC / device-token auth on `/api/pendants/event` + `/api/locations` (production hardening)
- Build + install the Android bridge app on a real tablet with a chosen RF receiver
- Wearable support (smartwatch button + location hints)
- Bathroom-frequency / location-drift Phase 4 insight

### P2
- Family portal (opt-in, resident-consent-based)
- AI-vision glasses/earbuds for walking guidance
- Floor-plan heatmap
- Multi-language
- Medication reminders via kiosk voice
- Fall detection via pendant accelerometer

## Next Tasks
- Install Android bridge on a physical tablet once RF receiver is chosen
- Drop Twilio + Resend keys into `backend/.env` and redeploy
- Pick wearable support (Garmin/Apple Watch/Fitbit) or bathroom-frequency Phase 4 next
