# Aria Capability Portfolio

Durable, machine-readable registry of every device/service/workflow/tool Aria
may control, per `commands/TERMINAL_5A_ARIA_CAPABILITY_PORTFOLIO.md`. This is
the source of truth Aria's tool routing must check before claiming to act —
Aria may never claim she can control a capability unless its `status` is
`verified_control` and the requested action is in `supported_actions`.

Do not erase or silently deprioritize entries when priorities change — flip
their `status` and update `current_blocker`/`next_step` instead.

## Storage

- `db.aria_capabilities` — one document per capability (model `AriaCapability`
  in `backend/models.py`).
- `db.aria_capability_receipts` — append-only verification log (one document
  per `POST /api/capabilities/{id}/verify` call). Never edited or deleted;
  history survives even if a capability regresses.

Home Assistant entity state may populate individual capabilities' observed
state later, but Home Assistant is never the only durable record — this
Mongo-backed registry is CAOSCare-owned and covers non-home-automation
capabilities (voice, memory, host services) too.

## Lifecycle states

```
planned → discovered → configured → verified_read → verified_control
                                   ↘ blocked / offline
                                                       → retired
```

- `planned` — known to be wanted, nothing built yet.
- `discovered` — the target device/service/system has been found/inspected.
- `configured` — control path is wired up but unverified.
- `verified_read` — read/observe path proven working.
- `verified_control` — write/control action proven working; only status where
  Aria may actually act.
- `blocked` — known blocker prevents progress (see `current_blocker`).
- `offline` — was working, currently unreachable.
- `retired` — no longer relevant; kept for history, not deleted.

## Fields (`AriaCapability`, `backend/models.py`)

| Field | Meaning |
|---|---|
| `capability_id` | stable ID (`cap_...`) |
| `name` | human-readable name |
| `category` | `voice`\|`memory`\|`home_automation`\|`appliance`\|`messaging`\|`infrastructure`\|`hardware`\|`future` |
| `target` | the device/service/workflow/system this acts on |
| `discovery_source` | how we know this exists (doc, host scan, directive) |
| `status` | lifecycle state, see above |
| `control_path` | API route / MQTT topic / CLI / etc. actually used to control it |
| `required_credentials` | env var **names only**, never values |
| `supported_actions` | actions Aria may invoke once `verified_control` |
| `read_only_observations` | things Aria may report without acting |
| `verification_state` | free-text note from the last verification attempt |
| `last_verified_at` | timestamp of last verification |
| `current_blocker` | exact reason progress is stalled, or null |
| `next_step` | the concrete next action |
| `human_confirmation_policy` | `always_confirm`\|`confirm_destructive`\|`autonomous` |
| `receipt_log_location` | always `db.aria_capability_receipts` today |

## API (`backend/routes/capabilities.py`, prefix `/api/capabilities`, owner-only)

- `GET /api/capabilities` — list all.
- `GET /api/capabilities/{id}` — one capability.
- `POST /api/capabilities` — register a new capability (`AriaCapabilityCreate`).
- `PATCH /api/capabilities/{id}` — update any field (`AriaCapabilityUpdate`).
- `POST /api/capabilities/{id}/verify` — record a verification attempt
  (`{"outcome": "verified_read"|"verified_control"|"blocked"|"offline", "note": "..."}`).
  Writes a receipt to `db.aria_capability_receipts` and updates the
  capability's `status`/`verification_state`/`last_verified_at` in the same call.
- `GET /api/capabilities/{id}/receipts` — full verification history for one capability.

All routes require `require_owner` (Michael's owner account) — this is
control-plane data, not resident/staff/family-facing.

`get_capability_summary()` in the same module returns a concise text block
(name + status + blocker per line) for the "load a concise summary of the
current capability portfolio" voice-session-start rule in Terminal 5A. It is
implemented but **not yet wired into `routes/realtime.py`** — that happens
once Aria's tool routing is connected to this registry (Terminal 5A's ordered
step 3), which comes after the voice foundation itself is proven.

## Initial portfolio (seeded 2026-08-02)

| Capability | Status | Blocker |
|---|---|---|
| CAOSCare conversational voice and memory (Aria) | `blocked` | No `OPENAI_API_KEY` on this host |
| Home Assistant status and control API | `discovered` | No HA long-lived token minted; no integration code yet |
| Midea MAP14AS1TWT-C portable air conditioner (Matter) | `blocked` | HA VM still behind NAT; needs Ethernet cable or router change; paused for voice-first |
| eMeet Luna Plus microphone/speaker endpoint | `verified_read` | none — capture+playback mechanically verified; audible-quality check with Michael still pending |
| MQTT broker and messaging path | `planned` | Not installed (Terminal 3 Phase 4 not started) |
| EliteDesk service health and restart/status operations | `verified_read` | No control action implemented yet; backend/frontend not systemd-managed |
| Future resident-room and family/staff capabilities | `planned` | Not yet connected to Aria at all |

See `db.aria_capabilities` for the live, authoritative state — this table is a
snapshot at seed time, not re-synced automatically.
