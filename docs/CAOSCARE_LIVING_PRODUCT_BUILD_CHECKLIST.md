# CAOSCare — Living Product Build Checklist

Updated: 2026-10-12 (06:10 CDT; alert close-out receipts ACKED / WORKING).

This is the owner-facing product build and progress tracker for the Care Operations build. Canonical owner direction: [Issue #129](https://github.com/caosos/CAOSCARE.COM/issues/129). Detailed historical evidence remains in [PILOT1_EXECUTION_CHECKLIST.md](https://github.com/caosos/CAOSCARE.COM/blob/integration/2026-09-27/docs/PILOT1_EXECUTION_CHECKLIST.md). This file controls current phase, active task, milestones, ETA, blockers, and the reporting contract.

**Do not mark a feature DONE because code exists or an agent says it is done.** Track these states separately:

- **PLANNED** — requirement captured; no accepted implementation.
- **IMPLEMENTED** — code exists at an exact commit.
- **TESTED** — automated checks passed with a receipt.
- **DEV_ACCEPTED** — intended user completed the workflow in the development runtime with receipt/provenance evidence.
- **LIVE_VERIFIED** — the deployed environment was exercised successfully and the exact deployed SHA is recorded.
- **READY_FOR_OWNER_REVIEW** — the whole bounded section meets its written acceptance criteria and is presented to Michael.
- **OWNER_ACCEPTED / DONE** — Michael inspected the completed section and explicitly approved it.
- **BLOCKED** — a named dependency prevents the next acceptance gate.
- **PARKED** — deliberately outside the active lane.

## Checklist marks and owner approval

- `[ ]` — not completed.
- `[~]` — work or evidence exists, but the item/section is not owner-approved DONE.
- `[!]` — blocked by a named dependency.
- `[x]` — Michael has reviewed and approved the completed item/section.

Existing evidence may support IMPLEMENTED, TESTED, DEV_ACCEPTED, or LIVE_VERIFIED without making the section `[x]`. The final checkmark is the owner acceptance record.

## Completion/update protocol

This protocol applies to every bounded build item, fix, workflow, and section.

1. **Select from the living checklist.** Record the active item, expected acceptance, branch/PR, dependencies, and ETA range before or when work begins.
2. **Build without routine permission stops.** Implementation, tests, integration, deployment, restarts, repair, and verification continue within existing authority.
3. **At every meaningful completion, update records before advancing.** A meaningful completion is a finished bounded task, accepted fix, merged PR, deployment, or completed acceptance case—not every keystroke or tiny commit.
4. **The completion update must record:** exact commit/PR/deployed SHA; tests; development and live acceptance; receipt IDs/provenance; changed checklist item; blocker if any; next bounded task; updated ETA; and whether owner review is ready.
5. **Update the existing sources of truth together:** this checklist, the active issue/queue, the applicable project-state or acceptance receipt, and PR/commit links. Do not create an unlinked parallel status record.
6. **Preserve history.** Do not delete prior DONE entries, failures, blockers, owner decisions, or superseded evidence. Append or clearly supersede with a dated reason.
7. **Section gate:** when every required item in a section meets its acceptance criteria, mark the section **READY_FOR_OWNER_REVIEW** and present the actual usable workflow to Michael with the exact URL/environment and a concise evidence summary.
8. **Michael reviews the completed section.**
   - If Michael approves it, record the approval date and evidence, change the section/items to `[x]`, mark **OWNER_ACCEPTED / DONE**, and advance to the next section.
   - If Michael does not approve it, record the punch list, keep the section `[~]`, and make the first correction the active task.
9. **No silent advancement.** A section is not DONE and is not checked off solely because code, tests, a PR, a merge, or a deployment exists.

## No-idle execution protocol

- An agent that finishes a bounded task must produce its completion receipt and accept the next eligible task immediately.
- An agent that becomes blocked must record the exact blocker and take another compatible, authorized task.
- The coordinator keeps the next bounded task prepared before the current task finishes.
- Idle is permitted only when every authorized task is blocked, unsafe, conflicting, or awaiting a genuine owner decision; the reason must be recorded.
- No invented busywork, duplicate worker, duplicate queue, or conflicting edit is allowed merely to keep an agent occupied.
- GitHub activity is not a process heartbeat. The EliteDesk local coordinator/watchdog must enforce the five-minute idle-detection and next-task handoff target and publish timestamped receipts.
- The hourly cloud supervisor is a backup reconciliation layer; PR Watch handles matching GitHub PR events. Neither is represented as a five-minute host watchdog.

## Escalation and recovery protocol

This is the required path whenever an agent, coordinator, watchdog, service, or automation needs something.

1. **Create a `NEED` receipt immediately.** It must include: project; task/section; timestamp; exact blocker; classification (`NEED_SERVICE`, `NEED_ACCESS`, `NEED_PERMISSION`, `NEED_HOST_ACTION`, or `NEED_OWNER`); exact requested action or one copyable command; impact; evidence; what compatible work continues; and next check time.
2. **Route it through the existing control channel.** CAOSCare uses Issue #129; Desktop Agent uses Issue #3; Deal Sniffer uses its existing liaison/READY_QUEUE path. Do not invent a parallel queue.
3. **Keep working.** A blocked agent takes the next compatible authorized checklist item. The coordinator may wait only when every useful authorized item is blocked, conflicting, unsafe, or requires a genuine owner decision.
4. **Use standing authority.** Routine builds, tests, integration, verified deployments already authorized for that project, necessary service restarts, repairs, and verification do not become new owner questions merely because an agent reached them.
5. **Escalate with a fix.** A service/host problem must include the recovery command or action and a verification check. A permission/access problem must identify the exact permission or credential required. Never send Michael only a problem statement.
6. **Receipts close the loop.** Required states are `DELIVERED → ACK → WORKING → DONE`, or `BLOCKED/NEED` with continued compatible work. After recovery, record the loaded revision, service/process identity, port/health checks, and next-task handoff.
7. **Cloud and host layers stay distinct.** The EliteDesk watchdog targets detection and handoff within five minutes. Hourly ChatGPT supervisors reconcile GitHub/checklist truth and notify this chat. PR watches react to GitHub PR events. None may claim another layer is alive without its receipt.
8. **Slack escalation target.** Actionable NEED receipts should also be mirrored to `#all-ask-aria` when the ChatGPT Slack app is installed and present there. Until that event trigger is verified, the project issue plus hourly supervisor remains the delivery path.

## ETA-driven checks and exception alerts (owner addendum, 2026-10-11)

Source: Issue #129 comment 6115336898. Governing rule: "No action without a receipt. No receipt without provenance."
Executable form: `scripts/owner_intake/eta_receipts.py` (schema, rules, CLI) and `heartbeat_probe.py` (the local watchdog's
check); tests `scripts/owner_intake/tests/test_eta_receipts.py`.

1. Every **ACK / WORKING** carries project, task_id, owner, stage, evidence reviewed, a realistic ETA (from the real scope:
   tests, browser run, deploy steps, host conditions), an exact `next_check_at` in America/Chicago, the acceptance evidence
   expected, and the blocker or NONE. The CLI refuses a receipt missing any of them or with a time without a timezone:
   `python3 scripts/owner_intake/eta_receipts.py WORKING --in-minutes 40 -f project=CAOSCare -f task_id=… -f owner=… -f stage=… -f evidence=… -f eta=… -f acceptance=… -f blocker=NONE`
2. The existing local watchdog owns the timer: the probe prints `next_check_at` and wakes the coordinator when it arrives.
   No other coordinator, worker, queue, watchdog or monitor.
3. At `next_check_at` exactly one of: **WORKING** (evidence, progress, revised ETA, new `next_check_at`); **DONE** (commit,
   tests, browser/review evidence, loaded revision, host observation, user-visible result, cost if known, timestamp, next
   item); **NEED / BLOCKED** (blocker, exact action or command, impact, compatible work continuing, next check).
4. Finishing early: publish **DONE** immediately and take the next eligible item; do not wait for the check.
5. A missed ETA or check is an exception, recorded with provenance as "APPEARS STALE — HOST STATE UNVERIFIED" unless host
   evidence proves more. Never claim a worker stopped without host evidence.
6. Michael is notified only for: DONE needing owner acceptance; NEED / BLOCKED; missed ACK, ETA or check; failed test,
   delivery, deployment or recovery; a genuine owner decision; a material cost or authority boundary. Not for healthy
   routine progress or already-granted build authority.
7. The cloud supervisor stays the hourly fallback; GitHub activity is not proof a host process is alive.
8. Projects stay isolated: misdelivered work is quarantined and routed, never executed here.

## Current build control

- **Current phase:** 3/7 — Care Operations workspaces.
- **ONE current bounded task:** `careops-alerts-close-receipts-001` — ACKED / WORKING through existing coordinator `caoscare-1-ee` and worker `da-6b6a0ace12`. The worker confirmed that resolve ignores legacy `escalated`, close can re-close and overwrite resolution provenance, and `_close_out` produces actor-less, unlinked receipt updates. It will add failing tests first, then unify resolve/close on one guarded active/acknowledged/escalated → resolved transition with exactly one actor/authority/before/after receipt and linked history entry; repeat/concurrent attempts will yield one winner and 409 for the rest without writes. ETA approximately Monday, October 12, 2026 — 7:23 AM America/Chicago; existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 7:23:11 AM America/Chicago; blocker NONE.
- **Control issue / dispatch channel:** [#129](https://github.com/caosos/CAOSCARE.COM/issues/129).
- **Completed review:** [PR #130](https://github.com/caosos/CAOSCARE.COM/pull/130), merged into integration.
- **Integration branch:** `integration/2026-09-27`; current accepted therapy-conflict product commit `77f83d3d53e17ffb75c71d137ab876e50552efe9` with guarded dev restart `1bf1bec26ea58a6c55730fea3c858734eb788d54`. This later integration work is not in production `ff87c22`; the release baseline is separate.
- **Transportation implementation:** `agent/transport-workspace-workable` at `21b2261f021d152181c94d8c95d006c533b18529`; integration merge `dc2e4ca1ba22aa6a0e81b950f5597f83a9b4c4ba`.
- **Accepted state:** IMPLEMENTED, TESTED, and DEV_ACCEPTED with receipt-backed browser evidence.
- **Not yet accepted:** authenticated production Transportation browser/receipt verification. `main` and production were observed at `ff87c22`; production deploy completed 21:28:50Z with backup `20261011-212802-pre-deploy-d7ff96a4e4d1`, independent bundle/service check, and 12/12 public smoke. This is a dated observation, not a current process heartbeat.
- **Coordinator task:** existing `caoscare-1-ee` owns `careops-transport-live-001`. Issue #129 comments 6113952748 and 6114006820 were delivered as `da-3995f8741b` and `da-a8f3b8ea5f`; explicit ACK/WORKING remains unverified in Issue #129. A dated production deploy receipt exists in PROJECT_STATE; the former main-push and deploy blockers are stale.
- **Current host observation:** PROJECT_STATE records a Linode deployment and independent service check at 21:28:50Z (16:28:50 CDT). No newer local coordinator heartbeat or authenticated Transportation browser receipt is available in Issue #129; current host liveness is UNKNOWN. Michael's 16:27 CDT screenshot is historical point-in-time coordinator evidence.
- **Owner decision required now:** none established. Routine build, promotion, exact-SHA deployment, restarts, tests and repair are already authorized. A GitHub tool consent prompt is separate from a Care App owner decision.
- **Authority reconciliation:** comment `6105970504` records that the later explicit owner authorization in Issue #129 and current PR #130 supersedes the original pre-acceptance no-deploy note. Do not ask Michael to approve the same release again.
- **Recovery evidence:** Desktop-Agent main `14aa2da70933118631a92631f511648de6788e8c` provides five-minute unacked detection and redelivery; controlled recovery evidence is in Desktop-Agent comment `6106188802`. CAOSCare commit `58010c2ed6796ab1bb9245f642fa16cfc5a12af8` repairs the heartbeat probe (11 owner-intake tests passed; live `coordinator_state.py` exits 0). The last proven ACK/WORKING on the retired coordinator is historical, not current liveness.
- **Slack liaison checkpoint:** scanned through `1791754656.483969` (16:37:36 CDT); newer messages were Deal Sniffer-only and were not acted on as CAOSCare work. Care App checkpoint posted at `1791755715.385529` (16:55:15 CDT), linked to Issue #129 comment `6114212326`.

### Update 2026-10-11 07:05 CDT (therapy ride link DEV_ACCEPTED; operational appointment details dispatched)

- **Completion receipt — `careops-therapy-transport-link-001`:** DEV_ACCEPTED on integration product commit [`7af6a0a4484d0f0dcd422f0e2019fe79287fb0dc`](https://github.com/caosos/CAOSCARE.COM/commit/7af6a0a4484d0f0dcd422f0e2019fe79287fb0dc). It reuses the ordinary transportation request engine from the canonical therapy StaffTask: Ride creates or attaches exactly one same-day request, records bidirectional IDs and provenance-linked receipts, follows reschedule/cancel, and remains idempotent while open. No second appointment or transportation store was added.
- **Gates:** backend 539 passed / 0 failed / 31 skipped; frontend 70 suites / 564; production build compiled. Isolated scratch acceptance passed 15/15 with zero failed API calls and zero page errors: plan → request/attach one ride → transportation calendar and resident Home visibility → idempotent re-ask → reschedule propagation → cancellation propagation → existing-ride attachment → completion leaves the ride open → 390 px clean. Canonical report: [`docs/reports/2026-10-11-therapy-ride-link-acceptance.md`](https://github.com/caosos/CAOSCARE.COM/blob/integration/2026-09-27/docs/reports/2026-10-11-therapy-ride-link-acceptance.md) (blob `2dceea207730b304fcc0da5f1e677412435407c1`).
- **Runtime receipt:** guarded development backend restart recorded by [`3d8c8d462b46d9334f88d7cf3c74765a173aa972`](https://github.com/caosos/CAOSCARE.COM/commit/3d8c8d462b46d9334f88d7cf3c74765a173aa972): old PID 432927, new PID 456493, zero leases, clean tree, runtime `7af6a0a`, log `/tmp/room214_backend_7af6a0a.log`. Development only; `main` remains `880d10f` and production remains `d7ff96a`.
- **Verdict:** this bounded ride-link slice is DEV_ACCEPTED, not LIVE_VERIFIED and not OWNER_ACCEPTED / DONE. Therapy/appointments is still not READY_FOR_OWNER_REVIEW because provider/discipline, location, recurrence, permission boundaries, conflict detection/date-ordered schedule, and complete staff/resident acceptance remain open.
- **Next single bounded task:** `careops-therapy-details-001`. On the existing therapy StaffTask only, add optional operational provider name, discipline, and appointment location; authorize create/edit/read appropriately; receipt before/after changes; show the truthful details in the therapy queue, resident-facing schedule/Home, and Aria/status path where applicable. Prove create → edit → reschedule → resident/staff visibility and unauthorized refusal with focused tests and one isolated browser run. Do not add clinical diagnosis/chart data, a provider registry, recurrence, billing, external messaging, audio, paid service, production deployment, or a new truth store.
- **Control evidence:** GitHub exposes no legacy combined-status contexts and no PR-triggered workflow runs for `7af6a0a`; the recorded local automated/build/browser gates are the applicable acceptance evidence. PR #130 remains merged and unchanged.
- **Receipt discipline:** committed work proves the existing coordinator executed `da-5ee2bb4526`, but explicit issue ACK/WORKING/DONE remains missing. The next task must close that protocol gap. Issue delivery `da-f616017117` contains the Deal Sniffer watcher receipt and is quarantined as cross-project context; do not execute it as CAOSCare work.
- **Slack cursor:** processed through `1791718151.045669`; all newer inputs were Deal Sniffer-only. CAOSCare then posted the completion/dispatch ACK at `1791720529.563279` with Issue receipt `6108860768`. No CAOSCare liaison input and no owner action.

### Update 2026-10-11 05:52 CDT (therapy appointment DEV_ACCEPTED; transport link dispatched)

- **Completion receipt — `careops-therapy-appointment-001`:** DEV_ACCEPTED on integration product commit [`47674f5329500e9fbb508cca01b5bc1d98906df9`](https://github.com/caosos/CAOSCARE.COM/commit/47674f5329500e9fbb508cca01b5bc1d98906df9). The implementation deliberately uses the canonical `StaffTask` in department `therapy`, with `requested_for_date` / `requested_for_time_label`; it adds the shared department queue, Plan/reschedule, reason-required cancel, resident visibility for front-desk-originated requests, and the spoken-window fix. No parallel appointment model was added.
- **Gates:** backend 538 passed / 0 failed / 31 skipped; frontend 68 suites / 561; production build compiled. Isolated scratch acceptance (`caoscare_therapy_acc`, providers blank) passed 21/21 with zero failed API calls: front desk create → therapy queue → plan → reschedule → resident/Aria/Home visibility → claim/start/complete, plus reasoned cancellation and one provenance-linked receipt chain. Canonical report: [`docs/reports/2026-10-11-therapy-appointment-acceptance.md`](https://github.com/caosos/CAOSCARE.COM/blob/integration/2026-09-27/docs/reports/2026-10-11-therapy-appointment-acceptance.md) (blob `803a396d4d58eff61785555e9acc9c5294dfb273`).
- **Runtime receipt:** guarded development backend restart recorded by [`d0718e2b31847b5cf12c50604dcec00b634d638c`](https://github.com/caosos/CAOSCARE.COM/commit/d0718e2b31847b5cf12c50604dcec00b634d638c): old PID 401682, new PID 432927, zero leases, clean tree, runtime commit `47674f5`, log `/tmp/room214_backend_47674f5.log`. Development only; `main` remains `880d10f` and production remains `d7ff96a`.
- **Verdict:** the bounded therapy appointment slice is DEV_ACCEPTED, not LIVE_VERIFIED and not OWNER_ACCEPTED / DONE. The broader coordinated-schedules section is not READY_FOR_OWNER_REVIEW because linked transportation, recurrence, and provider/discipline remain outside this completed slice.
- **Next single bounded task:** `careops-therapy-transport-link-001`. Inspect and reuse the existing transportation request path. From one synthetic therapy task, create or attach exactly one ordinary transportation request when a ride is marked needed; preserve idempotency, bidirectional identifiers or canonical relation, authorization, status visibility, and provenance-linked receipts; verify plan/reschedule and cancel/complete behavior in an isolated stack and browser. Do not create a second transportation engine or appointment truth store. Stop before recurrence, provider/discipline, billing, external messaging, audio, production deployment, paid service, or real-data mutation. Required receipts: explicit ACK/WORKING, exact implementation SHA, automated gates, browser cases, failures/repairs, and DONE/NEED.
- **Dispatch delivery:** Desktop Agent delivered `da-5ee2bb4526` to the existing `caoscare-1-ee` session at 05:56:01 CDT (Issue comment `6108288104`). Awaiting explicit `ACK da-5ee2bb4526` / `WORKING careops-therapy-transport-link-001`; do not create another coordinator or worker.
- **Control evidence:** GitHub reports no legacy combined-status contexts and no pull-request-triggered workflow runs directly attached to `47674f5`; the recorded local backend/frontend/build/browser gates are therefore the acceptance evidence. Delivery comments `6107685098` and `6107910794` did not receive explicit issue ACK/WORKING/DONE; work product proves execution, but the new task must close that receipt gap.
- **Slack cursor:** input processed through `1791715716.977699`; the latest input was a Deal Sniffer cross-project ACK only. CAOSCare posted the completion/dispatch ACK at `1791716142.179459` with Issue receipt `6108284581`. No new CAOSCare liaison instruction and no owner action is required.

### Update 2026-10-11 04:38 CDT (callback accepted; prompt scope corrected; therapy slice dispatched)

- `careops-frontdesk-callback-001` is acceptance-complete on the existing dev stack with no new product code: 19/19 cases, 0 failed API calls, 0 console/page errors. It proved front-desk callback create → department route → assign/unassign/claim → acknowledge → start → note → complete → explicit reopen → second complete; one workflow receipt chain; department scoping; 390 px rendering. Baseline `ce6c10b`; report blob `84df89048c410c0035812c7f5258588a2b2c050d`. Reassignment to another front-desk colleague and the administrator half remain unaccepted because the dev stack has one front-desk account and no available admin sign-in. This is DEV_ACCEPTED, not OWNER_ACCEPTED / DONE and not deployed.
- The prior “option 2 / auto mode” host instruction is superseded. The exact blocked operation was a read-only SSH query to `caoscare-prod` running `mongosh` counts for users by role, transportation staff, drivers, vehicles, residents, and open tasks. Prompt: **1 Yes once; 2 do not ask again for `ssh *`; 3 No**. Existing authority covered the one query, so **option 1 only** was appropriate. Option 2 widened approval and was unnecessary. The callback completed afterward; no host action is currently required.
- Single next compatible task: `careops-therapy-appointment-001`. Reuse canonical appointment/task/receipt records to implement or accept one labelled synthetic, non-recurring therapy appointment from staff creation through resident/staff schedule visibility, one reschedule, attendance completion or cancellation, and linked receipts. If transport is required, link the existing transportation-request path rather than copying it. Exclude recurrence, provider billing, external messaging, audio, paid services, and production deployment from this slice.
- Coordinator receipt compliance remains incomplete: work product proves execution, but Issue #129 lacks explicit callback `ACK/WORKING/DONE`. The therapy task must publish timestamped ACK/WORKING within five minutes or a structured NEED while compatible cloud-safe reconciliation continues.
- Slack cursor advanced through `1791711030.763209`. Next check: 05:20 CDT.

### Update 2026-10-11 04:19 CDT (reopen completion reconciled; next compatible task prepared)

- `careops-frontdesk-reopen-001` is complete on integration: feature `04cc580`, acceptance/report commit `ce6c10b`; backend 537 passed / 31 skipped / 0 failed, frontend 67 suites / 557 tests, production build compiled, development backend restarted on `ce6c10b`, and headless front-desk acceptance passed 23/23 including reopen → second completion with an unbroken receipt chain. This is DEV_ACCEPTED, not OWNER_ACCEPTED / DONE and not deployed.
- The single next compatible bounded task is `careops-frontdesk-callback-001`: use the existing canonical StaffTask/Receipt path to create a labelled synthetic resident callback, route it to one department, assign/reassign, add a note, complete, reopen once, and verify responsive front-desk UI history plus the linked receipt chain. No external email/SMS/phone call, no audio, no new record universe, and no admin/owner sign-in.
- Host handoff is degraded: `da-616acc5b05` was delivered to `caoscare-1-ee` at 04:08:01 CDT with no visible ACK/WORKING by 04:19 CDT. Exact recovery is to resume the existing CAOSCare Claude screen and approve its pending read-only command (option 2 / auto mode); do not create another coordinator. Cloud-safe records and dispatch continue through Issue #129.
- Slack input is processed through `1791707399.060289`; no newer liaison message was present. Dot Arya’s Desktop Agent routing-recovery request remains quarantined. The suspected working-directory fallback is an unconfirmed hypothesis until Desktop Agent inspects the loaded service and proves the intended recipient.
- Next check: 05:20 CDT. If the existing coordinator has not ACKed by then, preserve this NEED_HOST_RECOVERY and continue cloud-safe reconciliation without duplicate dispatch.

### Update 2026-10-11 03:20 CDT (Slack follow-through and no-idle fallback)

- Shared liaison thread processed through TS `1791703576.527529`; named CAOSCare ACK posted at TS `1791706917.729779`. Canonical dispatch receipt: Issue #129 comment `6107083640`.
- Latest actual repository evidence is integration head `49bb218b0aa7a915cf5d933b85b365769f3f5cde` at 03:02:17 CDT. It records the owner's direct release authorization, successful exact-candidate gate, and the refused deploy attempt. This is not proof of a live process heartbeat after that time.
- Transportation remains IMPLEMENTED, TESTED, and DEV_ACCEPTED; `main` remains `880d10f07e21a8572eec9a5f68771c42eba0eabe`; production remains reported at `d7ff96a`. Promotion, exact-SHA deployment, and LIVE_VERIFY remain incomplete.
- NEED_PERMISSION / NEED_HOST_ACTION remains: the coordinator classifier refused the main push, deployment SSH, and GitHub receipt command; live acceptance also needs an authenticated owner/admin browser session and driver/vehicle choice. Michael is unavailable tonight. No new authorization decision is required.
- No-idle fallback dispatched to the existing `caoscare-1-ee` coordinator only: `careops-frontdesk-reopen-001` — add and accept reopening a completed Front Desk request with truthful lifecycle state, linked receipts, focused API/UI tests, and synthetic browser evidence. If already claimed elsewhere, the coordinator must not duplicate it and must name the next unclaimed Front Desk/Admin checklist item.
- Automatic completion-to-next-task remains unproven; prior handoff required manual recovery. The next receipt must be timestamped `ACK` / `WORKING`, or a structured NEED if Desktop-Agent delivery is unavailable.
- Cross-project route contamination is now proven: Desktop-Agent Issue #3 comment `6106927226` delivered Desktop Agent item `da-601704c864` to CAOSCare coordinator `caoscare-1-ee`. CAOSCare quarantined it at Issue #129 comment `6107092750`; repair ownership was cross-referenced to Desktop Agent at its Issue #3 comment `6107092837`. Until exact-project routing is re-verified, GitHub Issue #129 remains the canonical CAOSCare dispatch and wrong-project `da-*` work must not be executed here.

### Update 2026-10-11 01:24 CDT (coordinator route recovery)

- The prior checklist statement that Front Desk/Admin acceptance was WORKING is corrected: the outgoing coordinator's handoff records that the slice never started and nothing was in flight.
- The current coordinator is `caoscare-1-ee`. Desktop Agent was still pinned/resolving deliveries to `caoscare-integration-b2`, causing the five-minute ACK failure.
- Desktop-Agent project-package pin is corrected on `main` at `2ccb63f1f86a63dd4af63222ddb6f3e06a4cee26`. Host activation still requires one fast-forward and service restart command recorded above.
- Cloud-safe compatible work completed: the CAOSCare heartbeat probe repair is on integration at `58010c2`; its receipt reports 11 tests passed and a successful live `coordinator_state.py` read.
- No release authorization decision is pending. After the routing restart produces `DELIVERED → ACK → WORKING` from `caoscare-1-ee`, resume `careops-transport-live-001`; if Linode access is genuinely unavailable, record the exact dependency and take the Front Desk/Admin normal-work acceptance slice.

### Update 2026-10-11 (EliteDesk, coordinator handoff and release gate)

- Coordinator role moved to a new session by Michael's direction (handoff capsule `docs/status/COORDINATOR_HANDOFF_2026-10-11.md`); Michael then gave direct owner authorization in that session: promote `ff87c22` to `main`, deploy the exact SHA, LIVE_VERIFY Transportation, then Front Desk/Admin.
- Release gate on a clean checkout of `ff87c22` (no local edits, shared venv, isolated port 8131 / DB `caoscare_gate_ff87c22`): backend `scripts/run_backend_tests.sh` 536 passed / 31 skipped / 0 failed (13 real_hardware deselected, 263 s); frontend 66 suites / 553 passed; production build compiled. `main` (`880d10f`) is an ancestor of `ff87c22` (fast-forward, 555 files); the only dependency change is `websockets>=14.0`; frontend deps unchanged; no manual data migration identified.
- Watchdog repair: `scripts/owner_intake/heartbeat_probe.py` no longer crashes on string worker rows in `docs/status/COORDINATOR_STATUS.json` (`58010c2`, 11 tests).
- 2026-10-11 ~08:00Z: Michael gave the owner authorization in the coordinator session (promote `ff87c22`, deploy, LIVE_VERIFY with live data, then Front Desk/Admin) and posted the coordinator ACK/WORKING receipt himself (#129 comment `6106922610`). His first deploy attempt was refused by the deploy script because `main` was still `880d10f` (the push had not run); production untouched (`d7ff96a`, no backup taken, nothing checked out). Production has one user account (owner) and no transportation staff, drivers or vehicles, so the live Transportation check needs his sign-in and at least one driver/vehicle (real or labelled demo, his choice).
- BLOCKED (tooling, not authority): the coordinator session's auto-mode permission classifier refused `git push origin ff87c22:main`, `ssh caoscare-prod` (deploy), and `gh issue comment` despite the owner's authorization. NEED: Michael runs the two commands (`git push origin ff87c22:main`; on the server `./scripts/deploy_caoscare.sh ff87c22df1dd69b405fa0ec60429c20fe72f6801`) or adds allow rules for them, plus a signed-in caoscare.com owner session in Chrome for LIVE_VERIFY. Production remains `d7ff96a`.

### Update 2026-10-10 (EliteDesk, receipts)

- **PR #130 merged into the local integration line** (merge of `21b2261`; no conflicts) on top of the 2026-10-10 My-rides work. **DEV_ACCEPTED, silently, no audio.**
- Tests on the merge: backend gate 536 passed / 0 failed / 31 skipped (port 8137, includes the extended Transportation lifecycle test); frontend 66 suites / 553 tests; `CI=true yarn build` compiled.
- Dev backend restarted with `scripts/restart_dev_backend.sh` on the merge commit (`dc2e4ca`; 0 leases; log `/tmp/room214_backend_dc2e4ca.log`).
- Browser (localhost:3000, signed in as the synthetic Transportation staff user "Demo - Pete Nash", `/workspace`): New ride (resident picker, purpose, appointment time as said) saved to "Needs coordination" -> Assign (pickup 13:15, confirmed with the demo driver/van) -> Open trip details (Change, Cancel, History) -> Change (moved to 14:02; the emptied 13:15 run shows Cancelled) -> Cancel with a reason. A second ride: Departed then Ride completed.
- Receipts for the first ride (`task_66caca092bf7`): `rcpt_60f8629f568e` requested, `rcpt_2906672ace84` booked, `rcpt_330f78904ce3` changed, `rcpt_d2946735dc6f` cancelled. Second ride (`task_2f7979e53135`): requested `rcpt_b54c68c74202`, booked, departed, completed. All real-human, identity authenticated, authority `acts_for:transportation`, channel `staff_ui`.
- Observations (not defects): the task's own `source` stays `front_desk` for staff-entered rides because Aria's ride-status lookup reads that value; the receipt channel is `staff_ui`. "My tasks today" refreshes every 10 s, so a just-completed ride can show for a few seconds.
- **Development result:** pushed to `integration/2026-09-27` and DEV_ACCEPTED. Not promoted to `main`, not deployed to Linode, and not live-browser verified. There is no remaining authorization ambiguity: Issue #129 explicitly permits the release path. Transportation remains `[~]` until LIVE_VERIFIED and Michael's owner review.

### Exact current sequence

0. Activate Desktop-Agent commit `2ccb63f1f86a63dd4af63222ddb6f3e06a4cee26` on the EliteDesk, restart `desktop-agent.service`, and prove `DELIVERED → ACK → WORKING` from coordinator `caoscare-1-ee` within five minutes.
1. Confirm `f35b4542a1b893357c78c21c4a7c4ce936fd8cff` is still the integration release candidate and record any drift from `main`.
2. Run the release regression gate on the exact candidate; do not substitute earlier branch-only results.
3. Promote the verified candidate to `main` and record the resulting exact main SHA.
4. Deploy that exact main SHA to Linode using the existing deployment runbook and restart only required services.
5. LIVE_VERIFY health, authentication, Transportation permissions, create → open → change → cancel, Departed → Completed, responsive UI, receipts, and rollback readiness using clearly labeled synthetic/demo data.
6. Update this checklist, Issue #129, `PROJECT_STATE.md`, and the release receipt with exact SHAs, timestamps, test totals, receipt IDs, failures/repairs, and final verdict.
7. If every written Transportation gate passes, mark it READY_FOR_OWNER_REVIEW; only Michael may change it to OWNER_ACCEPTED / DONE.

**ETA for `careops-transport-live-001`:** 0.5–1 focused workday after coordinator routing is restored. Confidence: medium; the estimate assumes existing Linode credentials and deployment runbook still work and expands if release drift or live-only failures are found.

## What “usable” means

A Care Operations workflow is usable only when the intended person can perform it without SSH or developer knowledge:

```text
resident / family / staff request
→ canonical record
→ correct department queue
→ staff action
→ truthful status update
→ resident/admin visibility
→ durable receipt with provenance
```

## Phase 1 — Core platform, identity, governance, and truth

Current status: **TESTED / partially DEV_ACCEPTED; not globally LIVE_VERIFIED.**

- [~] Canonical resident, staff, department, request/task, actor, and receipt structures exist.
- [~] Role and department access boundaries exist and have automated coverage.
- [~] Append-only lifecycle/history and provenance architecture exist.
- [~] Real and simulated records are structurally distinguishable.
- [~] Operations Simulator can exercise canonical task services rather than a separate fake business-logic universe.
- [~] Verify every active product surface reads/writes the canonical records; no parallel demo-only operational stores.
- [ ] Verify backup/restore, data retention, audit export, and facility isolation against the current runtime.
- [ ] Record one current release-wide security and permission acceptance pass.
- [ ] Record exact LIVE_VERIFIED runtime and SHA.

Milestone: one trustworthy shared foundation for all departments.

## Phase 2 — Core requests, service tickets, routing, and lifecycle

Current status: **Nursing and Maintenance DEV_ACCEPTED locally; cross-department completion incomplete.**

### Nursing / care

- [~] Request creation, department routing, queue, claim, acknowledge, start, notes, complete, history, receipts, and truthful resident status — DEV_ACCEPTED on the integration development path.
- [ ] Re-run the complete workflow on the current release candidate and record LIVE_VERIFIED evidence.
- [ ] Add explicit reassignment, unable-to-complete, escalation, and supervisor review acceptance where required.

### Maintenance / service tickets

- [~] Request/work order, queue, assignment, progress, notes, time spent, completion, resident status, history, and receipts — DEV_ACCEPTED on the integration development path.
- [ ] Re-run the complete workflow on the current release candidate and record LIVE_VERIFIED evidence.
- [ ] Verify priority, category, location/asset, photos/attachments, parts/costs, vendor handoff, reopen, and preventive-work paths.

### Shared lifecycle

- [~] Pending → claimed/assigned → acknowledged → in progress → completed lifecycle exists.
- [~] Status truth avoids claiming a worker is coming unless system evidence supports it.
- [~] Front desk can create and follow requests; full normal-work acceptance remains incomplete.
- [~] Admin can inspect cross-department work and history; every department has not been walked.
- [ ] Confirm cancellation, rejection, reschedule, duplicate, reopen, overdue, escalation, and supervisor override across supported departments.
- [ ] Mobile/desktop accessibility acceptance for staff lifecycle actions.

Milestone: every service request is actionable, traceable, and truthfully visible.

## Phase 3 — Care Operations workspaces (ACTIVE)

Current status: **ACTIVE. Transportation development slices are DEV_ACCEPTED; authenticated LIVE_VERIFY is blocked on production role/resource data, so compatible P0 Transportation correction continues.**

### Transportation — release/live task

- [~] Calendar, Day/Week, My rides/All rides, Completed, History, ride log, JSON/CSV export, and receipt-backed lifecycle exist in code.
- [~] PR #130 implements Transportation staff authority to create, assign, change, cancel, and open trip details.
- [~] Focused frontend tests passed: 3 suites / 3 tests.
- [~] Frontend production build passed; changed Python modules compile.
- [~] Refresh PR #130 onto current integration.
- [~] Run Mongo/FastAPI lifecycle test.
- [~] Configure acceptance drivers and vehicles in clearly labeled test data.
- [~] DEV_ACCEPT create → open → change → cancel → receipt inspection.
- [~] DEV_ACCEPT Departed → Completed → receipt inspection.
- [~] Merge integration and run full gate.
- [~] Promote/deploy and LIVE_VERIFY the workflow. Promoted (`main` → `ff87c22`, Michael, 2026-10-11 16:40Z) and DEPLOYED to Linode 2026-10-11 21:28Z (exact SHA, backup `20261011-212802-pre-deploy-d7ff96a4e4d1`, independent verification + 12/12 public smoke; PROJECT_STATE entry). LIVE_VERIFY not yet run: needs Michael's owner sign-in on production and one driver + one vehicle created there.

### Front desk and administrative communication

- [~] Resident directory, request queue, callback/request handling, communications views, and status lifecycle exist in part. Callback handling DEV_ACCEPTED 2026-10-11 (`careops-frontdesk-callback-001`, headless 19/19 as the demo front-desk user: create → route to Administration or Maintenance → assign/unassign/claim → note → complete → reopen once → second completion; 9-receipt linked chain; department scope enforced; `docs/reports/2026-10-11-front-desk-callback-acceptance.md`). Reassign to a colleague needs a second front-desk account (admin sign-in).
- [ ] One unified inbox for requests, messages, callbacks, approvals, and failed deliveries.
- [~] Create/assign/reassign/close/reopen from the workspace with truthful status and receipts. Verified 2026-10-11 for the front-desk role: create (resident-request bus, source `front_desk`), acknowledge, claim, assign select, start, note, complete, history — each with a linked receipt. **Reopen built the same day** (`careops-frontdesk-reopen-001`, integration `04cc580`): explicit receipted reopen with a required reason, headless-accepted 23/23 incl. reopen → second completion with an unbroken chain (report addendum). Awaiting owner review of the actual workspace.
- [ ] Shift notes, handoff, announcements, internal messages, read/acknowledge state, and searchable history.
- [~] Browser acceptance by a front-desk role and an administrator. Front-desk half DEV_ACCEPTED 2026-10-11 (headless, synthetic, 18/18 cases, 0 failed API calls, linked receipt chain; `docs/reports/2026-10-11-front-desk-acceptance.md`). Administrator half NOT run: no admin login on the dev stack for the coordinator (temp demo-admin creation refused by its permission classifier) — NEED owner sign-in or a permission rule.

### Dining / menus

- [~] Menu intake, review, publish, and resident lookup exist in part.
- [ ] Real correction propagation, version history, dietary/allergen fields, meal changes, and resident-facing confirmation.
- [ ] Live inbound source acceptance belongs to Phase 5.

### Activities / programs

- [~] Schedule intake, publish, Today view, and Aria lookup exist in part.
- [ ] Registration, attendance, capacity/waitlist, cancellation, transport link, reminders, and resident preferences.
- [ ] Staff and resident browser acceptance.

### Housekeeping

- [~] Request/task, queue, assignment, progress, completion, unable-to-complete, owner/admin review, reassignment, and receipt paths are DEV_ACCEPTED for a labeled synthetic workflow on `e2a8770` + `8ed21cd` + `347d2e6`.
- [~] Room/area scheduling, recurrence, inspection, and supplies/linen requests are DEV_ACCEPTED. Recurrence uses the canonical StaffTaskTemplate/StaffTask tick with facility-local dates, duplicate-proof occurrences, Upcoming visibility, single-occurrence reschedule, lifecycle completion, resident/Aria truth, role refusal, desktop/390 px, and linked receipts. Inspection supports receipted Pass or same-task Return for correction. Supplies/linen preserves typed item/quantity truth from Aria through queue, resident view, lifecycle, status, and receipts; no inventory source exists, so the product makes no stock claim.
- [x] **READY_FOR_OWNER_REVIEW:** the full Housekeeping section has passed labeled development acceptance for normal lifecycle, exceptions/review, scheduling, recurrence, inspection, and supplies/linen at desktop and 390 px. This is not OWNER_ACCEPTED / DONE until Michael explicitly approves it.

### Therapy and appointments

- [~] Therapy provider/discipline, appointment, recurrence, location, transport need, attendance, cancellation/reschedule, notes/status, and resident-facing schedule. DEV_ACCEPTED 2026-10-11 for one non-recurring appointment (`careops-therapy-appointment-001`): entered at the front desk → therapy shared queue → planned window (Plan) → reschedule → resident Home screen + Aria show it → attendance (complete) with a 6-receipt linked chain; second appointment cancelled with a reason (`task_cancelled`). Scratch-stack headless 21/21 with a synthetic therapist (`docs/reports/2026-10-11-therapy-appointment-acceptance.md`). Transport link DEV_ACCEPTED later the same day (`careops-therapy-transport-link-001`): "Ride" on a planned appointment creates or attaches exactly one ordinary transportation request through the existing core, linked both ways with receipts; reschedule/cancel of the appointment follow to the ride; scratch-stack headless 15/15 (`docs/reports/2026-10-11-therapy-ride-link-acceptance.md`). Provider/discipline/location DEV_ACCEPTED later the same day (`careops-therapy-details-001`): optional operational fields on the same StaffTask, receipted before/after, shown in the queue, the resident Home screen and Aria's status; scratch-stack headless 13/13 (`docs/reports/2026-10-11-therapy-details-acceptance.md`). Same day: the admin/front-desk request detail dialog shows and edits the same three fields through the same PATCH (frontend 72 suites / 570; report addendum). Date-ordered upcoming view DEV_ACCEPTED later the same day (`careops-therapy-upcoming-view-001`): `GET /tasks/upcoming` + `GET /tasks/resident-request/upcoming` over the canonical rows (facility day → planned time → created), Upcoming panel in the therapy workspace and "Coming up" on the resident Home screen with details, lifecycle and ride truth; admin edits details in the detail dialog with an admin_override receipt, front desk read-only; scratch-stack headless 25/25 (`docs/reports/2026-10-11-therapy-upcoming-acceptance.md`). Recurrence DEV_ACCEPTED 2026-10-12 (`careops-therapy-recurrence-001`) on `92aa098` + `9571aa0` + `468cbc8`: the canonical weekly series now preserves provider/discipline/location into duplicate-free occurrences; Admin has Therapy queue + Upcoming; a single occurrence can be rescheduled/cancelled without mutating or refilling the series; resident/Aria truth and one-reply concurrent-tool handling were proven in Claude Chrome at desktop and 390 px (`docs/reports/2026-10-12-therapy-recurrence.md`).
- [~] Permission boundaries for operational versus clinical information. DEV_ACCEPTED 2026-10-12 (`careops-therapy-permission-boundaries-001`) at `565cfa1`: explicit HTTP role × action matrix proves owner/admin, front desk, Therapy, other-department, and resident/public boundaries; clinical fields are rejected 422; unavailable Therapy sign-in is covered by direct API evidence. First proven leak repaired: unable-to-complete and supervisor-review reasons remain staff-only and no longer enter resident-visible notes. Backend 601 passed / 0 failed / 31 skipped plus focused 2/2; frontend 90 suites / 641; compiled build; nurse/resident 390 px and owner 1280 browser evidence on the development runtime (`docs/reports/2026-10-12-therapy-permission-boundaries.md`).
- [~] Calendar conflict detection and linked transportation request. Conflict detection DEV_ACCEPTED 2026-10-11 (`careops-therapy-conflict-001`): same-resident overlap over the canonical planned fields with one 60-min slot, warned in Plan/detail/Upcoming, saved only on an explicit "Save anyway" that is receipted (`conflict_override`, overlapped ids), honest when a time is unreadable; linked ride follows an overridden reschedule; scratch-stack headless 17/17 (`docs/reports/2026-10-11-therapy-conflict-acceptance.md`). Linked transportation request DEV_ACCEPTED earlier (ride link). Cross-resident provider/staff double-booking DEV_ACCEPTED 2026-10-12 (`careops-therapy-staff-conflict-001`) at `b7f6048`: same normalized provider name or assignee in overlapping 60-minute windows is refused with 409 before any write unless explicitly saved anyway; the override is receipted and shown to staff, while resident views carry no conflicts. Backend 603 passed / 0 failed / 31 skipped; frontend 90 suites / 642; build compiled; owner desktop/390 browser evidence (`docs/reports/2026-10-12-therapy-staff-conflict.md`).
- [x] **READY_FOR_OWNER_REVIEW:** final Therapy acceptance passed 32/32 checks on development with owner, front desk, a temporary labeled Therapy account, resident Home, and Aria status/schedule endpoints; desktop and 390 px; role refusals and clinical-field rejection; recurrence/Upcoming/conflict override/linked ride/receipt chain; full gates; and complete synthetic cleanup. Product `b7f6048` + frontend `db4317f`; records/report `8533b2a`. This is not OWNER_ACCEPTED / DONE until Michael explicitly approves it.

### Alerts / escalation

- [!] Canonical state model is unresolved; historical evidence records competing implementations.
- [~] Nursing unclaimed-request timer behavior is DEV_ACCEPTED on `e2a8770` + `28c0729` + `743c4d2`: one existing tick, 10-minute default threshold, one atomic receipt, repeated/concurrent-tick idempotency, stop after assignment/closure, supervisor visibility and truthful Aria status. Broader alert escalation levels/policy remain unresolved and are not OWNER_ACCEPTED / DONE.
- [ ] One escalation model, policy editor, acknowledgements, timers, fallback, receipts, and acceptance test.

Milestone: each department has a normal-work workspace, not a dead demo panel.

### Owner operator review — 2026-10-11 16:49 CDT; individual correction checklist

Michael's production screenshots and narrated review are owner observations. They establish UI gaps and questions, not a passed browser test. Each row below is part of this **same** living checklist, with `caoscare-1-ee` as the existing coordination owner. No second queue or worker is created. At claim time the coordinator records the one assigned worker and DELIVERED → ACK → WORKING → DONE or structured NEED in Issue #129. Every fix needs exact commit, role-specific browser evidence, linked receipts where applicable, loaded SHA, and Michael's review before its section can become OWNER_ACCEPTED / DONE.

**One current item:** `careops-transport-unresolved-001`, DISPATCHING through the existing coordinator `caoscare-1-ee`; explicit ACK/WORKING with an evidence-based ETA and exact `next_check_at` is pending. `careops-routing-exceptions-001` is DEV_ACCEPTED on loaded development revision `2155a9f` (backend 548/0/31, frontend 77/595, browser 11/11). `careops-current-operations-truth-001` remains READY_FOR_OWNER_REVIEW on `b3856b9`. ETA/watchdog enforcement is adopted and tested at integration `d87e9cc` (18 owner-intake tests). Production remains `ff87c22`; Transportation production LIVE_VERIFY remains blocked by absent labelled driver/vehicle and fresh signed-in role evidence.

| Item | Priority | Owner | Stage / exact blocker | Acceptance test | Next eligible action |
|---|---|---|---|---|---|
| `careops-resident-aria-core-reconciliation-001` | P0 | `caoscare-1-ee` | DEV_ACCEPTED (typed) 2026-10-12 01:45 CDT on dev `aba31a8`: owner-approved switch to gpt-realtime-2.1 + marin, 10-min continuity, owner v2 (`.env`, rollback in the report); 6 typed demo calls — time/weather/light/timer, quick return, bathroom → Nursing queue → claim/complete in Claude Chrome → Aria reports it handled; SIM start/pause/step/resume. Report `docs/reports/2026-10-12-overnight-live-acceptance.md`. Not done: spoken audio in Room 214, music/AC/email/calls/research (missing dependencies), 390 px walkthrough | Continuity after ~2 min, natural personality judged by Michael firsthand, live lookup with citations (`live:true`), calls only from real call-state receipts | Michael speaks to Aria in Room 214 and judges voice/personality; open wording defect: Aria says staff will "come help" before anyone is seen |
| `careops-nursing-exception-lifecycle-001` | P1 | `caoscare-1-ee` | DEV_ACCEPTED Monday, October 12, 2026 — 2:18 AM America/Chicago. Backend lifecycle `d16b3c7`; live-dropdown repair `1af968f`; records/report `6b2070e`; backend 592/0/31, frontend 88 suites/629, build compiled. Owner in Claude Chrome assigned synthetic task `task_789c03588ae8` to Demo - Nancy Reyes RN; `task_assigned` recorded `admin_override:owner`, null → nurse, same workflow; maintenance reassignment returned 403; nurse visibility passed at 390/1280 with no failed API calls; typed Aria `rt_62sib2cc_1791789384982` reported the true acknowledged/not-started state. Not OWNER_ACCEPTED / DONE. | Reassign, unable-to-complete with reason, escalation, supervisor review, truthful status, refusals, linked receipts | Present for owner review; department-lead role remains absent; automatic unclaimed-task escalation is the next bounded gap |
| `careops-nursing-unclaimed-escalation-001` | P1 | `caoscare-1-ee` | DEV_ACCEPTED Monday, October 12, 2026 — 2:53 AM America/Chicago on `e2a8770` + `28c0729` + `743c4d2`: existing tick flags a current pending/unassigned Nursing request once after configured threshold; receipt `task_unclaimed_escalated` chains to origin; request stays open; repeated/concurrent ticks deduplicate; assigned/closed/review records skip; no external delivery. Backend 593/0/31, frontend 88 suites/631, build compiled; owner Claude Chrome routing-exception proof; nurse 390; maintenance hidden; truthful Aria; cleared after claim with one receipt. | Deterministic threshold, atomic receipt, idempotency, stop conditions, supervisor visibility, truthful status, role refusal | Present for owner review; broader multi-level escalation remains open |
| `careops-housekeeping-exception-lifecycle-001` | P1 | `caoscare-1-ee` | DEV_ACCEPTED Monday, October 12, 2026 — 3:10 AM America/Chicago on backend `e2a8770`, frontend fix `8ed21cd`, and records/report `347d2e6`+. Typed Aria request → housekeeper at 390 px claim/start/cannot-complete → owner Claude Chrome review and dropdown assignment → housekeeper completion; nurse/maintenance refusals; truthful Aria; 8 receipts on one workflow; counts reconcile. | Housekeeping claim/start/cannot-complete/review/reassign/complete, truthful status, role refusal, responsive UI, linked receipts | Present for owner review; scheduled work is the next bounded Housekeeping gap |
| `careops-transport-live-001` | P0 | `caoscare-1-ee` | BLOCKED / LIVE_VERIFY PENDING; production `ff87c22` is loaded and public smoke is 12/12, but production has no labelled driver/vehicle and no fresh signed-in role acceptance receipt | Signed-in Transportation role creates, opens, changes, cancels, departs and completes rides on loaded `ff87c22`; inspect linked receipts and responsive UI | Preserve the exact blocker; resume when existing authorized session/data can supply a driver/vehicle without inventing live proof |
| `careops-transport-unresolved-001` | P0 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-12 on `0c517fe`: count reproduced (11 = open, unbooked rides, any date); tile opens the list; rows open the real request with receipt timeline; report scoped to transport coordinators; backend 549/0/31, frontend 78/597, browser 8/8 | Count opens a filtered canonical list; every row opens detail, owner/status/next action and receipt trail; count matches records | Owner review; not deployed (production `ff87c22`) |
| `careops-transport-new-order-001` | P0 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-12: no "New order" label exists; the admin Transportation daily screen lacked New ride (front desk, transport staff and calendar had it). Added the canonical New ride there; backend 550/0/31, frontend 79/598, build ok, browser 10/10 | Intended staff can create the relevant transport request from the visible entry point and see it in queue/calendar with receipt, or the misleading entry is removed/renamed | Owner review; not deployed |
| `careops-transport-calendar-001` | P1 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-12 on `7a7cd92`: empty day now shows next dates with rides (jump) and how many open requests are dated before today (10 of 11 on dev); default day = facility date; backend 559/0/31, frontend 82/609, browser 14/14 | Scheduled rides appear on day/week views and open their real request; empty state explains filters/data | Owner review; not production loaded or OWNER_ACCEPTED / DONE |
| `careops-transport-resources-001` | P1 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-12: setup guide (purpose, 4 steps) + status from engine rules (can rides be booked, what is missing, sharing off without seat counts); frontend 81/607, build ok, browser 8/8 | Authorized staff see what is required for assignment, how to manage drivers/vehicles, and what buffer changes; role refusals and empty states are clear | Audit resource screen by role, add task-specific instructions and browser test |
| `careops-routing-delivery-audit-001` | P0 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-11 ~23:00Z: trace passed every transition; first gap (department not actually notified, invisible) repaired — detail/board/overview now say delivered / sent / not notified; headless 7/7 (`docs/reports/2026-10-11-routing-delivery-audit.md`). Real delivery still needs the provider (RQ-005) | One synthetic resident request traces creation → Kitchen delivery → named worker claim/assignment → acknowledgement → completion with timestamps and linked receipts; detect any lost/aging request | Run end-to-end routing audit; repair first proven broken transition |
| `careops-routing-exceptions-001` | P0 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-12 ~00:55Z: GET /ops/routing-exceptions (+detail, receipted re-notify) over canonical tasks/notifications/receipts; Admin → Community → Routing exceptions; gate 548/0/31, frontend 77/595, headless 11/11 (`docs/reports/2026-10-11-routing-exceptions.md`) | Supervisor can filter undelivered, unassigned, overdue and failed handoffs; each state has owner, age, retry/escalation and receipt | Build the bounded exception view from canonical task/notification records; prove one recovery path per exception class in API and browser; preserve receipts |
| `careops-current-operations-truth-001` | P0 | `caoscare-1-ee` | READY_FOR_OWNER_REVIEW on loaded dev `b3856b9` (2026-10-11 18:09 CDT). No SIM run was running; 322 open alerts were 21–63 d old and none simulated; 56 open mock/test tasks. Current-by-default Alerts/queues, separated counts, SIM state/run ID, and receipted legacy close passed backend 547/0/31, frontend 76/592, build, browser 13/13. No dev or production record was closed | Observe `/simulator/state`; trace one fresh SIM request; distinguish current real, current SIM-run, and historical/test records; preserve receipts; provide audited legacy disposition; prove counts/sort/refresh/STOP/START/no cross-run leakage in API and browser | Michael reviews localhost:3000 Alerts and Nursing: current work must be default; 322 older alerts and 49-day mock requests must remain accessible under review, with emergencies requiring written disposition |
| `careops-dept-roster-001` | P1 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-11 22:50Z (built as the compatible fallback before this reordering landed; routing audit not yet started) | Housekeeping and Activities show actual department members, roles and availability from canonical staff records; add/remove or assignment rights follow role | DONE at dev level: `GET /departments/{slug}/board` + Admin → Departments dialog (members/roles, work by named worker, dispatch trail, completed history with receipts, receipted assign/ack/start/complete; 403 outside the department). Gate 543/0/31, frontend 76/589, scratch-stack headless 11/11 (`docs/reports/2026-10-11-department-board-acceptance.md`). Availability (schedules) not modelled; Activities board is empty until staff/requests exist. Owner review pending. |
| `careops-dept-dispatch-001` | P1 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-12: admin queues explain routing (Claim / Assign to…), name who works in the department, and state when nobody does (production has only the owner, so Assign lists are empty there); frontend 83/612, browser 8/8 | Manager assigns/reassigns a request to named worker; staff claim/start/complete in scope; each transition has time, actor and receipt | Reproduce current assignment path, then make it visible/operable |
| `careops-dept-history-001` | P1 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-12: admin queues show Recently closed (completed + cancelled, who, when, time spent, note) open by default; full history stays on the department board; frontend 85/619, browser 10/10 | Department shows open/in-progress/completed/skipped records by worker, date and reason; opens detail and receipt chain; counts reconcile | Add status/history filters and click-through; verify counts |
| `careops-activities-work-001` | P1 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-12: Admin → Community → Activities has the request queue with dispatch note, Claim/Assign and history; browser 12/12 | Activity staff see assigned event preparation/work, owner, due time, status and completion history | Reuse staff/task path, then accept intended staff workflow |
| `careops-ops-nav-kitchen-001` | P1 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-12: Kitchen request queue added to Admin → Community; overview department cards open their workspace; frontend 80/601, build ok, browser 12/12 | Kitchen appears for authorized users and opens its real queue/menu work; no dead panel | Add route/card with role test |
| `careops-ops-nav-transport-001` | P1 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-12: Transportation tabs moved into Admin → Community; overview Transportation card opens it; frontend 80/601, build ok, browser 12/12 | Transportation appears for authorized users and opens the real workspace | Add route/card with role test |
| `careops-activities-nav-001` | P1 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-12: activities calendar shown under Activities (same records as Communication → Schedule, not copied); overview card opens it | Activity events are found under Activities; resident schedule and Transportation calendar remain in their contexts without copied records | Rename/move navigation, preserve deep links, browser-test |
| `careops-activities-calendar-001` | P1 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-12: labeled paste→draft→publish→Aria schedule lookup→staff + resident screen 10/10; load failure no longer shown as empty (menu + schedule); production activities still need publishing by staff | Publish a dated activity and verify staff/resident views show correct event, owner and status; empty state distinguishes no events from load failure | Trace current intake/publish data to calendar and fix first break |
| `careops-menu-visible-001` | P1 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-12 on `4b270ef`: cause = published menu ends 2026-10-03 (prod 10-02); screens now say so; publish→Aria dinner lookup→resident screen traced 10/10; production menus still need publishing by staff | Published dated breakfast/lunch/supper shows in operator and resident views; “what's for supper tonight?” returns actual published meal or honest no-menu state | Trace existing publish/lookup path with labelled test menu |
| `careops-menu-paste-001` | P1 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-12 on `7e854ce`: one paste can cover a week (dated day headers → one draft per day); draft not public; publish; replacement shown as Replaced and hidden from Aria/residents; trace 12/12; PR #110 not used | Paste a complete multi-day/menu text into one review batch, inspect parsed meals/corrections, publish once and see versioned result; no blind merge of #110 | Browser-test current parser/import UI, fix concrete failure in a fresh bounded slice |
| `careops-family-add-001` | P1 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-12: Add button was off-screen at 390 px (header did not wrap); fixed; browser add verified at both widths | Authorized operator adds a family contact to correct resident, saves once, sees contact and receipt; unauthorized role refused | Reproduce add control by role, repair UI/API as needed |
| `careops-family-edit-001` | P1 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-12: PATCH edit + Edit button; approved phone owner/admin only; receipts for every contact change; backend 557/0/31, frontend 81/603, browser 11/11 | Authorized operator edits existing contact, sees before/after and receipt without duplicate contact | Implement/edit path with authorization and browser test |
| `careops-clinician-workspace-001` | P1 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-12 on `677e250`: purpose stated, load/refusal states, events open the close-out, older records flagged, summary filled; stats admin+nursing only (kitchen/front desk 403); backend 566/0/31, frontend 84/614, browser+API 14/14 | Define the clinician's allowed operational job, complete one normal-work path in browser, and show truthful permissions/empty state; hide misleading route until accepted | Audit current page and role, identify first complete workflow |
| `careops-screen-guidance-001` | P1 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-12: purpose + next step on Departments, Activities, Menu, Transportation (+ resources) and Family; browser 16/16; novice usability is the owner's review | Departments, Activities, Menu, Transportation and Family screens state purpose, setup, role, next action and result in plain language; novice operator can finish one task per screen | Add contextual guidance as each workflow is repaired, then cross-screen review |
| `careops-email-config-001` | P2 | `caoscare-1-ee` | BLOCKED on existing provider key, sender address, webhook secret/account facts; UI visibly reports unset | Configuration screen names each missing value and effect; real inbound/outbound test has delivery/failure receipts after existing account is supplied; no mock counted live | Keep honest unset state; prepare exact account/secret NEED only when this becomes active |
| `careops-good-surfaces-review-001` | P2 | `caoscare-1-ee` | DEV_ACCEPTED 2026-10-12 on `198fee4`: one task each on Requests, Devices, Reports/Audit, Facility, Live board (30/30); gap fixed: admin device command was open to any login and unreceipted, now owner/admin only with a receipt; owner acceptance still pending | Intended roles complete one normal task per surface; controls route to canonical records and receipts; no silent dead end | Include in section review after P0/P1 corrections |

Do not mark a row `[x]` from implementation or agent report alone. Keep prior history. Do not open a second queue, duplicate coordinator, or treat the owner-observed Kitchen Pending state as worker delivery. No audio/Hey Aria lane, paid provider commitment, or unapproved production data setup is included.

### PR and working-tree reconciliation — 2026-10-11 17:00 CDT

- **Active product:** `main` is `ff87c22`; integration is 73 commits ahead and 0 behind. This is code drift, not a claim that all later slices passed production acceptance.
- **Eight open PRs, zero ready for immediate Care Operations merge:** #110 menu parser draft conflicts with integration, whose existing parser/test already covers the three reported cosmetic cases in a different way; inspect semantics before any rebase. #105 Desktop-Agent project-package draft conflicts and its `.agentproject/project.yaml` is absent on integration. #67 Agent Control Plane is open/conflicting with old green CI and lacks current-base/host acceptance. #45 is an old conflicting hardware docs draft. #41/#42 are explicitly parked public onboarding drafts. #46 wake research and #23 voice remain parked outside this lane. None was merged or closed in this review.
- **Working tree:** this cloud supervisor can verify GitHub commits and its own clean scratch review clone; it cannot inspect the actual EliteDesk `~/CAOSCARE-INTEGRATION` worktree. Do not claim host changes are committed or clean without a timestamped host `git status`.
- **NEED_HOST_RECOVERY:** `da-ba92a5f535` was delivered 16:54:31 CDT with no Issue #129 ACK/WORKING after five minutes. Existing local watchdog/coordinator must run `cd ~/CAOSCARE-INTEGRATION && python3 scripts/owner_intake/coordinator_state.py && git status --porcelain=v1 -b && git rev-parse HEAD`, publish timestamped state and ACK/WORKING or an exact recovery NEED. Canonical receipt: Issue #129 comment `6114293012`. This is a missed receipt target, not proof the process stopped; current host liveness UNKNOWN.
- **Current bounded action is one:** `careops-routing-exceptions-001`. Current operations truth is READY_FOR_OWNER_REVIEW on loaded dev `b3856b9`; the earlier missing ACK is a receipt-protocol gap, but exact code, gates, browser evidence, clean loaded revision and user-visible result now exist. Transportation remains a preserved blocked acceptance item. Delivery receipt `da-6618877755` confirmed the existing coordinator intake path at 18:38:25 CDT, but no ACK/WORKING arrived by 18:43:25. `NEED_HOST_RECOVERY` is recorded in Issue #129 comment 6115232846; run the exact command through the existing watchdog/coordinator and do not create a duplicate worker.

## Phase 4 — Scheduling, records, resources, and coordinated calendars

Current status: **PARTIAL / not accepted as a complete system.**

- [~] Transportation calendar and ride log exist; current workspace correction is in Phase 3.
- [ ] Real drivers, vehicles, capacity, availability, service status, assignment, conflicts, and recurring runs.
- [ ] Resident appointment calendar linking therapy, medical appointments, activities, dining events, and transportation.
- [ ] Staff schedules, department coverage, handoffs, absence/substitution, and assignment visibility.
- [ ] Resource calendars for rooms, vehicles, equipment, and shared spaces.
- [ ] Conflict warnings, reminders, cancellation/reschedule propagation, and receipt history.
- [ ] Daily/weekly printable and exportable schedules.
- [ ] DEV_ACCEPT and LIVE_VERIFY each calendar from its intended role.

Milestone: one coherent schedule rather than disconnected department calendars.

## Phase 5 — Communications, family, email, SMS, and phone

Current status: **internal plumbing partially TESTED; real external delivery/calling not LIVE_VERIFIED.**

- [~] Admin communications and notification delivery/status views exist.
- [~] Provider states distinguish queued/logged/sent/delivered/failed where evidence exists.
- [~] Inbound email webhook, allowlist, parsing, review, and mock-provider tests exist.
- [ ] Configure verified domain, webhook, API keys, real inbound addresses, sender allowlists, and department destinations.
- [ ] Real inbound menu email → review → publish.
- [ ] Real inbound activities email → review → publish.
- [ ] Real outbound Nursing, Maintenance, Transportation, Front Desk, and Admin delivery with delivery/bounce receipts.
- [ ] Resident/family contact directory, permissions, preferred channel, message history, and opt-in/opt-out.
- [ ] Family updates and reply workflow without exposing unrelated resident information.
- [ ] SMS delivery and failure acceptance.
- [ ] Front-desk and approved-family voice calling with requested/dialing/connected/unanswered/failed/ended states and receipts.
- [ ] No delivery or connection claim without provider/runtime proof.

Milestone: communication actually reaches the intended person and comes back into the same record.

External dependency: provider accounts, domain/DNS, real addresses/numbers, and approved contacts. Estimate after configuration is available: 1–3 focused days per external service.

## Phase 6 — Pilot operation, reliability, room integration, and accessibility

Current status: **PARTIAL; broad voice work is PARKED while Care Operations is active.**

- [~] Room 214 home test proves portions of voice, lights, and local workflow; it is not a facility production pilot.
- [~] Demo room is synthetic and must stay visibly separate from real resident records.
- [ ] Select the real pilot community/room(s), network, resident identity, staff roster, department destinations, permissions, and hardware.
- [ ] Autostart, reboot recovery, network interruption/recovery, service health, backup, restore, rollback, and monitoring.
- [ ] One real resident request through staff completion and resident follow-up.
- [ ] One real transportation workflow.
- [ ] One real communication workflow.
- [ ] One real room-control workflow with hardware read-back.
- [ ] Accessibility: low vision, hearing assistance, touch targets, keyboard use, mobile staff use, clear language, and no color-only status.
- [ ] Ordinary operation without SSH babysitting.
- [ ] Repeat the installation in a second room from documented provisioning.

Milestone: one room and its staff workflows operate reliably, then reproduce in room two.

## Phase 7 — Release, deployment, and live acceptance

Current status: **AUTHORIZED; current Care Operations release not yet executed or LIVE_VERIFIED.**

Owner authorization permits verified CAOSCare work to proceed through integration, `main`, Linode deployment, necessary service restarts, testing, repair, and continued bounded development without routine permission stops.

- [~] Complete the active slice's implementation/test/DEV_ACCEPTED gates.
- [~] Merge accepted work into `integration/2026-09-27`.
- [~] Run the full integration regression gate and record results.
- [ ] Create the exact release candidate and change summary.
- [ ] Merge/promote the verified candidate to `main`.
- [ ] Deploy the exact `main` SHA to Linode.
- [ ] Verify health, authentication, permissions, the active workflow, responsive UI, receipts, and rollback path.
- [ ] Record deployed SHA, time, operator, commands/actions, test cases, receipt IDs, failures, repairs, and final verdict.
- [ ] Update public capability claims only after LIVE_VERIFIED acceptance.

Milestone: code is not merely present; the deployed product is usable.

## Milestone schedule

| Milestone | Acceptance result | Current state | Evidence-based estimate |
|---|---|---|---|
| M0 — Build control | Living checklist, current task, gates, ETA, and reporting contract in GitHub | COMPLETE with this file | Complete |
| M1 — Transportation usable | Staff creates/opens/changes/cancels and completes trips with receipts in the deployed app | DEV_ACCEPTED; main/production `ff87c22`; 12/12 public smoke; authenticated LIVE_VERIFY pending; coordinator ACK unverified | after authenticated role acceptance |
| M2 — Core Care Operations loop | Nursing, Maintenance, Front Desk/Admin, and shared service-ticket lifecycle re-accepted on current release | PARTIAL | 2–4 focused workdays after M1 |
| M3 — Coordinated schedules | Transportation + therapy/appointments + resident/staff calendar links accepted | PARTIAL | 3–6 focused workdays after M2 |
| M4 — Remaining departments | Dining, Activities, Housekeeping, Admin/reporting, alerts/escalation usable | PARTIAL / some planned | 5–10 focused workdays |
| M5 — Real communications | Email, then SMS/phone, with real delivery/call receipts | BLOCKED on provider configuration | 1–3 focused days per service after configuration |
| M6 — Pilot acceptance | One real room + staff + communications + recovery; then repeatability | NOT STARTED as a complete gate | 3–5 focused workdays after dependencies |
| M7 — Release verified | Exact SHA on Linode, live workflow accepted, release receipt recorded | Exact-SHA Linode deploy and 12/12 public smoke completed; authenticated workflow/receipt gate pending | after authenticated role acceptance |

**Current honest overall position:** the foundation is substantial, and Nursing/Maintenance have local end-to-end evidence. The product is not yet release-ready because Transportation is DEV_ACCEPTED but not LIVE_VERIFIED, the other department workspaces are incomplete or unaccepted, external communications are not live, and the full pilot/release gate has not passed.

**Overall planning range:** approximately 2–4 focused engineering weeks for the broader Care Operations product slice, plus calendar time for provider/hardware access. This is a planning range, not a promise; each milestone will replace it with actual cycle-time evidence.

## Owner-facing reporting contract

For every meaningful task completion, update this checklist and the active queue/issue atomically where authorized. Record:

- owner requirement and task/issue/PR;
- active phase and milestone;
- exact base, branch, implementation SHA, integration SHA, main SHA, and deployed SHA where applicable;
- files changed;
- automated test receipt;
- development browser acceptance;
- live acceptance;
- runtime/service restarted;
- receipt IDs and provenance;
- blocker and who/what can remove it;
- next bounded task;
- ETA range, assumptions, and confidence;
- whether an owner decision is actually required.

Do not report “built,” “done,” or “live” as interchangeable words. State exactly: IMPLEMENTED, TESTED, DEV_ACCEPTED, LIVE_VERIFIED, READY_FOR_OWNER_REVIEW, or OWNER_ACCEPTED / DONE.

## Autonomous build rule

Continue through bounded tasks without asking Michael for routine permission. Merge, deploy, restart, test, repair, and continue when the defined gates pass. The normal approval stop is when a complete section reaches READY_FOR_OWNER_REVIEW: present it to Michael, record his approval or punch list, then check it off and advance. Also stop for a genuine owner decision such as new spending, destructive loss of real data, a material product-direction choice, unavailable credentials/account access, or an irreversible external commitment.

Permanent law: **No action without a receipt. No receipt without provenance.**


---

## Update — 2026-10-11 07:50 CDT — therapy details DEV_ACCEPTED; upcoming schedule view dispatched

`careops-therapy-details-001` is **DEV_ACCEPTED**, not LIVE_VERIFIED, not READY_FOR_OWNER_REVIEW for the full Therapy/appointments section, and not OWNER_ACCEPTED / DONE.

- Product: `de8e4f2dc56eaa0ce541f7b34d6f4aba034a564a`; canonical optional operational provider, discipline, and location fields on the existing StaffTask. Changes are authorization-checked, no-op safe, and receipt-backed with before/after state. Queue, resident Home/schedule, history, and Aria status show the truthful values.
- Gates: backend 540 passed / 0 failed / 31 skipped; frontend 70 suites / 565; production build compiled. GitHub exposes no combined-status contexts or workflow runs for this SHA.
- Isolated browser: 13/13, 0 failed API calls, 0 page errors; unauthorized front desk refused, create/edit/reschedule visibility, linked receipts, history, Aria output, resident view, and 390 px layout verified.
- Report: `docs/reports/2026-10-11-therapy-details-acceptance.md`, blob `f57cfbd619e0744c9b8215bbc52240cf17104b49`.
- Dev runtime: guarded restart record `b34e7213c0a857672f892f0b7c18546165a91225`; old PID 456493, new PID 481325, zero leases, clean tree, runtime product commit `de8e4f2`, log `/tmp/room214_backend_de8e4f2.log`. Main remains `880d10f`; production remains `d7ff96a`.

Next single bounded task: `careops-therapy-upcoming-view-001`. Add a date-ordered upcoming-appointments view for therapy staff and residents using only the canonical StaffTask/resident-safe data. Show planned time, provider/discipline/location, lifecycle status, and linked-ride truth; test authorization and stable facility-time ordering; accept staff and resident paths in an isolated browser at desktop and 390 px. Excludes recurrence, a new calendar store, clinical data, conflict detection, billing, messaging, audio, paid services, production deploy, and real-data mutation.


### Handoff receipt — 2026-10-11 07:54:18 CDT
Desktop Agent automatic intake delivered `da-eecac34ab9` to the existing coordinator session `caoscare-1-ee` (Issue #129 comment 6109234198). This proves delivery only. Explicit ACK/WORKING remains pending; no duplicate coordinator or worker was created. Slack liaison output: `1791723184.185039`. Slack inputs were processed through `1791722564.078439`; those newer inputs were Deal Sniffer-only.


### Concurrent tested addendum reconciliation — `4b92e19`
The coordinator used the brief dry queue before the supervisor dispatch to close the therapy-details report's recorded admin/front-desk detail-dialog gap. Commit `4b92e193e8ee59056904da79e577b1fa06154373` shows and submits provider/discipline/location through the same canonical PATCH and shares one formatting/payload helper with the department queue. Frontend 72 suites / 570 passed and the production build compiled. This addendum is **IMPLEMENTED / TESTED**, not DEV_ACCEPTED: no browser run was recorded, and the browser must prove an authorized admin can edit while an unauthorized front-desk actor cannot silently mutate a therapy-owned task. That single compatible acceptance/repair case is folded into `careops-therapy-upcoming-view-001`; no second worker or task is created.


---

## Update — 2026-10-11 09:15 CDT — therapy upcoming schedule DEV_ACCEPTED; conflict detection dispatched

`careops-therapy-upcoming-view-001` is **DEV_ACCEPTED**, not LIVE_VERIFIED, not READY_FOR_OWNER_REVIEW for the full Therapy/appointments section, and not OWNER_ACCEPTED / DONE.

- Product: `958093a4f27080035f8e5552c9fbcc695e894c06`; canonical StaffTask reads only—no calendar store. Authorized staff and resident-safe endpoints return facility-day/time ordered upcoming rows with operational details, lifecycle truth, and linked-ride facts. Therapy workspace and resident Home render the same truth.
- Gates: backend 541 passed / 0 failed / 31 skipped; frontend 74 suites / 577; production build compiled. GitHub exposes no combined-status contexts or workflow runs for this SHA.
- Isolated browser: 25/25, 0 failed API calls. Staff and resident desktop/390 views, stable ordering, details/lifecycle/ride truth, authorized admin edit with an `admin_override` receipt, and truthful front-desk read-only plus direct 403 were verified. The pre-existing kiosk accessibility-row overflow at 390 px is recorded separately and is not attributed to this slice.
- Report: `docs/reports/2026-10-11-therapy-upcoming-acceptance.md`, blob `52a7bff65c9d350f6a8ff179f5e556774fb6765a`.
- Dev runtime: guarded restart `fce6026e61c3b6fa530e3f03581f1f54617a8fe0`; old PID 481325, new PID 504444, zero leases, clean tree, runtime product commit `958093a`, log `/tmp/room214_backend_958093a.log`. Main remains `880d10f`; production remains `d7ff96a`.
- Follow-up `b229485c96a57fb45d5a01c2f66a97bf0c00aced` hides lifecycle actions from unauthorized detail-dialog viewers. Frontend 74 suites / 578 and build compiled; it is IMPLEMENTED/TESTED, not DEV_ACCEPTED because it has no browser run. Its authorization case is folded into the next worker rather than creating a second task.

Next single bounded task: `careops-therapy-conflict-001`. On canonical StaffTask planned data, add a bounded operational duration and detect same-resident overlaps without copying records into another calendar store. Warn truthfully, require an explicit save-anyway choice, and receipt the override/provenance; preserve linked-ride behavior. Prove overlap/non-overlap, authorization, unparseable-time honesty, responsive staff/admin/front-desk behavior, and the `b229485` lifecycle-button rule. Excludes recurrence generation, clinical content, billing, messaging, audio, paid services, production deployment, and real-data mutation.


### Handoff receipt — 2026-10-11 09:19:07 CDT
Desktop Agent automatic intake delivered `da-b4fa364b0f` to the existing coordinator session `caoscare-1-ee` (Issue #129 comment 6109970689). This proves delivery only. Explicit ACK/WORKING remains pending; no duplicate coordinator or worker was created. Slack liaison output: `1791728274.258519`.


---

## Correction — 2026-10-11 16:32 CDT — current Care Operations boundary

`careops-therapy-conflict-001` is DEV_ACCEPTED on product `77f83d3d53e17ffb75c71d137ab876e50552efe9`: backend 542 passed / 31 skipped, frontend 75 suites / 585, compiled build, isolated browser 17/17. Evidence: `docs/reports/2026-10-11-therapy-conflict-acceptance.md`; guarded dev backend restart `1bf1bec26ea58a6c55730fea3c858734eb788d54` loaded `77f83d3`. The full Therapy section remains PARTIAL. Same-resident overlaps are checked; staff double-booking across residents remains open.

The prior M1 text saying `main` promotion awaits owner commands is stale. GitHub verifies `main` at `ff87c22df1dd69b405fa0ec60429c20fe72f6801`; last recorded production is `d7ff96a`. The existing `careops-transport-live-001` is the ONE active bounded release task. Standing authorization covers exact-SHA deployment and LIVE_VERIFY; a narrow host/tool approval may still require interaction, to be recorded as exact NEED, not misclassified as a new owner decision. Issue #129 comment 6113952748 routed it to existing coordinator `caoscare-1-ee`; automatic delivery `da-3995f8741b` at 16:27 CDT proves delivery only. Fresh ACK/WORKING and current host process health remain UNKNOWN. If blocked, record exact command/target/prompt and continue compatible authorized work. Checklist/project state closeout and live release verdict are pending.


---

## Checkpoint — 2026-10-11 19:58 CDT — routing exceptions reconciled; Transportation unresolved count dispatched

- `careops-routing-exceptions-001` is **DEV_ACCEPTED** at `2155a9f`: backend 548 passed / 0 failed / 31 skipped; frontend 77 suites / 595; production build compiled; isolated browser 11/11. Development loaded `2155a9f`; production remains `ff87c22`. This is not LIVE_VERIFIED or OWNER_ACCEPTED / DONE.
- The ETA-driven receipt/watchdog addendum is implemented and tested at integration head `d87e9cc`; `scripts/owner_intake/tests` reports 18 passed. The last timestamped host observation is the 19:01 CDT adoption receipt. Current host liveness after that receipt is UNKNOWN.
- Production Transportation LIVE_VERIFY remains blocked on an authenticated owner/admin session plus one driver and one vehicle. That blocked item stays preserved.
- **ONE current bounded task:** `careops-transport-unresolved-001`. Reproduce the reported “11 unresolved” count in the intended Transportation role, make the count open a canonical filtered list, make every row open detail with owner/status/next action/receipt trail, and reconcile the count to records. Use existing records and routes; do not create another queue or truth store.
- Dispatch is recorded in Issue #129. Explicit `ACK / WORKING` with realistic ETA, exact America/Chicago `next_check_at`, expected acceptance evidence and blocker/NONE is required within five minutes. Until that arrives, ETA and next check are UNKNOWN by design.


---

## Checkpoint — 2026-10-11 21:15 CDT — Transportation unresolved DEV_ACCEPTED; New order path dispatched

- `careops-transport-unresolved-001` is **DEV_ACCEPTED** at feature `0c517fedaf539736acd14ea1d5b787d0e7137435`, with development records/restart through `1d617b8` and `ffa13a7`. Backend 549 passed / 0 failed / 31 skipped; frontend 78 suites / 597; build compiled; isolated browser 8/8. Development loaded `1d617b8` on PID 939383 with zero leases. The Transportation **Unresolved 11** tile now opens exactly the 11 canonical open, unbooked rides (any date); every row opens the real request with owner/status/next action/receipt trail. Report: `docs/reports/2026-10-11-transport-unresolved.md`.
- GitHub exposes no combined-status contexts or pull-request workflow runs for this slice; the dated local gates, browser report, and host restart receipt are the acceptance evidence. It is not production loaded, LIVE_VERIFIED, READY_FOR_OWNER_REVIEW for the full Transportation section, or OWNER_ACCEPTED / DONE.
- Production remains `ff87c22df1dd69b405fa0ec60429c20fe72f6801`. Authenticated Transportation LIVE_VERIFY remains blocked on a signed-in authorized role plus one driver and one vehicle; preserve that exact NEED.
- **ONE current bounded task:** `careops-transport-new-order-001`. Reproduce the owner-reported unavailable **New order** control using the intended roles and trace whether it is the canonical transport-request entry or a misleading duplicate of **New ride**. If legitimate, make it visible and usable for the authorized role, create only the canonical request, and prove it appears in the queue/calendar with a linked receipt. If redundant or misleading, remove or rename it truthfully. Prove authorization/refusal, empty/error states, desktop and 390 px behavior, no duplicate records, and no parallel truth store.
- Explicit ACK/WORKING is due by **2026-10-11 21:20 CDT** with responsible coordinator/worker, stage, evidence, realistic ETA, exact America/Chicago `next_check_at`, expected acceptance evidence, and blocker `NONE`; otherwise publish an exact NEED_HOST_RECOVERY. No duplicate coordinator, worker, queue, monitor, or truth file.
- Slack liaison processed through `1791767219.741959` (2026-10-11 20:06:59 CDT). That input was a CAOSCare event-connection test only; it did not dispatch work or create an owner decision.


---

## Checkpoint — 2026-10-11 23:21 CDT — three development completions reconciled; Transportation resources guidance dispatched

- `careops-transport-new-order-001` is **DEV_ACCEPTED** at `0226119d61429db76d81febecbbeb1ec8a4b4a10`: backend 550 passed / 0 failed / 31 skipped; frontend 79 suites / 598; build compiled; isolated browser 10/10. The admin Transportation daily screen now opens the existing canonical **New ride** form; unauthorized roles are refused and one authorized save produces one canonical request, origin receipt, Unresolved visibility, and calendar visibility. Development frontend served the change; backend remained loaded at `1d617b8`. Production remains `ff87c22`.
- `careops-ops-nav-kitchen-001` and `careops-ops-nav-transport-001` are **DEV_ACCEPTED** at `4d0c473`: frontend 80 suites / 601, build compiled, browser 12/12 at desktop and 390 px. Kitchen and Transportation are now reachable under Admin → Community and overview department cards open the real workspace.
- `careops-family-add-001` and `careops-family-edit-001` are **DEV_ACCEPTED** at backend `f4f210f` and frontend/docs `a96b18a019cad1fc60f9883ca46075e33963daa4`: backend 557 passed / 0 failed / 31 skipped; frontend 81 suites / 603; build compiled; browser 11/11. Development backend loaded `f4f210f` at 2026-10-11 23:19 CDT, PID 1128830, healthy with zero leases; frontend served `a96b18a`. Production remains `ff87c22`.
- GitHub reports no combined-status contexts for the four implementation commits; the labeled coordinator receipts, reports, local gates, browser evidence, and timestamped host observation are the acceptance evidence. These slices are not production loaded, not LIVE_VERIFIED, and not OWNER_ACCEPTED / DONE.
- Production Transportation LIVE_VERIFY remains separately blocked on a current signed-in authorized production role plus a labeled driver and vehicle. The prior coordinator session refused production SSH reads/writes; this does not block compatible development work.
- **ONE current bounded task:** `careops-transport-resources-001`. Audit the existing Transportation resources UI by owner/admin, Transportation staff, and an unauthorized role. State exactly what is required before a ride can be assigned; make driver, vehicle, linked login/My rides, buffer behavior, role refusal, and empty/error states understandable. Reuse canonical driver/vehicle records and current endpoints; no new queue/store, production mutation, paid service, audio work, or parallel worker.
- Dispatch is recorded in Issue #129. The existing coordinator `caoscare-1-ee` must publish ACK/WORKING with responsible worker, reviewed evidence, realistic ETA, exact America/Chicago `next_check_at`, expected acceptance evidence, and blocker `NONE` by Sunday, October 11, 2026 — 11:26 PM America/Chicago, or the existing local watchdog publishes an exact NEED/BLOCKED receipt.


---

## Correction / checkpoint — 2026-10-11 23:24 CDT — Transportation resources already complete; calendar repair dispatched

The 23:21 supervisor dispatch of `careops-transport-resources-001` raced with the coordinator's completion and is explicitly superseded; no duplicate worker was created.

- `careops-transport-resources-001` is **DEV_ACCEPTED** at `11fe3f2734acff1e104b9f6c5cfb9994a9e789bf`: frontend 81 suites / 607 tests, production build compiled, isolated browser 8/8. The canonical Transport resources screen now explains its purpose, driver/vehicle prerequisites, login-linked **My rides**, buffer behavior, role expectations, and whether the current records are sufficient to book a ride. Development frontend serves the commit; backend remains `f4f210f`. Timestamped host observation Sunday, October 11, 2026 — 11:22 PM America/Chicago: development `:8092` healthy. Production remains `ff87c22`; not LIVE_VERIFIED or OWNER_ACCEPTED / DONE. GitHub exposes no combined-status contexts for the commit.
- **ONE current bounded task:** `careops-transport-calendar-001`. Reproduce the owner-reported empty/unchanged calendar with labeled dated rides; repair the first proven display/navigation/filter defect using canonical ride records; ensure each row/card opens its real request; distinguish no rides from load failure; prove authorized/refused roles plus desktop/390 px behavior. No new calendar store, production mutation, paid service, audio work, or parallel worker.
- Issue #129 is the dispatch channel. Existing coordinator `caoscare-1-ee` must publish ACK/WORKING with evidence-based ETA, exact America/Chicago `next_check_at`, expected acceptance, and blocker `NONE` by Sunday, October 11, 2026 — 11:29 PM America/Chicago, or the existing local watchdog publishes exact NEED/BLOCKED.


---

## 2026-10-11 23:39 CDT — Transportation calendar DEV_ACCEPTED; clinician workspace audit dispatched

Coordinator receipt [#6117835788](https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6117835788) proves `careops-transport-calendar-001` **DEV_ACCEPTED** at [`922919e`](https://github.com/caosos/CAOSCARE.COM/commit/922919e90e1bd3938e113f27b03989177600089d) plus [`7a7cd92`](https://github.com/caosos/CAOSCARE.COM/commit/7a7cd92e3dd1c4766f9be81a472133e85800026c): backend 559 passed / 0 failed / 31 skipped; frontend 82 suites / 609 tests; build compiled; browser 14/14. Development backend loaded `7a7cd92` at PID 1144062, dev `:8092` healthy, zero leases, observed Sunday, October 11, 2026 — 11:36:56 PM America/Chicago. GitHub exposes no combined-status contexts. Production remains `ff87c22`; this slice is not production loaded, LIVE_VERIFIED, or OWNER_ACCEPTED / DONE.

User-visible result: an empty Transportation calendar day now shows the next dates containing rides, provides one-tap date jumps, reports open requests dated before the facility-local current day, and uses the facility date instead of UTC.

**ONE current bounded task:** `careops-clinician-workspace-001`. Audit the existing clinician route and intended authorized role; define the allowed operational job; complete the first truthful normal-work path with purpose, next action/result, empty/load-failure state, authorization refusal, desktop and 390 px browser proof. Hide or relabel a misleading dead route if no canonical workflow exists. Reuse canonical StaffTask/receipt/state records. No clinical diagnosis/chart data, billing, provider registry, new truth store, production mutation, external messaging, audio, or paid service.

Issue #129 is the dispatch channel to existing coordinator `caoscare-1-ee`. ACK/WORKING is required by Sunday, October 11, 2026 — 11:45 PM America/Chicago, or the existing local watchdog must publish exact NEED/BLOCKED. ETA is UNKNOWN pending the coordinator receipt. Blocker: NONE.


---

## 2026-10-11 23:53 CDT — clinician workspace DEV_ACCEPTED; menu visibility dispatched

- `careops-clinician-workspace-001` is **DEV_ACCEPTED** at `677e2506f4e4a7837eae343ccbfde97ae2f28635`. Coordinator receipt #6117969982 reports backend 566 passed / 0 failed / 31 skipped; frontend 84 suites / 614 tests; compiled build; browser plus API 14/14. Development backend loaded `677e250`, PID 1167977, dev `:8092` healthy with zero leases, observed Sunday, October 11, 2026 — 11:51:28 PM America/Chicago. GitHub exposes no combined-status contexts. Production remains `ff87c22`; not production loaded, LIVE_VERIFIED, or OWNER_ACCEPTED / DONE.
- User-visible result: **Resident care patterns** explains its purpose, distinguishes load failure, opens each event’s real close-out, flags older open records, fills its summary from the resident briefing, and refuses Kitchen/front-desk roles; owner/admin and Nursing retain access.
- **ONE current bounded task:** `careops-menu-visible-001`. Trace the current publish/lookup path with one labeled dated breakfast/lunch/supper; prove the published menu appears in authorized operator and resident views and that “what’s for supper tonight?” returns the actual meal or an honest no-menu state. Reuse canonical menu/version records and existing routes. Exclude production mutation, new truth stores, external messaging, paid services, audio work, and parallel workers.
- Issue #129 dispatches to existing coordinator `caoscare-1-ee`. ACK/WORKING is required by Sunday, October 11, 2026 — 11:58 PM America/Chicago with realistic ETA, exact next check, acceptance evidence, and blocker `NONE` or an exact NEED/BLOCKED receipt.


---

## 2026-10-12 00:06 CDT — menu visibility DEV_ACCEPTED; Activities calendar dispatched

- `careops-menu-visible-001` is **DEV_ACCEPTED** at `4b270ef03fa9a0b79907b8363217faa9916d9c4e`. Coordinator receipt #6118089716 reports backend 567 passed / 0 failed / 31 skipped; frontend 85 suites / 617 tests; compiled build; labeled publish trace 10/10. Development backend loaded `4b270ef`, PID 1177328, dev `:8092` healthy; temporary `:3019` stopped and labeled test data removed, observed Monday, October 12, 2026 — 12:04:09 AM America/Chicago. GitHub exposes no combined-status contexts. Production remains `ff87c22`; not production loaded, LIVE_VERIFIED, or OWNER_ACCEPTED / DONE.
- User-visible result: Menu and Daily schedule now say when nothing is published for the current day and name the last published day. A labeled published menu reached Aria's supper lookup and the resident screen.
- Production menu ends Friday, October 2, 2026, and production Activities has no current published data. That requires authorized Kitchen/Activities staff or Michael to publish content, but it does not block compatible development work.
- **ONE current bounded task:** `careops-activities-calendar-001`. Trace canonical Activities intake/publish data to the Daily schedule with one labeled dated activity; prove authorized staff and resident views show the same event, owner, time, place, and status; distinguish no published events from load failure; prove desktop and 390 px behavior. Reuse canonical schedule/version records. Exclude production mutation, new truth stores, external messaging, paid services, audio work, and parallel workers.
- Issue #129 dispatches to existing coordinator `caoscare-1-ee`. ACK/WORKING is required by Monday, October 12, 2026 — 12:11 AM America/Chicago with realistic ETA, exact next check, acceptance evidence, and blocker `NONE` or an exact NEED/BLOCKED receipt.


---

## Checkpoint — 2026-10-12 01:50 CDT — honest Aria handoff wording DEV_ACCEPTED; Nursing exception lifecycle prepared

- `careops-resident-aria-core-reconciliation-001` remains **DEV_ACCEPTED (typed/demo)**, not spoken-room accepted, LIVE_VERIFIED, READY_FOR_OWNER_REVIEW, or OWNER_ACCEPTED / DONE. Canonical receipt: [#6119091064](https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6119091064). Development backend loaded `aba31a8`; production remains `ff87c22`. Michael's spoken Room 214 voice/personality check remains the firsthand acceptance gate.
- `careops-resident-aria-honest-request-language-001` is **DEV_ACCEPTED**. Coordinator receipts [#6119167547](https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6119167547) and [#6119172960](https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6119172960) prove code `8a06ad1` + `40c3fec`, 390 px title repair `d01796b`, report/PROJECT_STATE `9865cea`, backend 591 passed / 0 failed / 31 skipped, frontend 87 suites / 627 tests, compiled build, a live typed request/status trace, and Nursing `/staff` at 390 and 1280 without overflow or failed API calls. Development backend loaded `8a06ad1`; frontend served `d01796b`. Aria now says the request is on the Nursing list and explicitly refuses to promise that someone is on the way until evidence exists.
- GitHub exposes no combined-status contexts for these local acceptance commits; the labeled coordinator gate, typed trace, Claude Chrome/browser evidence, exact loaded revisions, and timestamped host receipt are the applicable evidence. Latest timestamped host observation remains Monday, October 12, 2026 — 1:37:33 AM America/Chicago; GitHub activity is not host-liveness proof.
- The open labeled demo request `task_134116c5c444` is preserved for canonical cleanup/review; it is not treated as real resident work.
- **ONE current bounded task prepared:** `careops-nursing-exception-lifecycle-001`. Using only canonical StaffTask and receipt paths, prove a labeled synthetic Nursing request through reassignment, unable-to-complete with reason, escalation, supervisor review, and a truthful resident/Aria status at each stage. Verify intended worker/supervisor permissions, unauthorized refusal, linked receipts, queue/history/count reconciliation, desktop and 390 px behavior, exact tested/loaded revisions, and a fresh host observation. Reconcile or close the existing labeled demo request only after its test provenance is confirmed. No production mutation, external messaging, paid provider action, audio work, new truth store, or duplicate coordinator/worker/session/queue/watchdog/monitor.
- **Blocker:** NONE for the prepared development task. Separate dependencies remain: spoken Room 214 acceptance by Michael; no Home Assistant media player; Midea AC unavailable; RESEND_API_KEY unset; research provider unset; no Asterisk/Twilio/SIP.


---

## Correction — 2026-10-12 02:09 CDT — Nursing exception lifecycle acceptance remains open

- Coordinator DONE [#6119393963](https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6119393963) proves substantial completion of `careops-nursing-exception-lifecycle-001`: code `d16b3c7`, records `f2f61e8`, backend 592 passed / 0 failed / 31 skipped, frontend 87 suites / 628 tests, compiled build, guarded development restart with zero leases, nurse 390 px cannot-complete, truthful typed Aria status, owner Claude Chrome review, nurse reclaim/complete, and 8 linked receipts on one workflow.
- **Acceptance correction:** the written task required reassignment proof in the live browser flow. The canonical report explicitly says the admin queue reassignment dropdown was **not clicked live**; reassignment was covered only by automated tests and the nurse later reclaimed the task. Therefore this slice is **IMPLEMENTED / TESTED / PARTIAL DEV_ACCEPTED**, not fully DEV_ACCEPTED, READY_FOR_OWNER_REVIEW, LIVE_VERIFIED, or OWNER_ACCEPTED / DONE.
- The coordinator's append-only 2:02 AM ledger entry calling the whole task DEV_ACCEPTED is preserved and explicitly superseded by the supervisor receipt for this correction.
- **ONE current bounded task remains:** `careops-nursing-exception-lifecycle-001`, stage ACCEPTANCE REPAIR. In Claude Chrome, use a labeled synthetic Nursing request and the existing owner/admin assignment dropdown to change assignment to a named Nursing worker; verify the canonical task/workflow remains one record, the `task_assigned` receipt captures actor authority plus before/after assignee, unauthorized roles cannot reassign, the assigned nurse sees the work, Aria reports the actual state, and desktop/390 px remain clean. If the live path fails, repair only that proven gap, rerun focused/full gates, load the exact accepted revision, record a fresh host observation, and update the report/checklist/PROJECT_STATE/ledger.
- **Blocker:** NONE. Michael action: NOTHING now.


### Update 2026-10-12 02:27 CDT (Nursing exception lifecycle DEV_ACCEPTED; unclaimed escalation prepared)

- **Completion receipt — `careops-nursing-exception-lifecycle-001`:** DEV_ACCEPTED, not OWNER_ACCEPTED / DONE, on backend `d16b3c7`, frontend repair `1af968fb228216b0d849e2101edbcfbd0a13c36b`, and records/report `6b2070e0f014933555cc286670ec9e81be0353f0`. Canonical coordinator DONE: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6119594909; transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6119616084.
- **Defect and repair:** Claude Chrome exposed that admin Nursing cards remounted during renders, closing the assignment list before a choice landed. `1af968f` converts the nested components to stable render functions and adds `departmentQueueStableCards.test.js`, which fails on the old code.
- **Gates and browser evidence:** backend 592 passed / 0 failed / 31 skipped; frontend 88 suites / 629 tests; build compiled. Owner assigned synthetic task `task_789c03588ae8` to Demo - Nancy Reyes RN in Claude Chrome; `task_assigned` records actor MICHAEL CHAMBERS, `admin_override:owner`, null → nurse and the original workflow id. Maintenance reassignment was refused 403. The nurse saw it under Assigned to me at 390 and 1280 px with no overflow or failed API calls. Typed Aria trace `rt_62sib2cc_1791789384982` truthfully said staff acknowledged it and work had not started.
- **Tested versus loaded:** backend tested/loaded `d16b3c7`; frontend tested/served `6b2070e` including `1af968f`; production remains `ff87c22`.
- **Host observation:** Monday, October 12, 2026 — 2:19:53 AM America/Chicago from the transport bridge: existing coordinator `caoscare-1-ee` idle and the control-plane process alive on `c43919bceb56`. This is host/process evidence, not the product loaded-revision proof above.
- **Verdict:** the bounded Nursing exception lifecycle is ready to be presented for owner review, but the broader Care Operations section is not READY_FOR_OWNER_REVIEW and nothing is marked `[x]`.
- **Next single bounded task:** `careops-nursing-unclaimed-escalation-001` through the existing coordinator. Use the canonical StaffTask/escalation path; create no new queue, truth store, timer service, coordinator, worker, watchdog or monitor. Prove deterministic one-time escalation of a pending/unassigned Nursing request, idempotency, stop conditions, truthful Aria status, supervisor visibility, refusals, desktop/390 px behavior, exact tested/loaded revisions and fresh host evidence. No external delivery, production mutation, audio/Hey Aria work, or PR #41/#42/#131 merge.
- **Blocker:** NONE for this development slice. Michael action: NOTHING.


### Update 2026-10-12 02:59 CDT (Nursing unclaimed escalation DEV_ACCEPTED; Housekeeping exception lifecycle prepared)

- **Completion receipt — `careops-nursing-unclaimed-escalation-001`:** DEV_ACCEPTED, not OWNER_ACCEPTED / DONE. Canonical DONE: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6120078175; transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6120099631.
- **Implementation / records:** `e2a87701275c714387848bdf64926f1e843b626f` code, `28c0729` labels/report, `743c4d2` records. The one existing escalation tick flags current pending/unassigned Nursing requests after `nursing_unclaimed_seconds` (default 600) exactly once via an atomic claim and canonical lifecycle receipt `task_unclaimed_escalated`; the request stays open; assigned, closed and review-bucket records skip; no SMS/email is sent.
- **Gates and browser:** backend 593 passed / 0 failed / 31 skipped; frontend 88 suites / 631 tests; build compiled. Typed request `task_63bc1794b15d` was flagged by the live tick; owner saw Unclaimed, flagged (1) and the Nursing badge in Claude Chrome; nurse at 390 px had no overflow or failed API calls; maintenance did not see it; typed Aria `rt_xl5l4ezc_1791791425175` was truthful; after nurse claim, it disappeared after two more ticks and retained one flag receipt.
- **Tested versus loaded:** backend tested/loaded development revision `e2a8770` with background tick enabled after a guarded restart and zero leases; frontend tested/served `743c4d2`; production `ff87c22` unchanged.
- **Host observation:** Monday, October 12, 2026 — 2:54:51 AM America/Chicago from the transport bridge: existing coordinator idle; control-plane service loaded `191d76a3eca2`; repository `ff930e5638bd` was newer and not loaded. This is control-plane/repository evidence; the CAOSCare product loaded revisions are established by the canonical DONE/report.
- **Limits:** Nursing only; one flag per request; supervisor notification remains inside CAOSCare. Broader alert escalation policy is still open.
- **Next single bounded task:** `careops-housekeeping-exception-lifecycle-001` through the existing coordinator. Reuse canonical StaffTask/receipts and existing exception controls; inspect first, repair only the first proven gap, then prove a labeled Housekeeping room/area request through claim/start/cannot-complete/review/reassign-or-reclaim/complete with role refusals, truthful status, responsive UI and an unbroken receipt chain.
- **Blocker:** NONE. Michael action: NOTHING.


### Update 2026-10-12 03:20 CDT (Housekeeping exception lifecycle DEV_ACCEPTED; scheduled work prepared)

- **Completion receipt — `careops-housekeeping-exception-lifecycle-001`:** DEV_ACCEPTED, not OWNER_ACCEPTED / DONE. Canonical DONE: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6120319393; transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6120332842.
- **Implementation / records:** backend unchanged at `e2a8770`; department-neutral exception-dialog wording `8ed21cd6dbda30a4a4514deadb9cd2a65b53a704`; report `docs/reports/2026-10-12-housekeeping-exception-lifecycle.md`; records `347d2e6`+. The shared DepartmentQueue and canonical task lifecycle already supported the workflow; the only proven product gap was nurse-specific example text on Housekeeping dialogs.
- **Gates and browser:** backend 593 passed / 0 failed / 31 skipped; frontend 88 suites / 631 tests; build compiled. Typed Aria created `task_256b9f7a6c7f`; a demo housekeeper at 390 px claimed, started and could not complete with reason; owner reviewed and assigned Demo - Rosa Vega in Claude Chrome; Housekeeping completed; Nursing/Maintenance actions returned 403; Aria stayed truthful; eight provenance-linked transitions remained on one workflow; queue/history/counts reconciled; no failed API calls or overflow.
- **Tested versus loaded:** development backend tested/loaded `e2a8770`; frontend tested/served `8ed21cd`; production remains `ff87c22` unchanged.
- **Host observation:** Monday, October 12, 2026 — 3:11:39 AM America/Chicago from the transport bridge: existing coordinator `caoscare-1-ee` idle; control-plane service and repository were both `82b625303080`. GitHub activity alone is not host-liveness proof.
- **Verdict:** the bounded Housekeeping exception lifecycle is ready to present for owner review. The full Housekeeping and Care Operations sections remain incomplete and are not OWNER_ACCEPTED / DONE.
- **Next single bounded task:** `careops-housekeeping-schedule-001` through the existing coordinator. Reuse the canonical StaffTask requested date/time, room/area location, Housekeeping queue, lifecycle service and receipts. Prove one labeled future job through authorized schedule/create, upcoming visibility, reschedule, start/complete, truthful status, refusal, desktop/390 px, exact tested/loaded revisions and fresh host evidence. Inspect first and repair only the first proven gap. Stop before recurrence, inspections, supplies/linen, external delivery, production mutation, audio/Hey Aria, duplicate infrastructure, or PR #41/#42/#131 merge.
- **Blocker:** NONE. Michael action: NOTHING.


### Update 2026-10-12 03:42 CDT (Housekeeping scheduling DEV_ACCEPTED; recurrence prepared)

- **Completion receipt — `careops-housekeeping-schedule-001`:** DEV_ACCEPTED, not OWNER_ACCEPTED / DONE. Canonical DONE: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6120747546; transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6120769216.
- **Implementation / records:** `af52bfa454ed8d82b48f943e97f8577f51369c19` adds the Housekeeping Upcoming panel to staff and Admin, refreshes it after queue changes, and refuses ride creation for in-room work; `8d03c65d67d0ebbe11c799edce286f25a4d8608f` makes Aria read every open request in the requested department. Report: `docs/reports/2026-10-12-housekeeping-schedule.md`.
- **Gates and browser:** backend 594 passed / 0 failed / 31 skipped; frontend 88 suites / 633 tests; build compiled. Front desk entered two future jobs; owner in Claude Chrome scheduled and rescheduled them; Upcoming ordered them by facility date/time immediately; nurse reschedule returned 403; housekeeper at 390 px saw both with no overflow or failed API calls; resident display matched; Aria trace `rt_dfwi8v3i_1791794082799` named both jobs and times; completion removed the finished job from Upcoming. The canonical workflow retained created → schedule_updated → schedule_updated → in_progress → completed receipts.
- **Tested / loaded:** development backend tested/loaded `8d03c65`; frontend tested/served `af52bfa`; production remains `ff87c22` unchanged. Latest host/process observation Monday, October 12, 2026 — 3:41:19 AM America/Chicago: existing coordinator idle; control-plane service `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. GitHub activity alone is not host-liveness proof.
- **Verdict:** the bounded Housekeeping scheduling slice is ready to present for owner review. Full Housekeeping and Care Operations remain incomplete.
- **Next single bounded task:** `careops-housekeeping-recurrence-001` through the existing coordinator. Inspect and reuse canonical StaffTask scheduling, receipts, and the existing scheduler/tick path. Prove one labeled synthetic weekly room/area series through authorized recurrence creation, deterministic occurrence generation without duplicates, Housekeeping/Admin upcoming visibility, single-occurrence reschedule, completion, truthful resident/Aria status, unauthorized refusal, desktop/390 px, focused/full gates, exact tested/loaded revisions, and fresh host evidence. Repair only the first proven gap. Stop before inspection, supplies/linen, external delivery, production mutation, audio/Hey Aria, duplicate infrastructure, or PR #41/#42/#131 merge.


### Update 2026-10-12 04:03 CDT (Housekeeping recurrence DEV_ACCEPTED; inspection prepared)

- **Completion receipt — `careops-housekeeping-recurrence-001`:** DEV_ACCEPTED, not OWNER_ACCEPTED / DONE. Canonical DONE: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6121076424; transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6121083277.
- **Implementation / records:** `6cb1f2c6c2c19682b625c9cbcc24fe6f1b16fdb2` repairs the canonical series fields and adds one facility-date recurrence generator on the existing tick and Generate now path, occurrence-key deduplication, planned department occurrences, system-origin receipts, receipted create/delete, resident visibility, and future-occurrence escalation exclusion. `93c3c58847caea8422a55c516ddcbb8bed87442d` closes legacy same-day deduplication and user-message regressions. Report: `docs/reports/2026-10-12-housekeeping-recurrence.md`.
- **Gates and browser:** backend 595 passed / 0 failed / 31 skipped at `93c3c58`; frontend 89 suites / 635 tests; build compiled. The first backend run at `6cb1f2c` failed two stale tests; both were corrected before the green gate. In Claude Chrome the owner created a Wednesday 11:00 AM weekly Housekeeping series; the existing tick generated exactly one October 14 occurrence 23 seconds later; Admin Upcoming showed it; owner moved only the occurrence to 1:00 PM; later ticks did not duplicate or refill it and the series remained 11:00 AM. Nurse reschedule returned 403; Housekeeping at 390 px completed it without overflow or failed API calls; Aria trace `rt_534cie2z_1791795162596` named the open Housekeeping jobs and times; Generate now truthfully reported that all due occurrences existed. Receipts remained spawned_from_template → schedule_updated → in_progress → completed on one workflow.
- **Tested / loaded:** development backend tested/loaded `93c3c58`; relevant frontend tested/served with the recurrence changes; production remains `ff87c22` unchanged. Latest host/process observation Monday, October 12, 2026 — 4:02:17 AM America/Chicago: existing coordinator idle; control-plane service `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. GitHub activity alone is not host-liveness proof.
- **Verdict:** the bounded Housekeeping recurrence slice is ready to present for owner review. Full Housekeeping and Care Operations remain incomplete.
- **Next single bounded task:** `careops-housekeeping-inspection-001` through the existing coordinator. Inspect and reuse the canonical completed Housekeeping StaffTask, lifecycle, history, receipts, queue, and reopen path. Prove one labeled synthetic completed room/area job through owner/admin inspection; receipted pass or return-for-correction with required reason; same-task reopen/reassignment; corrected completion; truthful resident/Aria status; unauthorized refusal; desktop/390 px; focused/full gates; exact tested/loaded revisions; and fresh host evidence. Repair only the first proven gap. Stop before supplies/linen inventory, external delivery, production mutation, audio/Hey Aria, duplicate infrastructure, or PR #41/#42/#131 merge.


### Update 2026-10-12 04:16 CDT (Housekeeping inspection DEV_ACCEPTED / READY_FOR_OWNER_REVIEW; supplies/linen prepared)

- **Completion receipt — `careops-housekeeping-inspection-001`:** DEV_ACCEPTED / READY_FOR_OWNER_REVIEW, not OWNER_ACCEPTED / DONE. Canonical DONE: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6121258397; transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6121270043.
- **Implementation / records:** `a38d6d163840557227aab77a1fab228d20c097e4` adds owner/admin-only inspection of completed work: receipted Pass leaves the task completed; Return requires a reason, reopens the same task through the existing receipted path with assignee/provenance intact, records the inspection return, and exposes truthful queue/history/resident/Aria state. `0ae2dac971267f590c91a5276ea09609552d2f2f` removes the duplicate returned-reason line. `daf188fb1eedda86145aefc490b4c05a408b41a5` adds the inspection report and project-state evidence.
- **Tests / browser evidence:** backend 596 passed / 0 failed / 31 skipped at `a38d6d1`; frontend 89 suites / 636 tests; build compiled after `0ae2dac`. In Claude Chrome, one labeled linen task `task_636c8e374136` completed, was returned by the owner with “pillowcases not changed,” showed the same task and reason to Housekeeping at 390 px, refused Housekeeper inspection with 403, produced truthful Aria trace `rt_jzd1fvsk_1791796144287`, was corrected/completed, and then passed by the owner as “Inspected: passed (MICHAEL CHAMBERS).” Ten receipts stayed on one workflow and every history item had a receipt.
- **Tested / loaded:** development backend tested/loaded `a38d6d1`; relevant frontend tested/served through `0ae2dac`; production remains `ff87c22` unchanged. Latest host/process observation Monday, October 12, 2026 — 4:14:58 AM America/Chicago: existing coordinator idle; control-plane service `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. GitHub activity alone is not host-liveness proof.
- **Verdict:** this bounded inspection slice is READY_FOR_OWNER_REVIEW; only Michael’s explicit approval can make it OWNER_ACCEPTED / DONE. Full Housekeeping and Care Operations remain incomplete. `DepartmentQueue.jsx` is 435 lines; split it before or with the next growth.
- **Next single bounded task:** `careops-housekeeping-supplies-linen-001` through the existing coordinator. Inspect and reuse canonical inventory/work-request truth first; prove one labeled synthetic room/area supply-or-linen request through item/quantity, authorized acknowledgement and fulfilment, truthful stock/status where an inventory source exists, refusal, linked receipts/history, Housekeeping/Admin desktop and 390 px, resident/Aria truth, full gates, exact loaded revisions, and fresh host evidence. Repair only the first proven gap. Stop before purchasing, vendor orders, paid commitments, external delivery, production mutation, audio/Hey Aria, duplicate infrastructure, or PR merges.
- **Blocker:** NONE. Michael action: NOTHING.


### Update 2026-10-12 04:22 CDT (Housekeeping supplies/linen ACKED / WORKING)

- **ACK/WORKING receipt — `careops-housekeeping-supplies-linen-001`:** https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6121342527; transport-only mirror https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6121380661.
- **Responsible coordinator / worker / stage:** existing coordinator `caoscare-1-ee` / existing worker `da-4d960cc7c3` / WORKING.
- **Evidence reviewed / plan:** inspect for any canonical inventory or stock source and how Aria `request_staff_help`, the front-desk form, and the department queue capture a supply/linen ask; prove one labeled request end to end; build only the first proven gap; no purchasing or vendor action.
- **Tested / loaded state:** no new product commit or test result at ACK. Development backend reported loaded at `a38d6d1`; prior accepted inspection gates remain backend 596 passed / 0 failed / 31 skipped and frontend 89 suites / 636 through `0ae2dac`; production remains `ff87c22` unchanged.
- **Host observation:** Monday, October 12, 2026 — 4:21:21 AM America/Chicago: coordinator `caoscare-1-ee` busy; control-plane service `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. GitHub activity alone is not host-liveness proof.
- **ETA / next check:** approximately Monday, October 12, 2026 — 5:49 AM America/Chicago; existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 5:19:26 AM America/Chicago.
- **Expected completion evidence:** exact commits; focused/full tests; one labeled desktop and 390 px browser workflow; refusal; resident/Aria truth; linked receipts/history; exact tested and loaded revisions; newest timestamped host observation; cost or UNKNOWN.
- **Blocker:** NONE. Michael action: NOTHING.


### Update 2026-10-12 04:32 CDT (Housekeeping supplies/linen DEV_ACCEPTED; Housekeeping section READY_FOR_OWNER_REVIEW; Therapy recurrence prepared)

- **Completion receipt — `careops-housekeeping-supplies-linen-001`:** DEV_ACCEPTED, not OWNER_ACCEPTED / DONE. Canonical DONE: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6121493509; transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6121513979.
- **Implementation:** `56004757c2e9290ec8d5025e4472fa0546808b06` adds optional validated item/quantity truth to the existing `request_staff_help` path, stores it on the canonical request, carries it to resident and queue views, and has Aria state it truthfully in every lifecycle state. The inspected repository has no inventory/stock source, so no availability or stock claim was invented; front-desk item entry and purchasing remain deliberately unbuilt.
- **Tests / browser evidence:** backend 599 passed / 0 failed / 31 skipped; frontend 90 suites / 638 tests; build compiled. In the development runtime, Aria trace `rt_qynuzxo4_1791796989926` captured 2 towels and 1 warm blanket into task `task_346a767999a8`; owner saw the structured items in Claude Chrome; nurse and maintenance completion attempts returned 403; Housekeeping at 390 px saw, claimed, and completed the request without overflow or failed API calls; Aria trace `rt_hksl8rj0_1791797058299` truthfully reported the accepted/not-started state without an arrival promise. Receipts remained created → assigned → in_progress → completed on one workflow.
- **Tested / loaded:** development backend tested/loaded `5600475`; relevant frontend tested/served with the same change; production remains `ff87c22` unchanged. Latest host observation Monday, October 12, 2026 — 4:29:38 AM America/Chicago: existing coordinator idle; control-plane service `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. GitHub activity alone is not host-liveness proof.
- **Verdict:** `careops-housekeeping-supplies-linen-001` is DEV_ACCEPTED, and the complete Housekeeping section is READY_FOR_OWNER_REVIEW. Only Michael’s explicit approval can mark it OWNER_ACCEPTED / DONE. Full Care Operations remains incomplete.
- **Next single bounded task:** `careops-therapy-recurrence-001` through the existing coordinator. Reuse the canonical recurrence generator and Therapy fields to prove one labeled weekly series through duplicate-free occurrence generation, preserved provider/discipline/location/resident details, Upcoming visibility, a single-occurrence change without altering/refilling the series, lifecycle/receipts, resident/Aria truth, refusal, desktop/390 px, exact tested/loaded revisions, and fresh host evidence. Repair only the first proven gap. Stop before clinical records, staff double-booking policy, real data, production mutation, audio/Hey Aria, duplicate infrastructure, or PR merges.
- **Blocker:** NONE. Michael action: NOTHING.


### Update 2026-10-12 04:41 CDT (Therapy recurrence ACKED / WORKING)

- **ACK/WORKING receipt — `careops-therapy-recurrence-001`:** https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6121650956; transport-only mirror https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6121678819.
- **Responsible coordinator / worker / stage:** existing coordinator `caoscare-1-ee` / existing worker `da-b0882b249a` / WORKING.
- **Evidence reviewed / first gap:** the canonical `task_recurrence.py` and recurring-series fields from the accepted Housekeeping slice; Therapy visits already carry provider_name/discipline/location, but StaffTaskTemplate lacks those fields, so a Therapy series cannot preserve them. The worker will confirm live, add validated fields through the canonical template/occurrence path, then prove one labeled weekly PT series through Therapy/Admin Upcoming, single-occurrence reschedule and cancel without refill, resident/Aria truth, refusals, desktop and 390 px.
- **Tested / loaded state:** no new current-task commit or test result at ACK. Development backend reported loaded at `5600475`; prior accepted supplies/linen gates remain backend 599 passed / 0 failed / 31 skipped and frontend 90 suites / 638; production remains `ff87c22` unchanged.
- **Host observation:** Monday, October 12, 2026 — 4:40:12 AM America/Chicago: coordinator `caoscare-1-ee` busy; control-plane service `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. GitHub activity alone is not host-liveness proof.
- **ETA / next check:** approximately Monday, October 12, 2026 — 5:38 AM America/Chicago; existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 5:38:18 AM America/Chicago.
- **Expected completion evidence:** exact commits; focused/full tests; one labeled desktop and 390 px Therapy workflow; single-occurrence reschedule/cancel without series mutation/refill; refusal; resident/Aria truth; linked receipt/history chain; exact tested/loaded revisions; newest timestamped host observation; cost or UNKNOWN.
- **Blocker:** NONE. Michael action: NOTHING.


### Update 2026-10-12 04:56 CDT (Therapy recurrence DEV_ACCEPTED; permission boundaries prepared)

- **Completion receipt — `careops-therapy-recurrence-001`:** canonical DONE https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6121870528; transport-only mirror https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6121897642.
- **Product:** `92aa098eceda8ec2876a2e5cadb8c5c9a92aedb4` preserves provider/discipline/location on the canonical recurring series and each occurrence; `9571aa025fce522daf31ac9a9799d935c3fbad7a` adds the Admin Therapy queue + Upcoming surface; `468cbc8c159b209d58245f878af14a7d79748409` makes resident schedule answers include their own planned appointments and emits one reply after concurrent tool calls.
- **Gates / development acceptance:** backend 600 passed / 0 failed / 31 skipped at `468cbc8`; frontend 90 suites / 641 tests; build compiled. In Claude Chrome, one labeled weekly PT series generated exactly one detailed occurrence; Admin Therapy showed queue + Upcoming; owner rescheduled it; Housekeeping reschedule returned 403; the resident 390 px screen showed provider/location; Aria trace `rt_tsujpccx_1791798467141` returned Thursday, October 15 at 2:00 PM in the Therapy gym with one lookup/no errors; owner cancelled with reason; later ticks did not refill; series remained Wednesday 10:00 AM. Receipt chain: spawned_from_template → schedule_updated → cancelled.
- **Tested / loaded:** development backend `468cbc8`; relevant frontend served with it; production `ff87c22` unchanged. No Therapy account exists on the dev stack, so therapist-side authorization is in-process-test evidence, not a signed-in browser claim.
- **Host observation:** Monday, October 12, 2026 — 4:54:40 AM America/Chicago: existing coordinator `caoscare-1-ee` idle; control-plane service `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. GitHub activity is not host-liveness proof.
- **Verdict:** IMPLEMENTED / TESTED / DEV_ACCEPTED; full Therapy/appointments remains PARTIAL, not READY_FOR_OWNER_REVIEW or OWNER_ACCEPTED / DONE.
- **Next single bounded task:** `careops-therapy-permission-boundaries-001`, READY / DISPATCHING through the existing coordinator. Prove the operational-versus-clinical boundary and exact role matrix on canonical Therapy task/status data without adding or exposing clinical records. ACK / WORKING is required within 300 seconds after delivery.
- **ETA / blocker / owner action:** ETA UNKNOWN pending ACK; blocker NONE; Michael action NOTHING.


### Update 2026-10-12 05:02 CDT (Therapy permission boundaries ACKED / WORKING)

- **ACK/WORKING receipt — `careops-therapy-permission-boundaries-001`:** https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6121965718; transport-only mirror https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6121993580.
- **Responsible coordinator / worker / stage:** existing coordinator `caoscare-1-ee` / existing worker `da-e7703038b0` / WORKING. ACK arrived before the 300-second deadline.
- **Evidence reviewed / plan:** read the resident-safe projection and every Therapy-touching route; build an isolated HTTP role × action matrix for owner/admin, front desk, Therapy, another department, and resident/public; inspect exactly what reaches residents and Aria; repair only the first proven gap; browser-check where accounts exist.
- **Tested / loaded state:** no new current-task product commit, test, or browser result at ACK. Development backend reported loaded at `468cbc8`; prior accepted recurrence gates remain backend 600 passed / 0 failed / 31 skipped, frontend 90 suites / 641, build compiled; production remains `ff87c22` unchanged.
- **Host observation:** Monday, October 12, 2026 — 5:01:04 AM America/Chicago: coordinator `caoscare-1-ee` busy; control-plane service `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. GitHub activity alone is not host-liveness proof.
- **ETA / next check:** approximately Monday, October 12, 2026 — 6:29 AM America/Chicago; existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 5:59:15 AM America/Chicago.
- **Expected completion evidence:** exact commits; explicit role/field/action matrix; focused/full gates; labeled desktop and 390 px browser evidence where accounts exist; direct API refusals for unavailable roles; resident/Aria safe truth; receipts/history; exact tested/loaded revisions; newest host observation; cost or UNKNOWN.
- **Blocker / owner action:** NONE / NOTHING.

- **DONE (coordinator) — `careops-therapy-permission-boundaries-001`, Monday, October 12, 2026 — 5:27 AM America/Chicago:** IMPLEMENTED / TESTED / DEV_ACCEPTED (not OWNER_ACCEPTED / DONE). Role × action matrix proven over HTTP (`backend/tests/test_therapy_permission_boundaries.py`); no clinical field can be stored (422). First proven gap repaired at `565cfa1`: "can't complete" and supervisor-review reasons no longer reach the resident's screen (they stayed out of Aria's speech already); dialogs say "Staff only". Backend 601 passed + fixed new test / 31 skipped; frontend 90 / 641; build compiled; headless browser nurse 390, resident room 390, owner 1280 on dev backend `565cfa1`. Report `docs/reports/2026-10-12-therapy-permission-boundaries.md` (`7b737ea`). No therapy login on dev, so the Therapy column is API-only. Production `ff87c22` unchanged.


### Update 2026-10-12 05:30 CDT (Therapy permission boundaries DEV_ACCEPTED; staff conflict detection dispatched)

- **Completion receipt — `careops-therapy-permission-boundaries-001`:** canonical DONE https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6122399284; transport-only mirror https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6122412245. Verdict IMPLEMENTED / TESTED / DEV_ACCEPTED, not OWNER_ACCEPTED / DONE.
- **Product / evidence:** `565cfa1` keeps unable-to-complete and supervisor-review reasons out of resident-visible notes and labels those dialogs staff-only. The explicit HTTP role × action matrix rejects clinical fields with 422 and proves the authorized operational actions. Backend 601 passed / 0 failed / 31 skipped plus focused 2/2; frontend 90 suites / 641; build compiled. Browser evidence: nurse at 390 px, resident at 390 px, and owner at 1280 on development; the resident and Aria did not receive the staff-only reason. Report commit `7b737ea`.
- **Tested / loaded:** development backend tested/loaded `565cfa1` (PID 1470556); relevant frontend served with it; production remains `ff87c22` unchanged. Latest host observation Monday, October 12, 2026 — 5:27:55 AM America/Chicago: existing coordinator idle; control-plane service `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. GitHub activity alone is not host-liveness proof.
- **Remaining Therapy gaps:** staff double-booking across residents; then final staff/resident browser acceptance. No Therapy login exists on the development stack, so its current permission evidence is API-only. Completion/cancel/reopen dialogs do not yet explicitly say their entered text is resident-visible; fold that wording check into final browser acceptance unless earlier evidence proves a narrower repair is required.
- **Next single bounded task:** `careops-therapy-staff-conflict-001` through the existing coordinator. Detect the same Therapy staff/provider overlapping across different residents on canonical planned data; require an explicit receipted save-anyway override; preserve recurrence, linked transportation, role boundaries and resident-safe truth; prove desktop/390 px, authorization/refusal, receipts, full gates, exact loaded revisions, and fresh host evidence. ACK / WORKING is required within 300 seconds after delivery.
- **ETA / next check / blocker / owner action:** ETA UNKNOWN pending ACK; existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 5:35 AM America/Chicago; blocker NONE; Michael action NOTHING.


### Update 2026-10-12 05:34 CDT (Therapy staff conflict detection ACKED / WORKING)

- **ACK/WORKING receipt — `careops-therapy-staff-conflict-001`:** https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6122483873; transport-only mirror https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6122520853.
- **Responsible coordinator / worker / stage:** existing coordinator `caoscare-1-ee` / worker `da-ed20c907a6` / WORKING. ACK arrived before the 300-second deadline.
- **Evidence reviewed / plan:** reuse the existing same-resident overlap check in `routes/schedule_conflict.py`, its 60-minute slot, 409 response, receipted save-anyway path, Upcoming conflict line, and canonical `provider_name` / `assigned_to` fields. Extend the same logic to other residents' open Therapy requests sharing the normalized provider name or assignee; prove isolated HTTP, full gates, desktop and 390 px.
- **Tested / loaded state:** no new current-task product commit, test, or browser result at ACK. Development backend remains reported loaded at `565cfa1` from the accepted permission-boundary task; production remains `ff87c22` unchanged.
- **Host observation:** Monday, October 12, 2026 — 5:34:18 AM America/Chicago: coordinator `caoscare-1-ee` busy; control-plane service `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. GitHub activity alone is not host-liveness proof.
- **ETA / next check:** approximately Monday, October 12, 2026 — 6:47 AM America/Chicago; existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 6:47:20 AM America/Chicago.
- **Expected completion evidence:** exact implementation commits; overlap/non-overlap across residents; normalized provider and assignee cases; explicit receipted override; recurrence/single-occurrence/linked-ride preservation; authorization/refusal; resident/Aria safety; desktop/390 px; full backend/frontend/build gates; exact tested/loaded revisions; newest host observation; cost or UNKNOWN.
- **Blocker / owner action:** NONE / NOTHING.

- **DONE (coordinator) — `careops-therapy-staff-conflict-001`, Monday, October 12, 2026 — 5:41 AM America/Chicago:** IMPLEMENTED / TESTED / DEV_ACCEPTED (not OWNER_ACCEPTED / DONE). Same provider or assignee double-booked across residents is now refused unless saved anyway (receipted); provider-only changes checked; nothing written before the choice. `b7f6048`; backend 603/0/31; frontend 90/642; build compiled; browser owner 1280 + 390 on dev `b7f6048`. Report `docs/reports/2026-10-12-therapy-staff-conflict.md`. Production `ff87c22` unchanged.


### Update 2026-10-12 05:43 CDT (Therapy staff conflict DEV_ACCEPTED; final Therapy browser acceptance dispatched)

- **Completion receipt — `careops-therapy-staff-conflict-001`:** canonical DONE https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6122651596; transport-only mirror https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6122660781. Verdict IMPLEMENTED / TESTED / DEV_ACCEPTED, not OWNER_ACCEPTED / DONE.
- **Product / evidence:** `b7f6048` extends the canonical 60-minute conflict check across residents for the same normalized provider name or assignee, checks provider-only changes before any write, reuses the 409 + explicit save-anyway path, receipts overrides on schedule/details, preserves recurrence and linked rides, and keeps conflicts out of resident views. Backend 603 passed / 0 failed / 31 skipped; frontend 90 suites / 642; build compiled. Owner 1280 and 390 px browser evidence showed the named conflicting appointment/room/shared provider, no write before choice, receipted override in Upcoming, nurse 403, no overflow or failed API calls; synthetic requests were cancelled.
- **Tested / loaded:** development backend tested/loaded `b7f6048`, PID 1478496; production `ff87c22` unchanged. No GitHub workflow runs were attached to `b7f6048`; the recorded local gates/browser receipt are the acceptance evidence.
- **Host observation:** Monday, October 12, 2026 — 5:42:36 AM America/Chicago: existing coordinator idle; control-plane service `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. GitHub activity alone is not host-liveness proof.
- **Known limits:** no persistent Therapy login exists on the development stack; claim/assign alone does not warn; provider identity is normalized exact text, not a registry. These limits do not invalidate the accepted bounded conflict task and are carried into final browser acceptance where applicable.
- **Next single bounded task:** `careops-therapy-browser-acceptance-001` through the existing coordinator. Prove the complete labeled synthetic Therapy workflow in the development runtime across authorized staff, a signed-in Therapy role using existing or temporary dev-only auth where safe, resident Home, and Aria; prove desktop/390 px, receipts, refusals, clinical-field rejection, recurrence/Upcoming/conflict/ride truth, and explicit resident-visible wording for completion/cancel/reopen. Clean up synthetic state. If all written criteria pass, reconcile and present the full Therapy section READY_FOR_OWNER_REVIEW. ACK / WORKING is required within 300 seconds after delivery.
- **ETA / next check / blocker / owner action:** ETA UNKNOWN pending ACK; existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 5:48 AM America/Chicago; blocker NONE; Michael action NOTHING.


### Update 2026-10-12 05:47 CDT (Final Therapy browser acceptance ACKED / WORKING)

- **ACK/WORKING receipt — `careops-therapy-browser-acceptance-001`:** https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6122696055; transport-only mirror https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6122727208.
- **Responsible coordinator / worker / stage:** existing coordinator `caoscare-1-ee` / worker `da-13af1cbe1d` / WORKING. ACK arrived before the 300-second deadline.
- **Evidence reviewed / first likely gap:** complete/cancel/reopen write notes that the resident screen shows and Aria speaks, but those dialogs do not disclose that the entered text is resident-visible. The development stack has no Therapy login.
- **Plan:** prove and label the resident-visible wording if confirmed; create a temporary labeled dev-only Therapy account through the existing owner staff API and remove it afterward; create labeled synthetic residents/tasks; exercise all 12 final acceptance criteria in headless browser for owner, front desk, Therapy, and resident at 1280 and 390 px; verify Aria through real status/schedule endpoints; run full gates; clean up all synthetic state.
- **Tested / loaded state:** no new current-task product commit, automated gate, or browser result at ACK. Development backend remains loaded at `b7f6048` from the accepted staff-conflict task; production remains `ff87c22` unchanged.
- **Host observation:** Monday, October 12, 2026 — 5:46:58 AM America/Chicago: coordinator `caoscare-1-ee` busy; control-plane service `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. GitHub activity alone is not host-liveness proof.
- **ETA / next check:** approximately Monday, October 12, 2026 — 7:15 AM America/Chicago; existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 7:15:02 AM America/Chicago.
- **Expected completion evidence:** exact commits; all 12 final criteria across authorized roles/resident/Aria; explicit resident-visible wording; desktop/390 px; clinical-field rejection and unauthorized refusal; one canonical receipt/history chain; recurrence/Upcoming/conflict/linked-ride truth; full backend/frontend/build gates; exact tested/loaded revisions; clean synthetic-data/account removal; newest host observation; cost or UNKNOWN; section READY_FOR_OWNER_REVIEW only if every criterion passes.
- **Blocker / owner action:** NONE / NOTHING.
- **DONE (coordinator) — `careops-therapy-browser-acceptance-001`, Monday, October 12, 2026 — 5:49 AM America/Chicago:** 32/32 end-to-end checks pass on dev (owner, front desk, temporary signed-in Therapy login, nurse, resident Home 1280/390, Aria status endpoints). Gap repaired `db4317f`: complete/cancel/reopen dialogs now say the text reaches the resident and Aria. Backend 603/0/31 (`b7f6048`, unchanged), frontend 90/642, build compiled. Synthetic data and temp account removed. Report `docs/reports/2026-10-12-therapy-acceptance.md`. **Therapy section: READY_FOR_OWNER_REVIEW** (only Michael can mark OWNER_ACCEPTED / DONE). Limits: no live voice call; resident kiosk 390 px overflow pre-existing. Production `ff87c22` unchanged.


### Update 2026-10-12 05:51 CDT (Therapy READY_FOR_OWNER_REVIEW; canonical alert state dispatched)

- **Completion receipt — `careops-therapy-browser-acceptance-001`:** canonical DONE https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6122762572, corrected records commit https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6122766978, transport-only mirror https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6122791597.
- **Verdict:** all 12 written criteria passed as 32/32 development checks with zero failed API calls. Therapy is READY_FOR_OWNER_REVIEW, not OWNER_ACCEPTED / DONE.
- **Evidence:** backend 603 passed / 0 failed / 31 skipped at `b7f6048`; frontend 90 suites / 642; build compiled. Frontend `db4317f` labels completion notes, cancellation reasons, and reopen reasons as resident-visible and potentially read by Aria. Browser covered owner, demo front desk, temporary labeled Therapy login, and resident Home at 1280/390; Aria used the real status/upcoming endpoints. Unauthorized nurse/front-desk/Therapy actions were refused; clinical diagnosis was rejected 422; recurrence, Upcoming, conflict refusal plus receipted override, linked ride, and one receipt chain all passed.
- **Cleanup / loaded state:** all synthetic requests, ride, recurrence occurrence/series, and temporary account were deleted. Development backend tested/loaded `b7f6048`; development frontend tested/loaded `db4317f`; production remains `ff87c22`. Records/report/screenshots/script are in corrected commit `8533b2aa9cb0ac5f49496df4fafa475f322e19c4`. No GitHub PR-triggered workflow run is attached; the recorded local gates and browser receipt apply.
- **Latest host observation:** Monday, October 12, 2026 — 5:51:06 AM America/Chicago — existing coordinator `caoscare-1-ee` idle; control-plane service `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. GitHub activity alone is not host-liveness proof.
- **Next single bounded task:** `careops-alerts-canonical-state-001` through the existing coordinator. Inventory the competing alert/task/notification state implementations and select one canonical, receipt-backed state contract without creating a new queue, timer, truth store, coordinator, worker, watchdog, or monitor. Preserve accepted Nursing unclaimed escalation. Prove alert creation, acknowledgement, timer/fallback transition, idempotency, terminal/stop conditions, supervisor visibility, unauthorized refusal, resident/Aria-safe truth, desktop/390 px, and explicit compatibility/migration handling. Repair only the first proven gap.
- **Expected completion evidence:** exact implementation and records commits; state-transition matrix; focused and full backend/frontend/build gates; labeled API/browser cases; receipts/history; exact tested/loaded revisions; newest timestamped host observation; cleanup; cost or UNKNOWN.
- **ETA:** UNKNOWN pending ACK.
- **next_check_at:** Monday, October 12, 2026 — 5:56:15 AM America/Chicago; owned by the existing LOCAL watchdog.
- **Blocker:** NONE.
- **Michael must do:** NOTHING.


### Update 2026-10-12 05:57 CDT (canonical alert state ACKED / WORKING)

- **Canonical ACK:** https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6122858667. Transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6122887366.
- **Current task / responsibility / stage:** `careops-alerts-canonical-state-001` / existing coordinator `caoscare-1-ee`, worker `da-2be29b619e` / ACKED, WORKING before the 300-second deadline.
- **Evidence reviewed:** writers of Alert `status`, `escalation_level`, `aria_state`, `live_line_state`; `escalation_tick` (RQ-018 sole escalation authority); notification statuses; StaffTask `needs_review` and unclaimed escalation; canonical receipts.
- **Plan / expected acceptance evidence:** grep every writer; publish the state/transition and compatibility matrix; prove accepted Nursing unclaimed escalation maps cleanly; introduce a failing test for the first conflicting writer before repairing it; run focused/full backend/frontend/build gates; prove supervisor/role behavior, resident/Aria-safe truth, desktop and 390 px; clean synthetic state; record exact tested/loaded revisions, newest host observation, and cost.
- **Current tested/loaded state:** no new current-task revision or gate at ACK. Prior accepted development backend remains `b7f6048`, frontend `db4317f`; production `ff87c22` unchanged.
- **Latest host observation:** Monday, October 12, 2026 — 5:57:31 AM America/Chicago — coordinator `caoscare-1-ee` busy; control-plane service PID 1370098 on `f1db2d358ca1`; repository `cd076d251ab9` newer/not loaded. GitHub activity alone is not host-liveness proof.
- **ETA:** approximately Monday, October 12, 2026 — 7:35 AM America/Chicago.
- **next_check_at:** Monday, October 12, 2026 — 7:35:34 AM America/Chicago; owned by the existing LOCAL watchdog.
- **Blocker:** NONE.
- **Michael must do:** NOTHING.

- **DONE (coordinator) — `careops-alerts-canonical-state-001`, Monday, October 12, 2026 — 6:04 AM America/Chicago:** IMPLEMENTED / TESTED / DEV_ACCEPTED. Inventory + canonical alert contract published (`docs/reports/2026-10-12-alerts-canonical-state.md`). First gap repaired `45bd442`: alert acknowledgement is now atomic, receipted (`alert_acknowledged`, actor/authority/before/after) and history-linked; concurrent acks one winner. Backend 604/0/31; browser nurse 390 + owner 1280 on dev `45bd442`. Open: who may acknowledge (owner decision), actor-less close-out receipts and re-close, direct wander/wearable inserts. Production `ff87c22` unchanged.


### Update 2026-10-12 06:06 CDT (canonical alert state DEV_ACCEPTED; close-out receipts dispatched)

- **Completion receipt — `careops-alerts-canonical-state-001`:** https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6122992084. Transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6123012360.
- **Verdict:** IMPLEMENTED / TESTED / DEV_ACCEPTED; the broader Alerts / escalation section remains incomplete and is not OWNER_ACCEPTED / DONE.
- **Canonical contract:** Alert staff workflow is active → acknowledged → resolved; legacy `escalated` is read-only/open. RQ-018 `escalation_tick` alone changes escalation level and stops after acknowledgement/resolution. StaffTask lifecycle and accepted Nursing unclaimed escalation remain separate and unchanged. Aria/live-line state remains separate.
- **First gap repaired:** product `45bd4427125d07aefa2da3817bbeb903126d02a9` makes acknowledgement one status-guarded atomic write, one `alert_acknowledged` receipt with actor/authority/before/after, and one linked history entry. Repeat acknowledgement returns 404; six concurrent attempts produce one winner, one receipt, and one history entry; legacy `escalated` rows are accepted.
- **Evidence:** backend 604 passed / 0 failed / 31 skipped; focused alert/escalation/dispatch 15/15; frontend unchanged at 90 suites / 642. Headless development browser on `45bd442`: nurse at 390 px acknowledged a synthetic DEMO alert with no overflow or failed API calls; owner at 1280 saw the acknowledgement; receipt `rcpt_43a2883ae8cb` matched history; public room status remained minimal; synthetic alert closed. Records/report/screenshots `eef8e8de410b29cbae938130a7f1eac1876c8468`.
- **Tested/loaded:** development backend `45bd442`, PID 1489371; frontend unchanged from `db4317f`; production `ff87c22` unchanged. No PR-triggered GitHub workflow run attached; recorded local gates/browser evidence apply. Cost UNKNOWN.
- **Latest host observation:** Monday, October 12, 2026 — 6:05:47 AM America/Chicago — existing coordinator idle; control-plane PID 1370098 on `f1db2d358ca1`; repository `cd076d251ab9` newer/not loaded. GitHub activity alone is not host-liveness proof.
- **Deferred policy decision:** which signed-in roles may acknowledge a help alert. This does not block compatible work and is not being sent to Michael as an action request in this transition.
- **Next single bounded task:** `careops-alerts-close-receipts-001`. Repair gap 2: resolve/close currently creates actor-less `alert_completed` receipts and can re-close. Make terminal close one guarded atomic transition, exactly one actor/authority/before/after receipt and linked history entry; prove repeat/concurrent idempotency and legacy `escalated` compatibility. Preserve canonical acknowledgement, RQ-018 escalation, dispatch, public status, resident/Aria safety, and Nursing mapping.
- **Expected evidence:** failing-before/fixed-after tests; exact commit; resolve and close paths; active/acknowledged/legacy-escalated inputs; repeat/concurrent attempts; authorization/refusal without deciding the deferred role-policy gap; linked receipt/history; focused/full gates; desktop/390 px browser; cleanup; exact tested/loaded revisions; newest host observation; cost or UNKNOWN.
- **ETA:** UNKNOWN pending ACK.
- **next_check_at:** Monday, October 12, 2026 — 6:11:15 AM America/Chicago; owned by the existing LOCAL watchdog.
- **Blocker:** NONE.
- **Michael must do:** NOTHING.


### Update 2026-10-12 06:10 CDT (alert close-out receipts ACKED / WORKING)

- **Canonical ACK:** https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6123049176. Transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6123077551.
- **Current task / responsibility / stage:** `careops-alerts-close-receipts-001` / existing coordinator `caoscare-1-ee`, worker `da-6b6a0ace12` / ACKED, WORKING before the 300-second deadline.
- **Evidence reviewed:** `alerts.resolve` accepts active/acknowledged but ignores legacy `escalated`; `alerts.close_alert` includes resolved and can re-close while overwriting `resolved_at` / `resolved_by`; `_close_out` calls `update_receipt_status` without actor, before/after, or a history link.
- **Plan / expected acceptance evidence:** failing tests first; one shared guarded terminal transition for both resolve and close, active/acknowledged/escalated → resolved; exactly one `alert_completed` receipt containing actor/authority/before/after and one linked history entry; repeat/concurrent attempts produce one winner and 409 for the rest with no additional writes; pattern statistics and dispatch remain unchanged; acknowledgement-role policy remains deferred. Then focused/full gates, desktop/390 px browser, cleanup, exact tested/loaded revisions, newest host observation, and cost.
- **Current tested/loaded state:** no new current-task revision or gate at ACK. Prior accepted development backend remains `45bd442`, frontend `db4317f`; production `ff87c22` unchanged.
- **Latest host observation:** Monday, October 12, 2026 — 6:10:08 AM America/Chicago — coordinator `caoscare-1-ee` busy; control-plane service PID 1370098 on `f1db2d358ca1`; repository `cd076d251ab9` newer/not loaded. GitHub activity alone is not host-liveness proof.
- **ETA:** approximately Monday, October 12, 2026 — 7:23 AM America/Chicago.
- **next_check_at:** Monday, October 12, 2026 — 7:23:11 AM America/Chicago; owned by the existing LOCAL watchdog.
- **Blocker:** NONE.
- **Michael must do:** NOTHING.
