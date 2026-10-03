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

## Seeded queue

| ID | Priority | Task | Intended lane | Dependencies | Exact definition of done | Safe-to-start condition | Status | Originating Michael decision / requirement | Resulting branch / SHA |
|---|---:|---|---|---|---|---|---|---|---|
| RQ-001 | 2 | Demo data continuity | Demo data continuity / Lane G-adjacent bounded worker | Current Demo kiosk work `pilot/demo-kiosk@0b69cae` must be integrated or coordinator must prove file ownership does not overlap. Strict separation from real resident data. | Returning to the demo after elapsed time shows a believable current community state instead of hundreds of frozen stale requests: `last_simulated_at`; background progression when available; deterministic catch-up on login/startup; old simulated work progresses realistically; completed work moves to history; unresolved work stays bounded; plausible new/current simulated state; real resident data is never touched. | Start only after Demo kiosk is accepted/integrated **or** the coordinator explicitly proves a non-overlapping branch/file boundary. | READY | Michael approved demo continuity so the simulated staff dashboard behaves as though time passed while nobody was logged in. | — |
| RQ-002 | 3 | Global Ask Aria | Resident/public experience worker; Shared Core owns any shared contract change | Stable governed Aria/auth/page contracts; no collision with current Shared Core or Demo kiosk integration. | Appropriate CAOSCare pages have a persistent bottom-right Ask Aria entry point using the **same governed Aria**, page-aware and product/workflow-aware, with text plus realtime/full-duplex voice where supported; click requires no wake word; authenticated pages are permission-scoped; public pages expose no private resident data; actions/status are truthful; opening/closing preserves current page/context. | Start only after the coordinator confirms the current Shared Core + Demo kiosk integration has stabilized the reused Aria and page contracts and no shared contract must be independently redefined. | WAITING | Michael approved a persistent Global Ask Aria entry point; it must not become another chatbot. | — |
| RQ-003 | 1 | Live Nursing voice acceptance | Nursing / care requests | Shared Core status-truth fixes must be integrated and verified first (SC-3 status truth is the explicit blocker). | Through actual resident Aria voice, “I need help going to the bathroom.” proves request → nursing → staff lifecycle → later spoken status truth. | Shared Core status-truth fix integrated on `integration/2026-09-27`, gates pass, and coordinator re-checks claim/status truth. | READY | Michael requires the accepted Nursing loop to be proven through actual resident Aria voice. | — |
| RQ-004 | 1 | Pilot hardware inventory | Hardware / Pilot Room inventory worker | Physical-model evidence may be needed for devices whose exact make/model/protocol is not recorded. | One exact Pilot Room hardware BOM identifies owned vs needed items and exact protocol/compatibility for wireless thermostat, wireless bulbs, smart plugs, TV/model, eMeet/audio, RF receiver, pendant/button equipment, room node, network requirements, IR requirement, and ATA/handset/front-desk SIP hardware requirement. No guessed model numbers or protocols. | **May start now** from repo/hardware evidence. Inventory what is proven; consolidate unknown physical model numbers into one request. If the missing physical evidence prevents further progress, change this item to BLOCKED rather than guessing. | READY | Michael requires an exact Pilot Room BOM before provisioning. | — |
| RQ-005 | 1 | Live email / Resend acceptance | Communications / calling | External provider/domain configuration, real inbound addresses, sender allowlists, and real department destinations are required. SC-8/request-linked notification work must be integrated as applicable. | Verified sending/domain configuration; inbound menu address; inbound activities address; sender allowlists; real department addresses; real nursing, maintenance, and transportation notifications; delivery/bounce state; request-linked notification receipts; real inbound and outbound paths acceptance-tested. | Start acceptance only when the required real provider/domain/address configuration is available and the request-link contract is integrated. | BLOCKED | Michael requires real inbound/outbound email acceptance, not logged/simulated delivery. | — |
| RQ-006 | 1 | Pilot Room 1 provisioning | Pilot Room provisioning | Operational core sufficiently integrated; exact room hardware BOM; wake/voice path; required device adapters; calling hardware/path as required for Pilot 1. | First real resident room operates under normal use without SSH babysitting and survives reboot and network interruption/recovery. | All listed dependencies accepted enough for a real-room install and coordinator assigns the room/provisioning lane. | WAITING | Michael requires the first real resident-room installation for Pilot 1. | — |

## Current queue summary

**READY:** RQ-001 Demo data continuity (Demo kiosk integrated at `239324a`, 2026-10-02; strictly separate from real resident data); RQ-003 Live Nursing voice acceptance (dependency met at `1d02630`, 2026-10-02; needs Michael speaking to a room screen); RQ-004 Pilot hardware inventory.

**WAITING:** RQ-002 Global Ask Aria; RQ-006 Pilot Room 1 provisioning.

**BLOCKED:** RQ-005 Live email / Resend acceptance.

No queued task was started by the work block that created this queue.
