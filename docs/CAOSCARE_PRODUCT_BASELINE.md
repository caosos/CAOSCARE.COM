# CAOSCare Product Baseline

**Canonical durable product truth.** Read this immediately after `AGENTS.md`,
before any CAOSCare work.

This document holds the current architecture and product invariants. It is
**not** a build log. For changing state use the other files:

| File | Holds |
|---|---|
| `docs/CAOSCARE_PRODUCT_BASELINE.md` (this) | durable truth · architecture · product invariants |
| `docs/PROJECT_STATE.md` | changing build state (append-only dated entries) |
| `docs/REPO_MAP.md` | where the implementation lives |
| `docs/BUILD_STATUS.md`, `docs/CURRENT_NODE_STATUS.md` | operational / runtime snapshots (point-in-time) |
| `docs/*_CONTRACT.md`, `docs/ROOM_AUDIO_ARCHITECTURE.md`, TSBs | task- and domain-specific rules and incident records |

When an older document conflicts with this one on architecture or product
direction, **this document wins** and the older statement is stale. Do not
delete useful history — mark it `HISTORICAL / SUPERSEDED` and point here.

---

## 1. What CAOSCare is

CAOSCare is the senior-care vertical of the CAOS ecosystem: a **governed,
assistive, human-supervised, receipt-backed** operating layer for a
senior-living community. It is not a doctor, nurse, emergency service,
medical device, or autonomous clinical decision-maker.

The intent is for CAOSCare to become the **operational nervous system of a
senior-care community** — resident context and assistance, then department
workflows, then cross-department coordination, then building/environmental
awareness, then higher-level automation. Later layers are **direction, not
built** (see §6).

---

## 2. Resident-room architecture (CURRENT)

**The resident room is NOT a tablet-based system.** The older concept of a
specialized, docked, or wall-mounted resident tablet as the primary room
interface is **obsolete** (`HISTORICAL / SUPERSEDED`).

Current resident-room architecture:

- **Room node** — a local CAOSCare computer per resident room. Current
  proven hardware baseline: an **HP EliteDesk-class small-form-factor PC**
  (the bring-up host is `caoscare1-hp-elitedesk`, an HP EliteDesk 705 G4
  DM). It is meant to sit **hidden behind or near the resident's TV**. The
  resident does not operate or see a conventional computer.
- **Resident audio** — an **eMeet-class conferencing speakerphone** sits
  near the resident's normal sitting/bed position and is the **single room
  audio capture + playback endpoint** for Aria's voice pipeline (one mic,
  one speaker per room). See `docs/ROOM_AUDIO_ARCHITECTURE.md` for the
  full AEC reasoning — that document is canonical for room audio.
- **TV** — remains the resident's normal television, and may also be used
  as a CAOSCare **visual output surface** when appropriate. TV audio is
  intended to eventually route through the same eMeet path so one AEC path
  owns both Aria and TV playback; the TV's own speakers are muted whenever
  CAOSCare owns TV audio.
- **Handset** — a corded/wireless handset held at the ear remains the
  guaranteed-duplex fallback audio surface.
- **Room-node integrations** — the room node *may include or integrate*, as
  the product develops: an RF receiver/transmitter covering a **wide range
  of frequency devices** (existing pendant / call-button / sensor
  infrastructure across the common sub-GHz bands — e.g. 315 / 319.5 / 433 /
  868 / 915 MHz — not a single fixed frequency), infrared control, Zigbee,
  Z-Wave or other local protocols, networking, communications integrations
  such as Twilio, and additional room-automation interfaces. The existing
  Android RF-bridge process (`android-bridge/`) is the current RF-decode
  path and is being **consolidated into the room node** — treat "bridge
  tablet" in older material as "the room node's RF receiver process".

**Proven vs planned must always be distinguished.** Proven today: EliteDesk
host + Nooelec SDR + rtl_433 RF decode + real paired Lifeline/Interlogix
pendants + OpenAI Realtime voice through a room audio endpoint. Planned /
partial: TV audio into the CAOSCare AEC path, IR/Zigbee/Z-Wave transmit,
full room-automation surface, multi-room fleet.

### "Kiosk" terminology

In this codebase `kiosk` is a **software/UI concept** — a per-room
resident-facing CAOSCare surface and its `Kiosk` record (room ↔ resident
mapping, `kiosk_id`). It does **not** mean a physical tablet appliance.
Where older docs or code comments use "kiosk" or "kiosk tablet" to mean
hardware, that wording is stale; the hardware is the room node above.

---

## 3. Staff-client model (CURRENT)

**Staff tablets, phones, and computers are valid and unchanged.** A staff
device is simply a logged-in CAOSCare client. Authentication resolves the
user's **role + department** and presents the appropriate authorized
workspace:

| User | Client | Lands in |
|---|---|---|
| Maintenance / Housekeeping / Transportation / Kitchen staff | tablet / phone / computer | that department's operational workspace (`/workspace`) |
| Nursing / Care staff | tablet / phone / computer | resident-assistance / care surface |
| Owner / Admin | computer (typically) | community command centre |

A "Maintenance tablet" is a Maintenance client; a "Kitchen tablet" is a
Kitchen client. **Do not build tablet-specific business logic** — a tablet
is a client of the same role/department-scoped workspaces every other
client uses.

---

## 4. Owner / Admin vs department staff

**Owner/Admin sits above the department workspaces.** Owner/Admin must be
able to inspect and manage: community operations, residents, rooms,
departments, staff, alerts/events, devices, reporting/audit, user access,
and facility setup — and can inspect the same operational work each
department sees. Department staff see only their department's authorized
workspace. Department isolation is enforced server-side
(`routes/tasks.py::list_tasks` scopes a `staff` role by `User.department`).

---

## 5. Aria information principle

Aria must not fabricate missing facility information, and CAOSCare should
avoid dead ends where a recovery path exists.

- **Data exists → use it.** Answer from the real record.
- **Data missing + a recovery workflow exists → use it.** Route/request the
  missing information from the responsible staff/department, and state
  truthfully what action was actually taken.
- **Data missing + no recovery path → say so truthfully** and preserve the
  need as a product/workflow gap.

Example: "What is for dinner?" — answer from the approved Menu record if it
exists; if not, request it from the kitchen through the existing request
path and tell the resident that was done; if there is no such path, say the
menu isn't available and log the gap. **Resident Aria runtime behavior is
Claude 2's lane** — this principle is doctrine, not a licence for another
lane to change Aria's code.

---

## 6. Priority order and future direction

**Current active priority: make the RESIDENT MODULE reliable first** —
resident context, room, assistance, communication, information retrieval,
staff routing, appropriate reminders, resident-facing Aria behaviour, and
the linked operational truth behind all of it.

Priority layers (do **not** present later layers as built):

1. Resident module ← current focus
2. Department workflows ← partially built (Maintenance, requests, transport, staff routing)
3. Cross-department coordination
4. Building / environmental awareness
5. Higher-level automation / optimisation

### FUTURE PRODUCT DIRECTION (not built)

- **Appointments / transportation.** Appointments may enter via staff
  entry, email ingestion, integrations, or external scheduling feeds; the
  appointment record becomes shared operational truth; Transportation
  receives tentative/suggested scheduling from it; staff confirm/adjust the
  driver/vehicle assignment; the resident may get Aria reminders (upcoming,
  next-day, same-day/departure, weekly review). Objective: humans should
  not have to remember what the system already knows.
- **Building / environmental organism.** Future building awareness *may*
  include hallway occupancy/motion, lighting state, energy optimisation,
  HVAC/thermostat state, mechanical-room temperature, irrigation runtime,
  fire-panel / building-system telemetry where legally and technically
  appropriate, doors/zones/equipment, and environmental anomalies — mostly
  by **consuming existing Home Assistant / building-controller telemetry
  before adding redundant instrumentation**. None of this is implemented.

---

## 7. Local-first deployment direction

- CAOSCare is **primarily local-first** within the community. Room nodes
  communicate with the local facility system.
- Appropriate functions should keep working locally during upstream /
  internet disruption where technically possible.
- Community staff **use the application**; they do **not** receive
  unrestricted source-repository access. Commercial deployment is expected
  to use controlled software releases / licensing, not handing customers
  the development repository. (The licensing/update implementation is not
  designed here.)

---

## 8. Engineering invariants

- **One source of truth.** No duplicate task, resident, alert, device, RF,
  reporting, staff, or department universes. A simplified dashboard may
  summarise a real source; clicking through must reach the real detail.
- **If the UI shows something actionable, it should generally be clickable
  into the underlying truth.** No decorative dead-end numbers/cards/rows;
  if something genuinely can't drill deeper, make its non-interactive
  nature visually clear.
- **Handwritten production-code file size: aim below 300 lines; hard cap
  300 lines** unless Michael explicitly approves an exception. Split by
  clear domain/responsibility, never arbitrary chopping. Do not launch a
  broad refactor solely to shrink an untouched legacy file; if you must
  modify a file already over the cap, do not make it larger — extract the
  responsibility being changed. Documentation, reports, generated files,
  static data, lockfiles, and necessary config are exempt. This is the
  canonical rule; it **replaces** the older "200-line soft / 400-line hard"
  guidance in `docs/CAOS_CARE_AGENT_ONBOARDING_CONTRACT.md`.
- **Truth discipline.** The system must know the difference between
  requested, attempted, succeeded, failed, inferred, and unknown.
  Meaningful actions produce receipts / events.
- **Preserve evidence.** Never do a destructive cleanup (bulk delete,
  overwrite, migration) of real or historical test data without explicit
  approval; raw evidence is preserved before any lifecycle migration.

---

## 9. Canonical agent boot sequence

Every AI/human builder, before meaningful CAOSCare work:

1. Read `AGENTS.md` (the one file to remember first).
2. Read this Product Baseline.
3. Read `docs/PROJECT_STATE.md` (recent dated entries).
4. Read `docs/REPO_MAP.md`.
5. Read `docs/BUILD_STATUS.md` / `docs/CURRENT_NODE_STATUS.md` where runtime matters.
6. Read the task-specific contracts / TSBs.
7. Identify the exact **branch/ref** and the **assigned lane** (what this
   agent owns and what it must not touch).
8. Inspect the **actual relevant source** before claiming what exists.
9. Inspect **actual runtime / telemetry** when runtime behaviour matters.
10. **Inventory the tools / connectors / capabilities available in the
    current environment** before telling Michael "I can't access / look up
    / do that" — check whether an available tool or connector can.
11. Keep these distinct at all times: **repository truth · runtime truth ·
    physical test evidence · Michael-provided product direction · inference
    · planned future capability.**
12. **Preserve raw evidence** before any destructive cleanup.
13. Update `docs/PROJECT_STATE.md` at meaningful handoff points, and leave a
    **handoff capsule** (§10).

---

## 10. Handoff capsule (agent/session transfer)

Replaces the manual "transfer token" text. At a handoff, record **only**
what the next agent needs to continue correctly — not the whole history:

```
HANDOFF CAPSULE
- Objective:        <what is being built right now>
- Branch:           <exact branch/ref>
- Lane / ownership: <what this agent owns; what it must NOT change>
- Last proven state:<what is actually verified working, and how>
- Commits:          <SHAs pushed this session>
- Runtime state:    <servers/services, ports, anything live and relevant>
- Unresolved proven defects: <bug + evidence, or "none">
- Product invariants that matter here: <the 2-4 that constrain this work>
- Do NOT change:    <files/behaviours off-limits, esp. the other lane>
- Next safe action: <the single concrete next step>
```

Durable product truth goes in this baseline / the contracts. Current
temporary state goes in `PROJECT_STATE.md` and the handoff capsule. Keep
them separate.

---

## Non-negotiable

CAOSCare is assistive, governed, human-supervised, privacy-aware, and
receipt-backed. No autonomous medical judgment. No fabricated clinical or
facility claims. No silent privacy risk. No undocumented architecture. No
decorative dead-end UI. No erased evidence.
