# CAOSCare autonomous agent-team audit — 2026-10-07

**Scope:** read-only audit before structural changes requested by Michael.

## Canonical project / branch

- Repository: `caosos/CAOSCARE.COM`.
- Authorized Pilot 1 integration branch: `integration/2026-09-27`.
- Integration head observed from GitHub: `31b230b4632982a940d7c179b769ee01b04ddde7`.
- Protected integration checkout documented on the EliteDesk: `~/CAOSCARE-INTEGRATION`.
- Production/Linode is not part of this setup. No deployment is authorized.

## Existing coordination system

CAOSCare already has the pieces that must remain authoritative:

- `docs/PILOT1_READY_QUEUE.md` — approved bounded work.
- `docs/PILOT1_ACTIVE_WORK.md` — current lane/worker ownership and merge queue.
- `docs/PILOT1_EXECUTION_CHECKLIST.md` — acceptance tracker.
- `docs/PILOT1_RECOVERY_CHECKPOINT.md` — recovery/runtime snapshot.
- `docs/PROJECT_STATE.md` — append-only changing state.
- `pilot/agent-control-plane` / PR #67 — owner-only Agent Operations control-plane work.

Therefore the autonomous team must **extend these files and PR #67**, not create a second queue or a second control plane.

## Current control-plane state

PR #67 branch head before this audit: `87d8be39acabeb7575d58ba9f8fd893d6d0dc822`.

Already built on that branch:

- owner-only agent registry and command API behind `CAOSCARE_AGENT_CONTROL_ENABLED`;
- mock command → delivery → acknowledgment receipt chain;
- read-only Claude session discovery;
- Agent Operations frontend;
- backend/frontend tests previously reported green;
- no real-session command delivery.

Coordinator review on 2026-10-06 marked #67 **NEEDS FIX** because it was behind integration, the router/UI were not mounted, a mount patch was left as a side file, and live PID/session snapshots were embedded in the design document.

## Existing workers / runtime evidence

Last durable integration record (2026-10-06 15:10 CDT):

- Agent Six waiting on an approved security follow-up;
- Claude Two waiting on wake-sheet/runbook follow-up;
- Agents Three, Four and Five done/idle;
- control-plane PR #67 awaiting fixes;
- no worker activity had been observed since roughly 09:00 CDT.

The control-plane branch previously discovered interactive Claude sessions, but those PID/session mappings are runtime snapshots and are not treated as current truth here.

**This GitHub-connected audit cannot inspect the EliteDesk process table or tmux state directly.** Runtime start/verification must be performed on the EliteDesk and then recorded back into GitHub.

## Simulator / receipt state

- Operations Simulator SIM-1 through SIM-4 work is substantially integrated; Nursing SIM-4 was accepted.
- Integration includes canonical task lifecycle receipts/provenance and simulator identity/provenance.
- Core law remains: **No action without a receipt. No receipt without provenance.**
- Agent self-report is not proof.

## Deployment / safety restrictions preserved

- Do not deploy Linode/production.
- Do not merge protected/open PRs merely for convenience.
- Do not overwrite another active lane.
- Do not interfere with the facility's existing pendant/call-button path.
- Do not treat a worker's "done" message as acceptance evidence.
- Integration remains one reviewed lane/PR at a time with gates between merges.

## Gap to close

The missing operating behavior is the **persistent foreman loop**:

1. persistent workers that survive SSH disconnect;
2. Agent 1 permanently owns dispatch/integration;
3. workers publish branch-local status;
4. Agent 1 continuously reconciles worker status with the existing READY queue and ACTIVE board;
5. workers finish → test → receipt → push → status → claim the next compatible READY item;
6. blocked workers take another compatible task;
7. only genuine owner decisions escalate to Michael.

The implementation that follows this audit should add only those missing persistence/orchestration pieces and complete the mounting fixes already requested on PR #67.
