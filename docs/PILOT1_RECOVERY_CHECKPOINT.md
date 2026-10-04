# CAOSCare Pilot 1 Recovery Checkpoint

Target: 2026-10-10
Goal: USABLE Pilot 1 product, not merely a website/demo

Current integration branch: `integration/2026-09-27` (GitHub `caosos/CAOSCARE.COM`)
Current integration SHA: the tip of `origin/integration/2026-09-27`. Last explicitly recorded accepted code state: `268963c` (SC-14/SC-15 integrated, 2026-10-03). Verify the live tip before every merge.
Current localhost:3000 source: `~/CAOSCARE-INTEGRATION/frontend` (systemd user service `caoscare-frontend-dev.service`, `/api` proxied to :8092)
Last verified: 2026-10-03 (documentation reconciliation; runtime details still require live verification)
Coordinator: Claude Code session in `~/CAOSCARE-INTEGRATION` on the EliteDesk (`caoscare1-hp-elitedesk`)
Production/Linode SHA: `d7ff96a4e4d1f4f253929377d7f386ee4b1cac6a` (read on the host 2026-09-28; public bundle `main.7a1fa061.js`)
Production deployment status: unchanged since 2026-09-27; none of the Pilot 1 integration work is deployed

**How to use this file.** Read it after `AGENTS.md`, `docs/CURRENT_PRIORITY.md`, `docs/PILOT1_EXECUTION_CHECKLIST.md` and `docs/PILOT1_ACTIVE_WORK.md`. If it conflicts with live source or runtime evidence, live evidence wins and this file must be updated.

**Where to read it.** These Pilot 1 files live on `integration/2026-09-27`, not on `main`. `main` (`880d10f`) is behind and its onboarding does not mention them. Read them with `git fetch origin && git show origin/integration/2026-09-27:docs/PILOT1_RECOVERY_CHECKPOINT.md` or from a checkout of that branch.

---

## 1. Non-negotiable development pipeline

```text
Laptop/control
→ SSH EliteDesk
→ feature lanes/worktrees
→ EliteDesk integration
→ whole-system tests
→ commit/push GitHub
→ Michael reviews exact release
→ deploy exact approved GitHub SHA to Linode
→ production verification
```

- EliteDesk = development/integration authority.
- GitHub = durable canonical committed history.
- Linode = approved production only.
- Worker lanes never deploy and never merge `main`.
- The integration coordinator merges one lane at a time and tests after every integration.
- Shared contracts belong to Shared Core (Lane E).
- Do not create parallel versions of CAOSCare.
- Release: show Michael the current production SHA, the proposed SHA and the exact commit/file range; deploy only after his explicit approval, with `scripts/deploy_caoscare.sh <sha>`.

## 2. Lanes and exact state (2026-09-28)

All worktrees below were clean and equal to their GitHub branch at this checkpoint.

| Lane | Purpose | Branch | Worktree | SHA | Status | Accepted / proven | Open blockers | Shared dependencies | Next action |
|---|---|---|---|---|---|---|---|---|---|
| Coordinator | Integration, tests, checklist, localhost:3000 | `integration/2026-09-27` | `~/CAOSCARE-INTEGRATION` | see header | Active | Nursing, Maintenance, Shared Core SC-1/SC-2, public panels, Therapy/Beauty placeholders integrated and browser-verified; Shared Core SC-3..SC-7 integrated at `1d02630` | — | all | Integrate Demo kiosk `0b69cae` |
| A Nursing | Care request loop | `pilot/nursing` (never created) | — | — | Core loop integrated at `7ae91bc` | "I need help going to the bathroom" → nursing queue → claim/ack/start/notes/complete → history (browser, 2026-09-28) | None in software; live voice test is RQ-003 | Shared Core | RQ-003 live voice acceptance with Michael |
| B Maintenance | Work orders | `pilot/maintenance` | `~/CAOSCARE-LANE-MAINTENANCE` | `51deae0` | **Integrated** at `6d1ffa4` | "My sink is leaking" lifecycle, three notes, five separate receipts (browser, `task_cf8ca2182ecb`); acceptance test `test_maintenance_resident_loop.py` | None (SC-3 test passes since `1d02630`) | Shared Core | — |
| C Front desk / Transportation | Front desk requests, callbacks, rides | `pilot/frontdesk-transport` | `~/CAOSCARE-LANE-FRONTDESK` | `6b67ac8` | Integrated at `5e6413c` (2026-10-03) | Every ride step now goes through `task_history.update_task_with_history`; history shown with the shared `RequestTimeline` (lane claim; coordinator not yet verified) | Needs SC-6, SC-7 (on `pilot/shared-core`) | Shared Core | Integrate after Shared Core; verify the transport timeline in the browser |
| D Community services | Dining/menu, activities/programs, housekeeping | `pilot/community-services` | `~/CAOSCARE-LANE-SERVICES` | `d95c4d6` | Handed off (based on `e9373d5`) | Kitchen/Activities/Housekeeping workspaces, menu paste intake and review, schedule draft batches, clock-ordered public schedule (lane tests only) | SC-9, CM-1; live/integration acceptance not done | Shared Core, Communications | Integrate after Front desk; live acceptance |
| E Shared core | Shared contracts | `pilot/shared-core` | `~/CAOSCARE-LANE-SHARED` | `5a9eb32` | SC-1..SC-7 integrated (`3249fcd`, `1d02630`) | SC-1, SC-2, SC-3 browser-verified; SC-4/SC-5 partly; SC-6/SC-7 tests only | SC-8, SC-9, SC-10 open | — | SC-10, then SC-8/SC-9 |
| F Communications / calling | Email delivery, notifications, phones | `pilot/communications` | `~/CAOSCARE-LANE-COMMS` | `0978bb1` | Implemented (based on `e9373d5`), tests only | Truthful notification delivery and fallback, Communications admin tab; calling per Michael's D1–D8 (see §6) — no Asterisk, ATA, trunk or OpenAI SIP test yet | Hardware, accounts, provider config; SC-8 | Shared Core | Integrate last; live acceptance needs hardware |
| G Demo kiosk | Demo kiosk command-to-visual state | `pilot/demo-kiosk` | `~/CAOSCARE-LANE-DEMO-KIOSK` | `0b69cae` | **Integrated** at `239324a` | Light on/off, thermostat, TV on/off visible from Aria commands (isolated stack + localhost:3000 Room 401); DEMO RESET on the isolated stack; Room 214 untouched | SC-10, SC-11, SC-12; volume/channel, blinds tool, staff-help/front-desk visuals not built | Shared Core | — (demo-only room `DEMO` since 2026-10-03) |

Other worktrees on the EliteDesk (older lanes, all clean and pushed, not part of Pilot 1 lanes): `~/CAOSCARE.COM` (`aria/conversation-substrate`), `~/CAOSCARE-ADMIN`, `~/CAOSCARE-CLAUDE`, `~/CAOSCARE-LEVEL1`, `~/CAOSCARE-LEVEL1-INTEGRATION`, `~/CAOSCARE-WEBSITE` (`feature/interactive-capability-cards`, PR #42), `~/CAOSCARE-WIP-PANELS` (merged into integration at `e70fbce`; can be retired when Michael agrees).

## 3. Shared core requests

"Implemented" means on a worker branch; "Integrated" means on `integration/2026-09-27`; "Verified" means proven in the browser/acceptance on integration.

| ID | Requirement | Implemented | Integrated | Verified |
|---|---|---|---|---|
| SC-1 | Receipts append per status change | `a6230cb` | `3249fcd` | Yes, 2026-09-28 |
| SC-2 | Timestamped note history (`StaffTask.event_log`) | `a6230cb` | `3249fcd` | Yes, 2026-09-28 |
| SC-3 | A claimed request counts as seen (truth defect) | `5a9eb32` | `1d02630` | Yes, 2026-10-02 |
| SC-4 | Latest note / completer in spoken status | `5a9eb32` | `1d02630` | Partly (latest note yes; completer by test only) |
| SC-5 | Real note timestamps; "times asked" wording | `5a9eb32` | `1d02630` | Partly (note time yes; wording by test only) |
| SC-6 | Front desk claim/assign/note on Administration | `5a9eb32` | `1d02630` | Tests only |
| SC-7 | Staff-entered callback times allowed | `5a9eb32` | `1d02630` | Tests only |
| SC-8 | Notifications linked to their request | Partly (`aa10645`: `notify_department` accepts the link; call sites not all passing it) | No | No |
| SC-9 | Department list readable by staff | No | No | No |
| SC-10 | Unsupported light attribute must not silently power the light on (truth defect) | No (filed by Lane G) | No | No |
| SC-11 | Mock devices in real rooms recorded as verified (simulator) | No | No | No |
| SC-12 | TV/thermostat commands carry the conversation `session_id` | No | No | No |
| CM-1 | Inbound activities email linked to its draft batch | No | No | No |

## 4. Next integration order

1. Shared Core `5a9eb32` (SC-3..SC-7) — **done** at `1d02630` 2026-10-02; SC-3 test passes.
2. Demo kiosk `0b69cae` — **done** at `239324a` 2026-10-02.
3. Front desk / Transportation `6b67ac8` — **done** at `5e6413c` 2026-10-03; ride-step receipt gap open (Agent 2).
3a. Simulator receipt-law docs `ffd1f60` — **done** at `75d19d8` 2026-10-03.
3b. Shared Core SC-13 `f5f07b4` — **done** at `79ca54b` 2026-10-03; follow-ups SC-14, SC-15 — **done** at `268963c` 2026-10-03 (`56f7807`).
4. Community services `d95c4d6` (based on `e9373d5`; expect doc conflicts).
5. Communications `0978bb1` (based on `e9373d5`; live acceptance needs hardware).

Test after each: backend gate (`backend/scripts/run_backend_tests.sh`), frontend tests, production build, the lane's browser acceptance.

## 5. Michael's decisions and priorities

**Deadline.** Pilot 1 must be USABLE by 2026-10-10: real resident Aria; real staff workflows; department routing and notifications; one or two actual resident rooms; minimum room hardware; calling; truthful receipts and status; a public site that shows only real, accepted capabilities.

**Functionality before design.** No major visual redesign while operational loops are unfinished.

**Public website.**

- Every major capability/department card is clickable.
- Each panel shows:
  - actual software where it exists;
  - supporting lifestyle imagery;
  - what the resident/staff does;
  - what CAOSCare does;
  - what staff sees;
  - what happens next;
  - what is built;
  - what is not yet accepted.
- Actual software visuals outrank generic pictures.
- Review notes:
  - Michael likes the interactive direction.
  - Therapy and Beauty Shop images must depict therapy and a salon; they are labelled placeholders until real images exist.
  - The colour palette is disliked; a cleaner blue + white with restrained neutrals comes later.
- Status labels advance only after acceptance evidence (`frontend/src/lib/capabilities/status.js`).

**Video.** Featured Video #001 is the ORIGINAL stitched ~30-second film, `frontend/public/media/caoscare-resident-experience-01.mp4`. Agents may raise concerns but may not recut, replace or edit Michael-supplied creative assets without explicit approval.

**Ask Aria.** Every appropriate page eventually gets a persistent bottom-right Ask Aria control. It is the same governed Aria, not a separate help bot:

- page-aware, product-aware, and knows CAOSCare workflows and where requests route;
- public mode exposes no private resident data;
- authenticated mode is permission-scoped;
- text fallback, with realtime voice where supported;
- no fabricated status or actions.

**Demo kiosk.** Commands must visibly affect the demo room before more design work.

- Flow: "Turn the light on" → normal Aria tool contract → simulated demo adapter → resulting state ON → the kiosk room visibly changes → truthful confirmation.
- The same flow applies to lights, thermostat, TV, blinds when supported, help requests and the front-desk call visualization.
- No second parser; demo state never touches real devices; DEMO RESET is required.

**Demo data continuity.** The simulated staff dashboard must not freeze between logins.

- Track `last_simulated_at`, with background simulation when available and deterministic catch-up on login/startup.
- Progress old simulated requests realistically, move finished work to history, keep open work bounded, and generate a plausible current state.
- Demo data stays strictly separate from real resident data.
- **Not yet assigned to a lane.**

**Room hardware — architecture reset 2026-10-03.**

- Target fleet direction: **one facility/building server + thin in-room voice endpoint + room-local control adapters only where physically required**. Do not plan an EliteDesk/dongle pile in every room.
- Existing EliteDesk + eMeet + Room 214 hardware remains the proven development/temporary Pilot 1 acceptance rig; it is not the intended per-room fleet standard.
- Ordered for prototype evaluation: **Home Assistant Voice Preview Edition** (CloudFree, backordered) and **Seeed Studio XIAO Smart IR Mate** (RobotShop). Neither is accepted until physical CAOSCare testing passes.
- TV/control strategy: native local IP/API first; CEC when useful; IR fallback through the room-local IR controller.
- Smart lights, blinds/window coverings, thermostat and sensors should use shared building Zigbee/Thread/Matter/Z-Wave/BLE/IP infrastructure where appropriate rather than per-room general-purpose computers.
- Pendant integration is **optional/additive**, not a Pilot 1 core dependency. The facility's existing pendant/call-button behaviour must never be interfered with. Passive read/ingest is allowed only when easy, approved and non-interfering.
- Still needed: exact pilot-room TV/thermostat/smart-plug models and protocols, Voice PE power/cable, IR Mate power plan, building-radio requirements actually needed by those devices, dependable wake/voice acceptance, and the calling BOM.

**Calling (Pilot 1 decisions).**

- Asterisk; an analog handset + ATA with off-hook/hotline behaviour to Aria, keeping direct digits (`0` = front desk).
- Approved family-contact calling; a SIP front-desk endpoint; local call control.
- Truthful provider/PBX call state.
- **911 bypasses Aria entirely.**
- Linode must not be needed for room-to-front-desk calls.

**Resident experience.** Aria is not "another Alexa". Core loop: ordinary resident need → context/intent → governed workflow → correct human department → receipt/state → truthful later follow-up.

## 6. Standard acceptance tests

| Area | Say / do | Must happen |
|---|---|---|
| Nursing | "I need help going to the bathroom." | Nursing request → staff sees → claim/ack/start/note/complete → history → Aria later reports the truth |
| Maintenance | "My sink is leaking." | Work order → claim/assign/start/note/time/complete → history → Aria reports the truth |
| Transportation | "I need transportation for my appointment at 9:30 on the fifth." | Clarify only missing facts → availability/request → staff assignment/confirmation → history/status |
| Front desk | "I want to speak with the executive director." | Front desk request with lifecycle and callback |
| Status | "Did anybody see my request?" | Answer from real state only; acknowledged ≠ on the way; in progress ≠ arrived |
| Room | "Turn the light on." | Real device or simulated demo state → verified state → visual/voice confirmation |
| Calling | "Aria, call the front desk." / "Call my daughter." | Truthful call state; family contact must be approved |

Demo data for tests: residents in rooms `3W01`–`3W10` (`Demo -` names), staff `@demo.caoscare` (e.g. Nancy Reyes RN, nursing; Carl Boone, maintenance), seeded by `backend/scripts/seed_demo_community.py`. Never use Room 214 / real residents for scripted tests.

## 7. Local runtime (EliteDesk, 2026-09-28)

| Port | What | Source |
|---|---|---|
| 3000 | Frontend dev server (`caoscare-frontend-dev.service`, drop-in `~/.config/systemd/user/caoscare-frontend-dev.service.d/worktree.conf`) | `~/CAOSCARE-INTEGRATION/frontend` |
| 8092 | Backend (nohup uvicorn, log `/tmp/room214_backend_239324a.log`) | `~/CAOSCARE-INTEGRATION/backend`, restarted 2026-10-02 22:40 CDT on `239324a` |
| 8000 | Old Level 1 backend, still the RF bridge target (`android-bridge/caos_rf_bridge.py`, pid 522046) | `~/CAOSCARE-LEVEL1-INTEGRATION/backend` |
| 8001 | Old Admin backend | `~/CAOSCARE-ADMIN/backend` |
| 27017 | MongoDB, database `caoscare` (shared by all local backends; real Room 214 data lives here) | system |

The pendant (RF bridge) still posts to :8000, not :8092. Moving it is a Room 214 hardware decision for Michael.

## 8. Do not change without Michael

- `main`, Linode, production data.
- Michael-supplied creative assets (Video #001).
- The RF bridge target and the facility pendant/call-button path.
- Real Room 214 devices and data (real-hardware tests are gated by the `real_hardware` pytest marker).
- Another lane's worktree.

---

## Michael's execution rule and ready queue

> **Capture everything. Execute one thing. Finish it. Then move.**

This is an operating/governance rule, not a ban on safe concurrency.

**Michael:** actively manages one decision/action at a time. New ideas are captured immediately but do not hijack the current task. Whenever practical, present Michael with one next decision/action.

**CAOSCare organization:** may run several jobs in parallel only when they are independently bounded, already approved, clearly owned, have known dependencies, and cannot silently redefine one another's shared contracts. “One thing at a time” applies per worker and to Michael's active management burden.

The coordinator now owns four related functions:
1. **ACTIVE WORK** — who is currently doing what?
2. **DEPENDENCIES** — what shared/core work must happen first?
3. **READY QUEUE** — what approved bounded job can an idle worker safely take next?
4. **INTEGRATION** — what completed branch is safe to merge next?

The coordinator must **not** create busywork to keep agents occupied, give two agents ownership of the same shared contract, or start lower-priority speculative work merely because a worker is idle. **Idle is better than destructive parallelism.**

Authoritative queue: [`PILOT1_READY_QUEUE.md`](PILOT1_READY_QUEUE.md).

Current queue summary at this checkpoint:
- **READY:** RQ-001 Demo data continuity (Demo kiosk integrated at `239324a`); RQ-003 Live Nursing voice acceptance (needs Michael); RQ-004 Pilot hardware inventory.
- **WAITING:** RQ-002 Global Ask Aria; RQ-006 Pilot Room 1 provisioning.
- **BLOCKED:** RQ-005 Live email / Resend acceptance.
- No queued task was started in the governance work block that created the queue.

## External memory principle

Chat/Claude sessions are **execution terminals, not authoritative project memory**.

Durable project truth lives in:
- source/runtime evidence;
- Git history;
- `CURRENT_PRIORITY.md`;
- `PILOT1_EXECUTION_CHECKLIST.md`;
- `PILOT1_ACTIVE_WORK.md`;
- `PILOT1_READY_QUEUE.md`;
- `PILOT1_RECOVERY_CHECKPOINT.md`;
- `PROJECT_STATE.md`.

A conversation may disappear without taking the project with it. New agents should not require Michael to reconstruct prior conversation.

Before changing code, a cold-start agent must know the current integration SHA, its lane, current active task, shared dependencies, whether its job is ACTIVE / READY / WAITING / BLOCKED, and the October 10 usable-product target.
