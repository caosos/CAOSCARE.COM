# CAOS Care — Product Requirements Document

## Original Problem Statement
CAOS Care is an AI-powered adjunct to the existing 900 MHz Life-Alert style pendant systems
used in senior living communities. Today those pendants only track to the room. CAOS Care
adds a wall-mounted tablet kiosk per room that (a) lets residents — many of whom are blind or
low-vision — press one big button to page staff, (b) holds a calming voice conversation with
them until staff arrive, and (c) reports zone-level location using the building's existing mesh.
A staff dashboard receives alerts + live locations. Future: AI-vision glasses/earbuds to guide
residents who are walking.

## User Personas
- **Resident (primary)**: 75+, often visually impaired, anxious when alone, needs reassurance. Kiosk is voice-first with one massive button.
- **Caregiver / Nurse**: triages alerts on a tablet, needs to know who is paging, from where, and how urgent.
- **Admin**: manages residents, staff accounts, kiosks, and building zones.

## Architecture
- **Backend**: FastAPI + MongoDB (motor). Routers under `/api`: `auth`, `residents`, `staff`, `kiosks`+`zones`, `alerts`, `locations`, `ai`.
- **Frontend**: React 19 + Tailwind + shadcn/ui. Outfit + Manrope fonts. Forest-green / bone-white / terracotta palette.
- **AI**: Claude Sonnet 4.5 (via emergentintegrations) for chat, OpenAI Whisper-1 for STT, OpenAI `tts-1` (voice: sage) for TTS. Single Emergent Universal LLM key.
- **Auth**: JWT email/password + Emergent-managed Google Social Login. Seed creates admin + nurse demo accounts.
- **Location tracking**: public POST `/api/locations` endpoint ready for real mesh sensors; `POST /api/locations/mock/generate` for demo.

## Implemented (Feb 2026)
- Landing page with hero, feature grid, and split image
- Resident Kiosk at `/kiosk/:kioskId` (and `/kiosk/demo`) — public, huge emergency button, voice AI companion with hold-to-talk mic and spoken replies, auto-escalation on emergency language
- Staff Dashboard at `/staff` — live alert feed (3s polling), color-coded severity, acknowledge + resolve, stats tiles, live location panel, mock-simulation button
- Admin Panel at `/admin` — 4-tab CRUD (residents, staff, kiosks, zones), role-gated
- JWT login/register + Emergent Google Social Login + seeded demo credentials
- Claude Sonnet 4.5 chat with resident context injection + history persistence
- OpenAI TTS (tts-1, voice=sage) + Whisper STT upload endpoint
- Building-wide location tracking (real ingest + mock generator + latest-per-resident)
- Seed data: admin, nurse, 6 residents, 4 zones, 6 kiosks (1 per room)
- Alert auto-linking: kiosk → room → resident → latest zone
- AI triage detecting emergency keywords → auto-escalates to emergency alert

## Prioritized Backlog (P0 / P1 / P2)
### P0 — foundational & safety
- None open. Testing passes 32/32 backend + ~95% frontend.

### P1 — next iteration
- Cascade delete: removing a resident should also wipe their locations + chat history
- HMAC / device-token auth on `POST /api/locations` (real sensors need it)
- Rate-limit public `POST /api/alerts` to prevent abuse
- Staff pager SMS integration (Twilio) — real paging, not just dashboard notifications
- Kiosk PIN / tamper lock so residents can't accidentally navigate away
- Push notifications for mobile staff tablets (web-push)

### P2 — future phases
- AI-vision glasses/earbuds integration (real-time walking guidance)
- Floor-plan heatmap of live resident positions
- Family portal (with resident consent) to view comfort-chat highlights + location
- Fall detection via pendant accelerometer signal
- Medication-reminder prompts delivered through the kiosk voice
- Multi-language support (Spanish first)

## Next Tasks
- Hook a real SMS pager integration (Twilio) once you provide account SID + auth token
- Add HMAC guard on the public locations ingest endpoint before shipping to a real site
- Wire a production MongoDB connection string + backup policy
