# CAOS Care — Product Requirements Document

## Original Problem Statement
CAOS Care is an AI-powered adjunct to the existing 900 MHz Life-Alert style pendant systems used in senior living communities. Today those pendants only track to the room. CAOS Care adds a wall-mounted Android tablet kiosk per room with a plug-in USB RF frequency receiver. The tablet hears the pendant (each pendant has its own frequency), identifies the resident, pages staff, and holds a calming voice conversation with the resident — personalized to that specific resident — until a caregiver arrives. Staff have their own dashboard; admins manage residents, staff, kiosks, zones, pendants, and the roadmap.

## User Personas
- **Resident (primary)**: 75+, often visually impaired, anxious when alone. Kiosk is voice-first with one huge button.
- **Caregiver / Nurse**: triages alerts on a tablet, needs live location + event timelines + close-out outcomes.
- **Admin**: manages residents (with AI personalization), staff, kiosks, zones, pendants, and the build roadmap.

## Architecture
- **Backend**: FastAPI + MongoDB (motor). Routers under `/api`: `auth`, `residents`, `staff`, `kiosks`+`zones`, `alerts`, `locations`, `ai`, `pendants`, `roadmap`.
- **Frontend**: React 19 + Tailwind + shadcn/ui. Outfit + Manrope fonts. Forest-green / bone-white / terracotta palette.
- **AI**: Claude Sonnet 4.5 (per-resident personalized prompts with preferred_name + preferences + memory), OpenAI Whisper-1 STT, OpenAI tts-1 (voice: sage). Single Emergent Universal LLM key.
- **Hardware hook**: Android tablet + USB RF receiver → bridge app POSTs `/api/pendants/event` with `{frequency_mhz, event_type, zone, signal_strength, battery_percent, device_token}`. Backend looks up pendant by frequency → identifies resident → creates alert.

## Implemented

### Iteration 1 (Feb 2026)
- Landing page, Kiosk (public), Staff Dashboard, Admin Panel, JWT + Google Auth
- Claude Sonnet 4.5 resident chat + OpenAI TTS/STT voice
- Location tracking (real ingest + mock generator + latest-per-resident)
- Alert lifecycle (create/ack/resolve)
- Seed: admin, nurse, 6 residents, 4 zones, 6 kiosks

### Iteration 2 (Feb 2026)
- **Pendant registry**: admin CRUD for pendants (frequency ↔ resident). 7 seeded.
- **RF event ingest**: public `POST /api/pendants/event` (for Android bridge app). Press → alert, fall → emergency alert, periodic_ping → location-only update.
- **Per-resident AI personalization**: residents now have `preferred_name`, `preferences`, `memory`, `participation_level`. Claude uses these in the system prompt so each AI is specific to that resident.
- **Escalation timers**: unacknowledged alerts auto-escalate on every feed poll (60s → Lv1, 3min → Lv2, 7min → Lv3) with color-differentiated badges.
- **Event close-out**: `POST /api/alerts/{id}/close` captures `outcome` + `close_notes`. `GET /api/alerts/{id}` returns full timeline + related chat.
- **Alert detail dialog** on the Staff dashboard with timeline + chat + close-out form.
- **Roadmap tab**: 34 seeded items across phases 1–5 with live status updates and per-item notes.
- **Unknown-pendant pings** logged to `pendant_unknown` for admin review.
- **Tests**: 46/46 backend pytest + full frontend Playwright flows passing.

## Backlog

### P1 — next iterations
- **Android bridge app** (Kotlin) that reads USB RF receiver and POSTs `/api/pendants/event`. Needs USB-HID / USB-serial driver + background service.
- **HMAC/device-token auth** on `/api/pendants/event` + `/api/locations` (production hardening).
- **Twilio SMS pager** integration for real staff paging on existing phones.
- **Family portal** (opt-in): `FamilyContact` per resident with notification scopes; event notifications via email (Resend) or SMS (Twilio).
- **Wander / geofencing**: restricted-zone breach detection + automatic alerts.
- **Movement timeline per resident**: visualize location history.

### P2 — Phase 4 / future
- Baseline behavior profiles (nightly rollups per resident)
- Nighttime activity drift detection, bathroom frequency change, mobility decline
- Confidence-scored risk flags ("Margaret's nighttime help requests up 3x this week")
- AI-vision glasses/earbuds integration for walking guidance
- Fall detection via pendant accelerometer signal
- Multi-language (Spanish first)
- Medication reminders through kiosk voice
- Floor-plan heatmap of live positions

## Next Tasks
- Keep marching down the Phase 3 (wander + geofencing) and Phase 4 (pattern detection) roadmap items, or build the Android bridge app once user is ready to commit to a hardware stack.
- Wire Twilio + Resend when the user provides credentials.
