# CAOSCare — Living Product Build Checklist

Updated: 2026-10-11 (05:52 CDT therapy appointment DEV_ACCEPTED and transport-link slice dispatched, America/Chicago).

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
- **Today’s active engineering task:** `careops-therapy-transport-link-001` DISPATCHED 2026-10-11 10:52Z: reuse the canonical therapy StaffTask and existing transportation request engine to add one optional, idempotent linked-ride flow with receipt/provenance evidence; no new appointment/transport truth store, recurrence, billing, external messaging, audio, paid service, production deploy, or destructive real-data action. Predecessor `careops-therapy-appointment-001` is DEV_ACCEPTED at product commit `47674f5329500e9fbb508cca01b5bc1d98906df9` (21/21 isolated browser cases; backend 538 passed/31 skipped; frontend 68 suites/561; build compiled; dev backend restarted on that commit). Earlier today: `careops-frontdesk-callback-001` DEV_ACCEPTED (19/19) after `careops-frontdesk-reopen-001`. Transportation `careops-transport-live-001` remains authorized but blocked on the already-recorded main-push/deploy/live-browser host path.
- **Control issue / dispatch channel:** [#129](https://github.com/caosos/CAOSCARE.COM/issues/129).
- **Completed review:** [PR #130](https://github.com/caosos/CAOSCARE.COM/pull/130), merged into integration.
- **Integration branch:** `integration/2026-09-27`; pre-reconciliation control head `d0718e2b31847b5cf12c50604dcec00b634d638c`; therapy product commit `47674f5329500e9fbb508cca01b5bc1d98906df9`; release-code baseline `f35b4542a1b893357c78c21c4a7c4ce936fd8cff` (later coordinator-only commits may update control records without changing product code).
- **Transportation implementation:** `agent/transport-workspace-workable` at `21b2261f021d152181c94d8c95d006c533b18529`; integration merge `dc2e4ca1ba22aa6a0e81b950f5597f83a9b4c4ba`.
- **Accepted state:** IMPLEMENTED, TESTED, and DEV_ACCEPTED with receipt-backed browser evidence.
- **Not yet accepted:** `main` promotion, exact-SHA Linode deployment, and live browser/receipt verification.
- **Coordinator task:** `careops-transport-live-001` remains the single authorized release task. The prior `da-446d044fa0` Front Desk/Admin acceptance slice never started and is superseded by the coordinator handoff receipt at `58010c2`.
- **Current live worker heartbeat:** coordinator execution is proven through product commit `47674f5`, the 21/21 therapy acceptance report, and guarded dev restart receipt `d0718e2`; deliveries `da-0315a1eb1a` and `da-47650341ef` still lack explicit issue `ACK → WORKING → DONE` receipts. This remains a receipt-compliance gap, not proof of a dead host. The new transport-link task was delivered as `da-5ee2bb4526` at 05:56:01 CDT (Issue comment `6108288104`) and must now receive explicit timestamped ACK/WORKING or a structured NEED.
- **Owner decision required now:** none for `careops-therapy-transport-link-001`. Correction to the prior host instruction: the blocked command was a one-time read-only `ssh ... caoscare-prod 'mongosh ... countDocuments(...)'` production inventory query. The prompt choices were **1 = Yes once**, **2 = allow all `ssh *` without asking**, **3 = No**. Only option **1** matched the already-authorized read-only query; option 2 would have widened permission and was not required. Callback acceptance subsequently completed, so no prompt action is currently requested.
- **Authority reconciliation:** comment `6105970504` records that the later explicit owner authorization in Issue #129 and current PR #130 supersedes the original pre-acceptance no-deploy note. Do not ask Michael to approve the same release again.
- **Recovery evidence:** Desktop-Agent main `14aa2da70933118631a92631f511648de6788e8c` provides five-minute unacked detection and redelivery; controlled recovery evidence is in Desktop-Agent comment `6106188802`. CAOSCare commit `58010c2ed6796ab1bb9245f642fa16cfc5a12af8` repairs the heartbeat probe (11 owner-intake tests passed; live `coordinator_state.py` exits 0). The last proven ACK/WORKING on the retired coordinator is historical, not current liveness.
- **Slack liaison checkpoint:** input processed through thread message timestamp `1791715716.977699` (05:48:36 CDT); that item was a Deal Sniffer supervisor ACK and is cross-project only. The CAOSCare completion/dispatch ACK was then posted at `1791716142.179459` with Issue #129 receipt `6108284581`; no new CAOSCare liaison request was received. The prior Dot Arya permission-scope correction remains recorded; quarantine remains active and no CAOSCare replay is authorized.

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
- [ ] Promote/deploy and LIVE_VERIFY the workflow.

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

- [~] Therapy provider/discipline, appointment, recurrence, location, transport need, attendance, cancellation/reschedule, notes/status, and resident-facing schedule. DEV_ACCEPTED 2026-10-11 for one non-recurring appointment (`careops-therapy-appointment-001`): entered at the front desk → therapy shared queue → planned window (Plan) → reschedule → resident Home screen + Aria show it → attendance (complete) with a 6-receipt linked chain; second appointment cancelled with a reason (`task_cancelled`). Scratch-stack headless 21/21 with a synthetic therapist (`docs/reports/2026-10-11-therapy-appointment-acceptance.md`). Not built: recurrence, provider/discipline, location, transport link, date-ordered schedule view.
- [ ] Permission boundaries for operational versus clinical information.
- [ ] Calendar conflict detection and linked transportation request.
- [ ] Staff and resident browser acceptance.

### Alerts / escalation

- [!] Canonical state model is unresolved; historical evidence records competing implementations.
- [!] Automatic timer/rule behavior is not accepted.
- [ ] One escalation model, policy editor, acknowledgements, timers, fallback, receipts, and acceptance test.

Milestone: each department has a normal-work workspace, not a dead demo panel.

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
| M1 — Transportation usable | Staff creates/opens/changes/cancels and completes trips with receipts in the deployed app | DEV_ACCEPTED; RELEASE GATE PASSED on `ff87c22` (2026-10-11); main promotion + deploy waiting on owner-run commands or permission rule | same day once the two commands run |
| M2 — Core Care Operations loop | Nursing, Maintenance, Front Desk/Admin, and shared service-ticket lifecycle re-accepted on current release | PARTIAL | 2–4 focused workdays after M1 |
| M3 — Coordinated schedules | Transportation + therapy/appointments + resident/staff calendar links accepted | PARTIAL | 3–6 focused workdays after M2 |
| M4 — Remaining departments | Dining, Activities, Housekeeping, Admin/reporting, alerts/escalation usable | PARTIAL / some planned | 5–10 focused workdays |
| M5 — Real communications | Email, then SMS/phone, with real delivery/call receipts | BLOCKED on provider configuration | 1–3 focused days per service after configuration |
| M6 — Pilot acceptance | One real room + staff + communications + recovery; then repeatability | NOT STARTED as a complete gate | 3–5 focused workdays after dependencies |
| M7 — Release verified | Exact SHA on Linode, live workflow accepted, release receipt recorded | NOT STARTED for current slice | 0.5–1 focused day per accepted release |

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
