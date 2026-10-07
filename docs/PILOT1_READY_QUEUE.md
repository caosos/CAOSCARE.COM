# CAOSCare Pilot 1 Ready Queue

Target: 2026-10-10  
Integration branch: `integration/2026-09-27`  
Owner: Pilot 1 integration coordinator  
Created: 2026-09-28

## Michael's control rule

> **Capture everything. Execute one thing. Finish it. Then move.**

### Interpretation

**Michael**
- actively manages one decision/action at a time;
- new ideas are captured immediately so they are not lost;
- captured ideas do not hijack the current task;
- whenever practical, the coordinator presents Michael with the single next decision/action.

**The CAOSCare organization**
- may execute several jobs in parallel only when those jobs are independently bounded, already approved, have clear ownership, have known dependencies, and cannot silently redefine one another's shared contracts;
- applies "one thing at a time" per worker and to Michael's active management burden;
- does not treat this rule as a ban on safe parallel work across independent lanes.

## Queue status meanings

| Status | Meaning |
|---|---|
| READY | Approved, bounded, compatible work that is safe for the coordinator to assign now. |
| WAITING | Approved work whose dependency is not yet finished. |
| BLOCKED | An external requirement prevents meaningful progress or acceptance. |
| ASSIGNED | Coordinator has given the job to one named lane/worker. |
| DONE | The exact definition of done / acceptance has been met. |
| PARKED | Preserved idea that must not steal Pilot 1 time. |

## Queue rules

1. Worker agents never invent work merely because they are idle.
2. Worker agents do not self-promote speculative backlog items to READY.
3. The coordinator may assign the highest-priority compatible READY task when a worker becomes idle.
4. WAITING means the job is approved but a dependency is unfinished.
5. BLOCKED means an external requirement prevents progress.
6. PARKED preserves ideas without allowing them to steal Pilot 1 time.
7. A job moves to DONE only after its definition of done / acceptance is met.
8. Shared-contract dependencies still go through Shared Core.
9. Integration still happens one branch at a time with tests between merges.
10. Michael can override ordering at any time.
11. Idle is better than destructive parallelism.

## RQ-010 — Autonomous Agent 1 foreman / persistent team

- **Priority:** P0 coordination infrastructure.
- **Intended lane:** Coordinator + Agent Control Plane.
- **Dependencies:** extend PR #67; preserve the existing queue/active/checklist authority; host must have tmux for runtime acceptance.
- **Definition of done:** owner-only Agent Operations is mounted behind its feature flag; dedicated tmux sessions survive SSH disconnect; every worker publishes branch-local status; Agent 1 reconciles READY/ACTIVE/dependencies and assigns the next compatible task; at least two non-overlapping workers finish with tests/receipt/commit/push and continue without Michael relaying instructions; reboot recovery is proven; no Linode deployment.
- **Safe-to-start:** Michael explicitly authorized setup on 2026-10-07. Existing historical Claude sessions are not hijacked; dedicated sessions are new.
- **Status:** ASSIGNED — repo/control-plane implementation on PR #67; EliteDesk runtime acceptance still requires host execution/evidence.
- **Receipt expectation:** audit report + control-plane/foreman commit + host tmux/status evidence + worker receipts + coordinator integration receipt.

## Seeded queue

| ID | Priority | Task | Intended lane | Dependencies | Exact definition of done | Safe-to-start condition | Status | Originating Michael decision / requirement | Resulting branch / SHA |
|---|---:|---|---|---|---|---|---|---|---|
| RQ-001 | 2 | Demo data continuity | Demo data continuity / Lane G-adjacent bounded worker | Current Demo kiosk work `pilot/demo-kiosk@0b69cae` must be integrated or coordinator must prove file ownership does not overlap. Strict separation from real resident data. | Returning to the demo after elapsed time shows a believable current community state instead of hundreds of frozen stale requests: `last_simulated_at`; background progression when available; deterministic catch-up on login/startup; old simulated work progresses realistically; completed work moves to history; unresolved work stays bounded; plausible new/current simulated state; real resident data is never touched. | Start only after Demo kiosk is accepted/integrated **or** the coordinator explicitly proves a non-overlapping branch/file boundary. | ASSIGNED (Agent Five, 2026-10-04; new files only; merges after SC-16/17) | Michael approved demo continuity so the simulated staff dashboard behaves as though time passed while nobody was logged in. | — |
| RQ-002 | 3 | Global Ask Aria | Resident/public experience worker; Shared Core owns any shared contract change | Stable governed Aria/auth/page contracts; no collision with current Shared Core or Demo kiosk integration. | Appropriate CAOSCare pages have a persistent bottom-right Ask Aria entry point using the **same governed Aria**, page-aware and product/workflow-aware, with text plus realtime/full-duplex voice where supported; click requires no wake word; authenticated pages are permission-scoped; public pages expose no private resident data; actions/status are truthful; opening/closing preserves current page/context. | Start only after the coordinator confirms the current Shared Core + Demo kiosk integration has stabilized the reused Aria and page contracts and no shared contract must be independently redefined. | WAITING — readiness audit merged (PR #61, `92beeec`). Blocked until (a) the unauthenticated `/realtime/aria-session` owner-memory exposure is fixed (Agent Six, security PR) and (b) Michael decides Aria governance for public/authenticated pages | Michael approved a persistent Global Ask Aria entry point; it must not become another chatbot. | — |
| RQ-003 | 1 | Live Nursing voice acceptance | Nursing / care requests | Shared Core status-truth fixes must be integrated and verified first (SC-3 status truth is the explicit blocker). | Through actual resident Aria voice, “I need help going to the bathroom.” proves request → nursing → staff lifecycle → later spoken status truth. | Shared Core status-truth fix integrated on `integration/2026-09-27`, gates pass, and coordinator re-checks claim/status truth. | READY — **priority for the next acceptance loop** (2026-10-05); needs Michael speaking to a room screen. SIM-4 Nursing (simulated loop) accepted at `7446cc7` | Michael requires the accepted Nursing loop to be proven through actual resident Aria voice. | — |
| RQ-004 | 1 | Pilot hardware inventory | Hardware / Pilot Room inventory worker | Physical-model evidence may be needed for devices whose exact make/model/protocol is not recorded. | One exact Pilot Room hardware BOM identifies owned vs needed items and exact protocol/compatibility for wireless thermostat, wireless bulbs, smart plugs, TV/model, eMeet/audio, RF receiver, pendant/button equipment, room node, network requirements, IR requirement, and ATA/handset/front-desk SIP hardware requirement. No guessed model numbers or protocols. | **May start now** from repo/hardware evidence. Inventory what is proven; consolidate unknown physical model numbers into one request. If the missing physical evidence prevents further progress, change this item to BLOCKED rather than guessing. | BLOCKED — BOM integrated at `42ac6f3` (PR #47); remaining items need Michael's physical facts | Michael requires an exact Pilot Room BOM before provisioning. | — |
| RQ-005 | 1 | Live email / Resend acceptance | Communications / calling | External provider/domain configuration, real inbound addresses, sender allowlists, and real department destinations are required. SC-8/request-linked notification work must be integrated as applicable. | Verified sending/domain configuration; inbound menu address; inbound activities address; sender allowlists; real department addresses; real nursing, maintenance, and transportation notifications; delivery/bounce state; request-linked notification receipts; real inbound and outbound paths acceptance-tested. | Start acceptance only when the required real provider/domain/address configuration is available and the request-link contract is integrated. | BLOCKED | Michael requires real inbound/outbound email acceptance, not logged/simulated delivery. | — |
| RQ-006 | 1 | Pilot Room 1 provisioning | Pilot Room provisioning | Operational core sufficiently integrated; exact room hardware BOM; wake/voice path; required device adapters; calling hardware/path as required for Pilot 1. | First real resident room operates under normal use without SSH babysitting and survives reboot and network interruption/recovery. | All listed dependencies accepted enough for a real-room install and coordinator assigns the room/provisioning lane. | WAITING | Michael requires the first real resident-room installation for Pilot 1. | — |
| RQ-009 | 3 | Hearing Assistance / Personal Audio Compatibility | Agent Six (Round 5) — research/docs only | None for research. Any later product change goes to the owning lane (Shared Core / voice / room audio) as a separate, approved task. | A research document on an isolated branch, opened as a draft PR into integration: how residents who use hearing aids or other personal audio devices can hear Aria and room announcements; the options and their technical/compatibility requirements; what applies to the current room architecture (Voice PE room endpoint, central server); each claim sourced; unknowns marked UNKNOWN; open questions for Michael. No code, firmware or shared-file changes. | May start now: research/docs only, no heavy compute, no shared-code ownership. | ASSIGNED (Agent Six, 2026-10-04) | Michael, 2026-10-04: add RQ-009 as assigned to Agent Six, research/docs only. | — |
| RQ-008 | 2 | EliteDesk storage + obsolete worktree cleanup | Agent Five (Round 5) — read-only audit first | Active wake batch / heavy jobs must not be using the related files or worktrees before any deletion; worktree owners consulted. | Filesystem usage recorded; git worktrees inventoried; each worktree classified ACTIVE / MERGED / OBSOLETE / UNKNOWN; unpushed/uncommitted work protected; large node_modules / venvs / build / cache / lab artifacts identified; safe reclaim estimate produced; cleanup executed later only from an approved, evidence-based list; post-cleanup disk receipt recorded. | **Audit may start now (read-only).** Deletion must not start while the wake batch or other heavy jobs use related files/worktrees, and only from a list Michael approves. | ASSIGNED — audit + RF bridge log audit merged (PR #58, `57f71ce`); Phase 1 cache cleanup done (8.03 GB). **Phase 2 deletions: awaiting Michael approval** — none authorized | Michael, 2026-10-04: record a bounded storage/worktree cleanup so it cannot get lost. | — |
| RQ-007 | 0 | Receipt-backed Operations Simulator | New bounded Simulator lane; Shared Core owns any canonical receipt/service-contract changes | Canonical request/task/receipt services; simulator must not fork business logic. | Michael can Start/Pause/Step/Resume a simulated community, watch the live event/receipt stream, trace every action to origin, and assign at least one normally simulated staff role to a real logged-in human who completes work through the normal UI; simulator then continues from the real resulting state. No action without a receipt; no orphan state change; real/simulated identity explicit. | Documentation/spec may start now. Code starts only after coordinator assigns a non-conflicting lane and identifies any Shared Core receipt-contract work. | ASSIGNED — SIM-1 `1126d8c`, SIM-2 `5567d3e`, SIM-3 `c276a2b`, latest-run `737df76`, **SIM-4 Nursing accepted at `7446cc7`** (PR #62, 2026-10-05); demo room only until Michael lifts the gate | Michael, 2026-10-02: build multiple agents that artificially run the community, make everything visible, allow real people to take over roles, and prohibit any action that cannot be traced to origin. | `agent/operations-simulator-receipts` (governance/spec branch) |

## Current queue summary

**ASSIGNED (Round 5, 2026-10-04):** RQ-009 Hearing Assistance / Personal Audio Compatibility (Agent Six, research/docs only); RQ-007 SIM-2 Live Operations UI (Agent Three; SIM-1 integrated at `1126d8c`); RQ-008 storage/worktree (Agent Five): audit + Phase 1 cache cleanup done; later phases need sign-off. **Partly done:** RQ-004 hardware BOM integrated at `42ac6f3` (evidence-based; blocked on Michael's physical facts — see the request at the end of `PILOT1_ROOM1_HARDWARE_INVENTORY.md`).

**ASSIGNED:** RQ-001 Demo data continuity (Agent Five, 2026-10-04).

**Update 2026-10-05:** SIM-4 Nursing accepted (`7446cc7`). RQ-008 Phase 2 deletions await Michael. RQ-002 waits on the `/realtime/aria-session` security fix and Michael's Aria governance decision.

**READY — next acceptance priority:** RQ-003 Live Nursing voice acceptance (dependency met at `1d02630`, 2026-10-02; needs Michael speaking to a room screen).

**WAITING:** RQ-002 Global Ask Aria; RQ-006 Pilot Room 1 provisioning.

**BLOCKED:** RQ-005 Live email / Resend acceptance.

No queued task was started by the work block that created this queue.
