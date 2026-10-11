# CAOSCare — Living Product Build Checklist

Updated: 2026-10-11 (16:54 CDT; exact-SHA production deploy verified, Transportation live workflow pending; owner operator review captured).

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

## Current build control

- **Current phase:** 3/7 — Care Operations workspaces.
- **ONE current bounded task:** `careops-transport-live-001` — Transportation authenticated LIVE_VERIFY on deployed `ff87c22`; the exact-SHA Linode deployment and 12/12 public smoke are complete. Therapy conflict remains DEV_ACCEPTED on integration product `77f83d3` (backend 542 passed/31 skipped, frontend 75 suites/585, browser 17/17), not deployed.
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

Current status: **ACTIVE. Transportation is DEV_ACCEPTED; release/live verification is the current bounded slice.**

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

- [~] Request/task, queue, assignment, progress, completion, and receipt paths exist in part.
- [ ] Room/area schedule, recurring work, inspection, supplies/linen, unable-to-complete, and supervisor review.
- [ ] Staff browser acceptance.

### Therapy and appointments

- [~] Therapy provider/discipline, appointment, recurrence, location, transport need, attendance, cancellation/reschedule, notes/status, and resident-facing schedule. DEV_ACCEPTED 2026-10-11 for one non-recurring appointment (`careops-therapy-appointment-001`): entered at the front desk → therapy shared queue → planned window (Plan) → reschedule → resident Home screen + Aria show it → attendance (complete) with a 6-receipt linked chain; second appointment cancelled with a reason (`task_cancelled`). Scratch-stack headless 21/21 with a synthetic therapist (`docs/reports/2026-10-11-therapy-appointment-acceptance.md`). Transport link DEV_ACCEPTED later the same day (`careops-therapy-transport-link-001`): "Ride" on a planned appointment creates or attaches exactly one ordinary transportation request through the existing core, linked both ways with receipts; reschedule/cancel of the appointment follow to the ride; scratch-stack headless 15/15 (`docs/reports/2026-10-11-therapy-ride-link-acceptance.md`). Provider/discipline/location DEV_ACCEPTED later the same day (`careops-therapy-details-001`): optional operational fields on the same StaffTask, receipted before/after, shown in the queue, the resident Home screen and Aria's status; scratch-stack headless 13/13 (`docs/reports/2026-10-11-therapy-details-acceptance.md`). Same day: the admin/front-desk request detail dialog shows and edits the same three fields through the same PATCH (frontend 72 suites / 570; report addendum). Date-ordered upcoming view DEV_ACCEPTED later the same day (`careops-therapy-upcoming-view-001`): `GET /tasks/upcoming` + `GET /tasks/resident-request/upcoming` over the canonical rows (facility day → planned time → created), Upcoming panel in the therapy workspace and "Coming up" on the resident Home screen with details, lifecycle and ride truth; admin edits details in the detail dialog with an admin_override receipt, front desk read-only; scratch-stack headless 25/25 (`docs/reports/2026-10-11-therapy-upcoming-acceptance.md`). Not built: recurrence.
- [ ] Permission boundaries for operational versus clinical information.
- [~] Calendar conflict detection and linked transportation request. Conflict detection DEV_ACCEPTED 2026-10-11 (`careops-therapy-conflict-001`): same-resident overlap over the canonical planned fields with one 60-min slot, warned in Plan/detail/Upcoming, saved only on an explicit "Save anyway" that is receipted (`conflict_override`, overlapped ids), honest when a time is unreadable; linked ride follows an overridden reschedule; scratch-stack headless 17/17 (`docs/reports/2026-10-11-therapy-conflict-acceptance.md`). Linked transportation request DEV_ACCEPTED earlier (ride link). Staff double-booking across residents not checked.
- [ ] Staff and resident browser acceptance.

### Alerts / escalation

- [!] Canonical state model is unresolved; historical evidence records competing implementations.
- [!] Automatic timer/rule behavior is not accepted.
- [ ] One escalation model, policy editor, acknowledgements, timers, fallback, receipts, and acceptance test.

Milestone: each department has a normal-work workspace, not a dead demo panel.

### Owner operator review — 2026-10-11 16:49–16:54 CDT (punch list; no duplicate worker dispatched)

Michael inspected the production Care App and reported these concrete gaps. His screenshots and narrated review are owner observation, not authenticated browser acceptance by the supervisor. Existing partial functions remain [~] until the intended operator can complete them. The current single worker task stays `careops-transport-live-001`; the first next eligible correction after its live verdict is the department staffing/dispatch view, unless the coordinator documents an exact blocker and takes that compatible item sooner.

| Priority / area | Observed state or question | Acceptance for one bounded follow-up |
|---|---|---|
| P0 Transportation | Owner can see New ride and filters, but cannot use New order / unresolved count; calendar looks unchanged. | In the deployed signed-in role, create/open/change/cancel a labelled test ride, click each unresolved row to its canonical detail, verify driver/vehicle assignment and receipts, and record any role-specific failure. Do not call the 12/12 public smoke a staff workflow test. |
| P0 Routing truth | “What's for supper tonight?” appears as a Kitchen request, Pending. The screenshot proves creation/routing to a department, not worker delivery or action. | Trace one resident request through department routing, named worker claim/assignment, acknowledgement, completion, and linked receipt; expose undelivered/unassigned/aging work and test that no request silently disappears. |
| P1 Departments & staff | Housekeeping shows open/completed/skipped counts but no department roster, per-worker assignment, dispatch trail, or usable completed history; Activities similarly lacks worker/work view. | Department page shows members and roles, open/assigned/in-progress/done work by named worker, dispatch/status timestamps, completed history and receipts; authorized manager can assign/reassign, staff can act within scope. |
| P1 Navigation | Kitchen and Transportation are absent from the operations overview list despite separate screens. “Daily schedule” contains activities and is empty; owner wants activities under Activities, with resident and transport schedules in their own contexts. | Navigation labels/routes match actual operator jobs; Kitchen and Transportation are discoverable in operations; activities calendar and resident/transport schedules open from their relevant workspaces without duplicate records. |
| P1 Menu & Activities | No useful menu is visible; owner cannot paste a whole menu. Activities lacks populated schedule and work ownership. | Paste/import a full menu into review, validate/date meals, publish once and confirm resident “supper tonight” lookup against the published version; show activity events, responsible staff, and resident-facing schedule with clear empty states. |
| P1 Family & clinician | Family contacts can be copied/deleted but owner cannot edit; clinician dashboard is “totally unusable.” | Authorized operator can add/edit a family contact and see the save/receipt; clinician view has a stated user/job and a usable normal-work path, or is hidden until one is accepted. |
| P1 Operator guidance | Several screens and controls do not explain purpose or next action; Transportation resources show drivers/vehicles/buffer without workflow explanation. | Each operational section has plain-language purpose, required setup, role permissions, action results, and meaningful empty/error states; test with an operator unfamiliar with the code. |
| P2 Email provider | UI reports provider key, sender address and webhook secret unset. | Show configuration status honestly, give the exact setup dependencies, then prove real inbound/outbound delivery with receipts when existing provider/account access is supplied; no paid commitment or “live” claim from mocks. |

Owner review does **not** mark any section OWNER_ACCEPTED / DONE. Reconcile each correction against the canonical StaffTask, department, appointment, menu and receipt records. Preserve the current task and claim only one eligible follow-up through the existing coordinator. For the Transportation production test, first check whether an authorized session or existing labelled driver/vehicle is already available; do not re-ask Michael for routine release permission. If a real owner login or production data choice is indispensable, publish one structured NEED with exact missing access/action and continue the staffing/dispatch slice.

### PR and working-tree reconciliation — 2026-10-11 17:00 CDT

- **Active product:** `main` is `ff87c22`; integration is 73 commits ahead and 0 behind. This is code drift, not a claim that all later slices passed production acceptance.
- **Eight open PRs, zero ready for immediate Care Operations merge:** #110 menu parser draft conflicts with integration, whose existing parser/test already covers the three reported cosmetic cases in a different way; inspect semantics before any rebase. #105 Desktop-Agent project-package draft conflicts and its `.agentproject/project.yaml` is absent on integration. #67 Agent Control Plane is open/conflicting with old green CI and lacks current-base/host acceptance. #45 is an old conflicting hardware docs draft. #41/#42 are explicitly parked public onboarding drafts. #46 wake research and #23 voice remain parked outside this lane. None was merged or closed in this review.
- **Working tree:** this cloud supervisor can verify GitHub commits and its own clean scratch review clone; it cannot inspect the actual EliteDesk `~/CAOSCARE-INTEGRATION` worktree. Do not claim host changes are committed or clean without a timestamped host `git status`.
- **NEED_HOST_RECOVERY:** `da-ba92a5f535` was delivered 16:54:31 CDT with no Issue #129 ACK/WORKING after five minutes. Existing local watchdog/coordinator must run `cd ~/CAOSCARE-INTEGRATION && python3 scripts/owner_intake/coordinator_state.py && git status --porcelain=v1 -b && git rev-parse HEAD`, publish timestamped state and ACK/WORKING or an exact recovery NEED. Canonical receipt: Issue #129 comment `6114293012`. This is a missed receipt target, not proof the process stopped; current host liveness UNKNOWN.
- **Next eligible action remains one:** finish authenticated Transportation LIVE_VERIFY on deployed `ff87c22`; if blocked, continue the compatible department staffing/dispatch correction through the same coordinator.

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
