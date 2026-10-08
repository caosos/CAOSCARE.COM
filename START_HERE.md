# CAOSCare START HERE

This is the canonical onboarding bootloader for humans and AI agents entering CAOSCare.

It is intentionally a **pointer map, not a doctrine copy**. The authoritative rules live in the files below. If another onboarding document gives a different read order, this file + `AGENTS.md` define the correct sequence and that other document must be corrected.

## Mandatory read order

1. `AGENTS.md` — mandatory agent protocol, safety, receipts/provenance, continuous-progress rule, change discipline.
2. `docs/CAOSCARE_PRODUCT_BASELINE.md` — canonical durable product truth and current architecture/invariants.
3. `docs/PROJECT_STATE.md` — recent changing build state and handoff capsules. Read the latest relevant entries; do not treat old entries as current truth.
4. `docs/REPO_MAP.md` — implementation/source orientation.
5. `docs/BUILD_STATUS.md` and `docs/CURRENT_NODE_STATUS.md` — point-in-time runtime/build snapshots; verify runtime directly when it matters.
6. `README.md` and `docs/CAOS_CARE_AGENT_ONBOARDING_CONTRACT.md` — product/context doctrine; where they conflict with the Product Baseline, the Product Baseline wins.
7. Task-specific contracts, TSBs, lane onboarding files, and acceptance docs.
8. Inspect the exact branch/ref, source, tests, and runtime relevant to the assigned task before making claims or changes.

## Lane overlays

After the mandatory sequence, load only the overlay needed for the task:

- Aria / voice / realtime / memory / conversation / operational-state work:
  `docs/ARIA_LANE_ONBOARDING.md`
- Operations Simulator:
  `docs/CAOSCARE_OPERATIONS_SIMULATOR.md`
- Pilot 1 execution:
  `docs/CURRENT_PRIORITY.md`
  `docs/PILOT1_EXECUTION_CHECKLIST.md`
  `docs/PILOT1_ACTIVE_WORK.md`
  `docs/PILOT1_READY_QUEUE.md`
- Room audio / Voice PE:
  `docs/ROOM_AUDIO_ARCHITECTURE.md`
  `docs/ARIA_WAKE_WORD_ARCHITECTURE.md`
- Shared operational service-layer changes:
  `docs/ENGINEERING_CONTRACT.md`
- Troubleshooting / known failures:
  `docs/tsb/INDEX.md` and the relevant TSB

Do not load every historical document by default. Load the canonical core plus the task-specific overlay.

## Truth hierarchy

When sources disagree, use this order:

1. Michael's latest explicit direction, once durably recorded
2. accepted ADR / binding contract for the affected scope
3. `docs/CAOSCARE_PRODUCT_BASELINE.md`
4. `AGENTS.md` for operating/safety/engineering rules
5. latest relevant `docs/PROJECT_STATE.md` entry
6. current source + tests + runtime evidence
7. point-in-time status docs
8. older historical docs

If an older document conflicts with a higher source, mark it historical/superseded or correct its pointer. Do not silently carry both versions forward.

## Shared-state rule

Everybody must be able to join cold and reach the same current truth.

Therefore:
- durable product truth goes in the Product Baseline / accepted contracts;
- changing state goes in PROJECT_STATE;
- implementation location goes in REPO_MAP;
- current work goes in Pilot 1 queue/active-work docs;
- consequential actions get receipts/provenance;
- lane-specific context goes in a lane onboarding pointer file;
- no required knowledge may exist only in a chat.

## Handoff rule

Before a worker/session exits, it must leave the handoff capsule required by `AGENTS.md` in `docs/PROJECT_STATE.md`, with branch/ref, proven state, commits, runtime state, unresolved defects, invariants, do-not-change boundaries, and next safe action.

## One-line onboarding rule

> Read START_HERE → AGENTS → Product Baseline → current Project State → Repo Map → runtime snapshots → your lane/task overlay → actual source/tests/runtime.

If a new onboarding file is created, it must point back to this file rather than inventing another boot sequence.
