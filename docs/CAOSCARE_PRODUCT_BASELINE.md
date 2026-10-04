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

Current resident-room architecture / product direction (Michael, 2026-10-03):

- **One facility/building brain, not one general-purpose PC per resident room.**
  The target fleet architecture centralizes CAOSCare services on a
  facility-local server (EliteDesk-class or equivalent): CAOSCare service
  layer, Home Assistant integration, database/state, routing, speech/AI
  services where applicable, receipts/provenance, and operator/admin
  services.
- **Thin in-room voice endpoint.** A resident room should contain only the
  hardware that physically needs to be near the resident. The active
  prototype candidate is the **Home Assistant Voice Preview Edition**:
  microphone array, speaker, local-capable wake-word endpoint, Wi-Fi and
  room audio interface. One unit has been ordered for bench evaluation
  (CloudFree; backordered as of 2026-10-03). It is **not accepted hardware
  until physical CAOSCare tests pass**.
- **Room-local IR only where needed.** The active prototype candidate is a
  **Seeed Studio XIAO Smart IR Mate**, ordered 2026-10-03, for learning and
  transmitting TV/PTAC/fan remote codes over a network-controlled path.
  TV control order is: native local IP/API control first; HDMI-CEC when it
  gives a useful deterministic path; IR as the universal legacy fallback.
- **Shared building device networks.** Lights, blinds/window coverings,
  thermostats, outlets and sensors should normally use shared
  Zigbee/Thread/Matter/Z-Wave/BLE/IP infrastructure rather than a radio
  dongle or computer in every room. Distributed radio coordinators/proxies
  are allowed where physical coverage requires them; distributed radio is
  not a second server.
- **Music/audio.** The room voice endpoint may handle spoken responses.
  Better music playback may use the endpoint's audio output or another
  room speaker if physical testing shows the built-in speaker is
  insufficient.
- **Existing facility pendant/call-button systems remain independent.**
  CAOSCare may passively ingest an existing event stream or RF transmission
  when that is easy, approved and non-interfering, but pendant integration
  is not a core dependency of the resident voice product or Pilot 1.
- **Existing EliteDesk + eMeet + TV room rig is retained as proven
  development/acceptance hardware, not the target per-room fleet design.**
  It may be used temporarily to keep Pilot 1 software and real-room
  acceptance moving while the thin-endpoint prototype is unavailable or
  still under test. Do not infer from that temporary use that every room
  should receive an EliteDesk.

**Proven vs planned must always be distinguished.** Proven today on the
existing development rig: EliteDesk host + Nooelec SDR + rtl_433 RF decode +
real paired Lifeline/Interlogix pendants + OpenAI Realtime voice through a
room audio endpoint + resident voice control of real Home Assistant-backed
lights with read-back verification (2026-09-05) + the local wake-word
mechanism (listener → page → existing session) at close range, Room 214,
2026-09-23. Newly ordered but **not yet physically accepted**: Voice PE and
XIAO Smart IR Mate. Planned / partial: dependable far-field wake behaviour,
thin-endpoint CAOSCare integration, TV control strategy acceptance, IR
learning/control acceptance, shared multi-room radio coverage, and a
repeatable room-install BOM.

### Resident activation paths

- **Existing pendant / call-button system** — remains a parallel facility
  safety system and is not replaced by CAOSCare voice. Passive observation or
  integration is optional and must not interfere with the building's current
  path. It is not required for Pilot 1 core acceptance.
- **Room screen** — "Call for help" / "I just want to talk" buttons.
- **Voice (spoken wake phrase)** — local on-device wake detection starts a
  conversation-only session (no resident event). Requirement: natural voice
  activation without touching anything; detection must stay local — no
  continuous room audio sent to a cloud service to find the wake phrase.
  The durable assistant-name decision is **not changed by a hardware
  prototype alone**. "Aria" remains the current product name in the repo until
  Michael explicitly finalizes a rename. The single word "Aria" is not
  accepted as the production wake phrase (2026-09-24: "air-ee-uh" is
  identical to the common word "area"; overnight false wakes). Voice PE ships
  with supported wake models such as "Hey Jarvis"; using one for a prototype
  does not silently rename the product. The production activation phrase and
  utterance-boundary behaviour must be selected by evidence
  (`docs/WAKE_PHRASE_LAB.md`, `docs/ARIA_WAKE_WORD_ARCHITECTURE.md`).

### Room-control boundary — Home Assistant (Michael-directed, 2026-09-23)

```
Aria / resident endpoint
  → canonical CAOSCare service layer
  → Home Assistant integration (backend/device_adapters.py)
  → physical room device
  → verified resulting state (read-back)
  → CAOSCare receipt / device state
  → Aria confirmation (only of the verified result)
```

- Home Assistant is a **local hardware/control integration layer**, not
  CAOSCare's canonical brain. CAOSCare owns residents, rooms, devices,
  requests and truth; HA executes and reports physical state.
- Resident endpoints do **not** each need Home Assistant administrator
  accounts; the CAOSCare backend holds the integration credential.
- Michael's personal/home Home Assistant and the CAOSCare development /
  facility Home Assistant are **separate systems** — never conflate them.
- Home Assistant Cloud (Nabu Casa) is an optional remote-access service and
  is **not** the same thing as local Home Assistant; nothing here depends on
  it.
- Known gap: today the resident page calls the device endpoint
  (`/devices/public/room/{room}/command`) from the browser without
  authentication — existing technical debt, not the intended boundary.

### Resident endpoint — alternative UNDER EVALUATION (not ratified)

A **managed Android phone + dock** is being evaluated as a possible future
resident endpoint. **This is not a ratified replacement; the EliteDesk + eMeet
+ TV room node above remains the active architecture** and is not deprecated.

- Possible phone advantages being investigated: built-in battery, Wi-Fi,
  optional cellular failover, Bluetooth, camera, display, mic/speaker, local
  compute, USB-C peripherals, possibly lower room hardware cost.
- Possible dock capabilities being investigated: charging, far-field
  mic/speaker, USB expansion, IR, and only those room-local radios or
  peripherals that prove necessary. No dock name has been chosen — use
  neutral terms ("phone dock", "CAOSCare dock") until Michael names it.
- Phone work must not block current development. New resident-facing work
  should avoid needless coupling of the service layer to EliteDesk/Chrome,
  without speculative refactors. The wake-word page protocol
  (`room-node/aria_wake/README.md`) was built endpoint-neutral for this
  reason. Nothing Android has been built or tested.

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
  Concretely (ratified 2026-09-20, full decision record in
  `docs/ENGINEERING_CONTRACT.md`): human UI, Aria, any future simulator,
  front desk, and external adapters all call the SAME canonical service
  functions rather than each maintaining a parallel state system, and a
  human-facing "what needs attention now" aggregation (Live Board) is a
  read model over the canonical domain objects — reusing Aria's own
  `resolve_operational_state()` unification where practical — never a
  second source of truth in its own right.
- **If the UI shows something actionable, it should generally be clickable
  into the underlying truth.** No decorative dead-end numbers/cards/rows;
  if something genuinely can't drill deeper, make its non-interactive
  nature visually clear.
- **File size / modularity.** Implementation files and UI components stay
  roughly within 300-400 lines when reasonably practical; ~400 is a signal
  to split by responsibility, not a hard wall. Canonical rule (and its
  history) lives in `AGENTS.md`'s "Change discipline" section — do not
  restate it here.
- **Truth discipline.** The system must know the difference between
  requested, attempted, succeeded, failed, inferred, and unknown.
  Meaningful actions produce receipts / events.
- **Receipt/provenance invariant (Michael-directed, 2026-10-02).** No action is
  validly complete without a durable receipt, and no receipt is valid without a
  traceable origin. Human, agent, scheduler, Aria, provider, device, simulator
  and external-integration actions must link actor + authority + intent + target
  + execution + result evidence + resulting state. An agent's self-report is
  never completion evidence. See `docs/CAOSCARE_OPERATIONS_SIMULATOR.md`.
- **Simulator same-world invariant.** Any operations simulator uses the same
  canonical service functions and domain objects as real resident/staff/admin
  flows. Simulated actors/adapters are explicit; they do not create a parallel
  business-logic universe. Real and simulated actors may coexist in a scenario
  when their identity/provenance is unambiguous.
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
