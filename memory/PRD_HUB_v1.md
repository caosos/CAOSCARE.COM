# CAOS Care — PRD Hub v1
**Status: living spec · Last updated: Apr 25, 2026**

This is the canonical product brief that supersedes ad-hoc notes and snippets across past chats. It documents the brand, the architecture, and the Device Class doctrine that lets CAOS Care expand beyond "a tablet on a wall."

---

## 1. Brand stack (lock)

```
Create
A Resident Experience.

through
Compassionate Adaptive Resident Engagement

powered by a
Cognitive Adaptive Operating System
```

| Layer | Acronym | What it is |
|---|---|---|
| Tagline / promise | **CARE** | The resident-facing layer. Family hears this. |
| Engine / platform | **CAOS** | The cognitive operating system. Engineers and ODMs hear this. |

Where the stack appears (canonical):
- Kiosk welcome (idle screen)
- Landing page hero
- Admin login left panel
- Blueprint page hero
- Manufacturer pitch deck slide 1
- Family portal welcome (next phase)

---

## 2. Product split (two systems, one brand)

| System | Path | Scope |
|---|---|---|
| **CAOS Care kiosk + companion** | `/app/` | Room kiosk, AI voice loop, RF pendant pairing, Android Companion APK, family portal, clinician registry |
| **caos-care-node v1 (wearable + watch + facility node)** | [github.com/caosos/caos-care-node](https://github.com/caosos/caos-care-node) | Wi-Fi smartwatch + staff smartwatch + facility hub. v1 spec lives in `src/lib/blueprintContent.js` |

The two products **share the brand and the integration contract**, not the code. They communicate through a versioned API per `[INT-001]`.

---

## 3. Device Class doctrine (from canvas PRD)

CAOS Care must stop thinking *"tablet first."* It thinks:

```
Device Class
  → Capability Profile
    → Compatibility Probe
      → Hardware Receipt
        → Deployment Role
          → Admin Blueprint Stack
```

This unlocks support for:
- Cheap Android tablet
- Custom CAOS Care Hub (ODM)
- Screenless smart speaker node
- Linux receiver bridge
- Future wearable gateway
- Wall-mounted display terminal

The hard rule:

> **No marketplace claim counts. No "OTG supported" claim counts. No model-name assumption counts. Only a live hardware receipt proves deployment compatibility.**

That's what makes this commercially serious instead of hacky.

### Manufacturer pitch (clean phrase)

> We need an open Android or Linux-based smart voice terminal with far-field microphones, good speaker quality, haptic feedback (body-worn only), USB host support, Wi-Fi/Bluetooth, and a custom boot-to-kiosk application flow.

Manufacturers do not need to know the full CAOS vision yet. That sentence is enough to start ODM/OEM conversations.

---

## 4. Implementation phases

| Phase | What ships | Complexity |
|---|---|---|
| **P1 — Spec contract** | Data models, capability profile, probe endpoint, receipt schema, admin Hardware Receipts UI. No probes yet — just the contract. | ~80–120 credits |
| **P2 — Probes live** | Companion APK runs the probes (mic, speaker, USB host, OTG SDR detect, Wi-Fi/BT). Emits signed receipt. Admin UI shows pass/fail per capability. | ~60–100 credits |
| **P3 — Per-role auto-stack** | Each `deployment_role` ships a manifest. Assigning a role auto-installs the right services on the device. | ~80 credits |
| **P4 — ODM portal** | `caoscare.com/manufacturers` — vendor signs up, runs probes against pre-production hardware, gets a compatibility certificate before tooling ships. | ~120+ credits |

---

## 5. Status of v1 build (as of Apr 25, 2026)

### ✅ Shipped
- Three-tier roles (`owner` / `admin` / `staff`)
- Owner-only Blueprint at `/admin/blueprint`
- Two-bin memory model (Personal Facts + Life Events) w/ live bulletin
- Realtime full-duplex voice (OpenAI Realtime API) — kill-switched cleanly against legacy turn-based loop
- Kiosk persona (3,700-char system prompt with banned phrases, vision-impaired handling, memory hydration)
- RF pendant pairing system — listen-and-learn flow, vendor-agnostic, sub-GHz wideband
- Install wizard at `/admin/install/{kiosk_id}` with OS auto-detection
- Android Companion APK scaffold (Gradle/Kotlin/Compose, USB host, foreground service, QR provisioning, HMAC-signed events)
- Clinician event registry backend (auto-classification + per-resident stats)
- Per-resident clinical thresholds + wearable suppression
- Audit CSV exports (alerts, tasks, pages, medications)
- Family magic-link portal + nightly haiku
- Brand stack (CARE/CAOS) integrated across kiosk, landing, admin, blueprint

### 🚧 Active / next
- **Clinician Dashboard UI** — visualize `/api/residents/{id}/stats` (this session)
- **Memory bulletin CRUD** — pin/archive/edit inline (this session)
- **Device Class architecture** — `[INF-004]` Blueprint section, then P1 contract build

### ⏭ Backlog
- Tutorial video infrastructure (player + `/admin/help` hub + 6 embedded spots)
- APK rtl_433 NDK build (1–2 day NDK task)
- Twilio SMS paging (needs user keys)
- Resend email (needs user keys)
- Recharts HR trend bands per resident
- Auto-escalation for unacknowledged alerts (on-call rotation)
- Memory dehydration "sanitize" job (PII redaction on archived turns)
- Multi-tenancy (`facility_id` on every model)
- Vuzix M400 wayfinding loop
- Public marketing site expansion (`/devices/*`, `/setup/*`)

---

## 6. Operating principles

1. **Blueprint is the source of truth** — code follows the blueprint, never the other way.
2. **No section ships without validation and status lock.**
3. **Privacy by design** — Tier 1 PII never enters AI prompts or integration payloads.
4. **No marketplace claim counts** — only signed hardware receipts prove compatibility.
5. **CARE on top, CAOS underneath** — never expose the engine to family / residents.
6. **AI is confined** — companion AI only sees what it needs to see for the resident in front of it.
7. **Local fallback always active** — CAOS-platform unreachable does not degrade the care system.

---

## 7. Open questions for product owner

- Pricing model: per-room / per-resident / per-facility / freemium for first facility?
- Pilot strategy: one facility deep, or 3 facilities shallow?
- ODM partner shortlist: who's on the call list?
- Branding: trademark filings on CAOS Care, CARE, "Compassionate Adaptive Resident Engagement"?
