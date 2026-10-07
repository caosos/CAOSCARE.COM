# CAOSCare autonomous Agent 1 foreman loop

**Status:** ACTIVE orchestration contract requested by Michael on 2026-10-07.  
**Project:** CAOSCare only. Michael Business OS / Deal Sniffer is separate.  
**Integration authority:** `integration/2026-09-27`.

## Purpose

Michael should be able to walk away from the terminals. Agent 1 coordinates the build from durable repository truth, workers continue compatible work after finishing, and only genuine owner/product decisions come back to Michael.

This document **extends the existing Pilot 1 coordination files**. It does not create a second source of truth.

## Authoritative coordination state

Read and update these, in this order:

1. `docs/PILOT1_EXECUTION_CHECKLIST.md` — acceptance / finish line.
2. `docs/PILOT1_ACTIVE_WORK.md` — who owns what now.
3. `docs/PILOT1_READY_QUEUE.md` — approved bounded next work.
4. `docs/PILOT1_RECOVERY_CHECKPOINT.md` — recovery/runtime snapshot.
5. `docs/PROJECT_STATE.md` — dated changing state.
6. branch-local `docs/status/AGENT_STATUS.md` — each worker's own current claim/result.

GitHub is the durable communication bus. Terminal scrollback, Claude memory, screenshots and self-report are not authoritative.

## Existing team topology

Preserve the current six-agent identity instead of inventing a competing roster:

| Agent | Primary compatibility lane |
|---|---|
| 01 | permanent coordinator / integration / release gate |
| 02 | resident voice / wake / Aria / room voice endpoint |
| 03 | Operations Simulator / scenario / integration QA |
| 04 | Shared Core / state / receipts / provenance / lifecycle |
| 05 | Home Assistant / devices / room control / RF / hardware |
| 06 | security / operator surfaces / communications / cross-cutting hardening |

These are compatibility lanes, not permanent monopolies. Agent 1 may assign a bounded task across adjacent areas when file ownership is explicit and no active lane collides.

## Agent 1 loop — mandatory

Agent 1 does not passively WAIT while useful project work exists.

After startup and after every meaningful worker push:

1. `git fetch origin`.
2. Read every worker's branch-local `docs/status/AGENT_STATUS.md` when present.
3. Read the READY queue, ACTIVE board, checklist and current integration failures.
4. Verify dependencies against repository evidence, tests and receipts.
5. Mark newly unblocked work READY.
6. Resolve reversible technical questions without Michael.
7. Assign the highest-value compatible READY work to idle/finished workers.
8. Record assignment durably in the existing READY/ACTIVE files.
9. Nudge the dedicated tmux worker session to fetch and continue.
10. Review finished work from branch/diff/tests/receipt evidence.
11. Integrate one branch/PR at a time and run the gate between integrations.
12. Refill the queue from the real checklist/punch list when useful approved work is exhausted.
13. Repeat.

Do not invent speculative busywork merely to keep a worker occupied. If no useful compatible work exists, WAITING is correct and must state the dependency.

## Worker loop — mandatory

A worker never treats one completed task as the end of its session when compatible READY work exists.

```
CLAIM
→ IMPLEMENT
→ TEST
→ RECEIPT
→ COMMIT
→ PUSH
→ UPDATE AGENT_STATUS
→ CHECK READY QUEUE
→ CLAIM NEXT COMPATIBLE TASK
→ CONTINUE
```

If blocked: record the blocker and evidence, push the status, inspect READY work, claim another compatible task if one exists, and WAIT only when no compatible work is available or a real dependency blocks the lane.

## Queue claim semantics

CAOSCare already uses `ASSIGNED` in `PILOT1_READY_QUEUE.md`. For this system, **ASSIGNED is the durable equivalent of CLAIMED**. Do not create a second queue just to rename the state.

A claim identifies task ID, agent, branch/worktree, base integration SHA, start time, dependencies, acceptance condition and expected receipt/test evidence.

## Branch / worktree rule

Persistent **tmux session identity is separate from task worktree identity**.

Agent 1 owns the protected integration checkout. Agents 2–6 start in **separate persistent worker worktrees** created by `scripts/caos-agent-team` under `~/caoscare-agent-worktrees/agent-XX`. One worker, one worktree; never let two workers edit the same checkout.

The persistent worker branch is only a safe starting point. Before modifying code for an assigned task, the worker verifies a clean tree and creates or switches to the bounded task branch named by the queue, based on current `origin/integration/2026-09-27` unless the queue explicitly names another base. Reuse an existing appropriate task branch rather than duplicate it.

Agent 1 alone performs integration/coordination work in the integration checkout. Workers do not self-merge.

## Persistent sessions

Dedicated sessions are named `caos-agent-01` through `caos-agent-06`. Use `scripts/caos-agent-team`.

tmux solves SSH/session persistence. It does **not** replace the GitHub foreman loop.

Existing old interactive Claude sessions are historical runtime state; do not hijack them.

## Worker status contract

Each active task branch carries `docs/status/AGENT_STATUS.md`, based on `docs/status/AGENT_STATUS_TEMPLATE.md`.

Minimum fields: Agent/role, State, Task ID, Branch, Worktree, Base integration SHA, Started/updated, objective, tests/result, receipt/provenance, blocker, next compatible task or WAIT reason.

Agent 1 must never convert COMPLETE into accepted integration solely because a worker wrote COMPLETE.

## Agent-work receipts

Meaningful agent work needs durable evidence: agent identity, task ID, branch, base SHA, changed files, tests/results, commit SHA, source/provenance, dependency state and next state.

A PR plus tests is evidence; a chat sentence is not.

## Michael escalation rule

Agent 1 resolves reversible internal technical choices such as file layout, test organization, adapter shape, migration order and merge mechanics.

Escalate only genuine owner/product questions such as spending, production deployment, irreversible infrastructure changes, resident/staff policy, safety/authority boundaries and product behavior. Whenever practical, present one decision as YES / NO / MODIFY / HOLD.

## Control-plane relationship

`docs/CAOSCARE_AGENT_CONTROL_PLANE.md` and Admin → Agent operations provide observability and receipted control.

The Pilot queue/checklist remain the authority for **what should be built**. The UI must not invent or reorder project priorities.

`CAOSCARE_AGENT_CONTROL_ENABLED` remains EliteDesk-only and default-off elsewhere. Never enable it on Linode through this work.

## Persistence / reboot

- SSH or laptop disconnect: tmux sessions continue.
- EliteDesk reboot: tmux dies with the host; recover through the documented user-systemd unit or `scripts/caos-agent-team recover`.
- A boot-started user service requires user-systemd at boot; if linger is disabled, enabling it is a recorded host operation.
- Recovery never implies production deployment.

## Acceptance

Accepted only when host evidence proves:

1. tmux sessions 01–06 exist.
2. Sessions survive a full SSH disconnect/reconnect.
3. Workers read the same canonical READY/ACTIVE state.
4. At least two workers finish different non-overlapping tasks concurrently.
5. Each leaves tests + receipt + commit + pushed status.
6. Agent 1 observes completion and assigns the next compatible READY task without Michael relaying it.
7. A blocked worker records the blocker and takes another compatible task.
8. Agent 1 integrates one accepted branch, runs the gate and updates canonical state.
9. A controlled reboot proves the recovery path.
10. No production/Linode change occurs.
