# CAOSCare PROJECT_STATE

**Current truth — reconciled 2026-10-16 01:00 CDT** (docs PR #170). The chronological story behind this state is `docs/CAOSCARE_ENGINEERING_HISTORY.md`. Entries older than 2026-10-12 were trimmed from this file on 2026-10-12 and remain in git history: `git show 4647c79^:docs/PROJECT_STATE.md`. Dated entries below are append-only history; read the newest first. This header is rewritten at each reconciliation and is the one place a new coordinator should start. Status words used here: IMPLEMENTED (code at an exact commit) · TESTED (gates passed) · SCRATCH ACCEPTED (worked on a scratch DB/stack) · BROWSER VERIFIED (real browser run) · PHYSICALLY VERIFIED (Michael observed it in Room 214) · LOADED (running on the named host/port) · OWNER ACCEPTED (Michael approved) · PRODUCTION DEPLOYED (caoscare.com).

| Question | Answer (with the source to read) |
|---|---|
| What is CAOSCare? | A governed, assistive, human-supervised, receipt-backed operating layer for a senior-living community; Aria is its voice. `docs/CAOSCARE_PRODUCT_BASELINE.md` §1. |
| Authoritative branch / runtime | Branch `integration/2026-09-27` (tip `e69cb69`, PR #171 merged). Dev backend `:8092` on the EliteDesk LOADED at code `1f60a58` with `OPENAI_REALTIME_MODEL=gpt-realtime-2.1-mini` from `.env` (pid 3391399, `scripts/restart_dev_backend.sh`, 2026-10-15 18:45 CDT); Room 214 page `:3002` build `main.b13c2b0d.js`. `main` = production caoscare.com (Linode) PRODUCTION DEPLOYED `06e7e2b` (2026-10-12 17:03 CDT; not re-verified today). `docs/CURRENT_NODE_STATUS.md` runtime table. |
| What is actually working today (Room 214, PHYSICALLY VERIFIED) | "Hey Aria" local wake on the eMeet (`room-node/aria_wake/`), OpenAI Realtime voice, lights with read-back, Sony TV by infrared (one-way, unverified by design), call-start TV mute/restore, concise goodbye, lifelong memory + re-wake continuity, live web lookup (paid, receipted), read-only self-code inspection (2026-10-15). Entries 2026-10-12 → 2026-10-15 below. |
| What is only simulated | Everything in the Living Community Simulator (80 apartments / 70 occupied / 75 synthetic residents, simulated staff, department runs) on scratch databases — never the shared `caoscare` dev DB. Running: **v11 Kitchen** run `simrun:living:ebe800685588c1283a63` at 1× (engineering live-accepted 2026-10-16T00:30Z, #168; owner acceptance pending) on `:8096` (`~/CAOSCARE-CO008-V11` @ `eaa1c23`, user unit `caoscare-dashboard-backend`) + `:3006`. v12 staffing (55 workers) is built and tested on `co008/workspace-staff-drilldown`, NOT loaded. Simulation metrics are not resident-care metrics. `docs/CAOSCARE_OPERATIONS_SIMULATOR.md` §11 (owner-approved assumptions). |
| What model does Aria use | Live voice: `gpt-realtime-2.1-mini` (owner cost decision 2026-10-15; full Realtime is not a fallback). Text/extraction: `gpt-4o-mini`. Live research: `gpt-4.1-mini` via the Responses API. Baseline §5a. |
| What can Room 214 Aria do / not do | Do: converse, remember, control the room's lights/TV/thermostat through CAOSCare → Home Assistant, file staff requests and report their true status, look things up, set reminders, read her own approved source (Room 214 only). Not: change code, run commands, deploy, send texts/emails, make outside calls, order anything, or claim an action a tool did not prove. `docs/ROOM214_SELF_CODE_INSPECTION.md`; tool catalog `backend/routes/realtime_tools*.py`. |
| How memory works | Every turn stored at once (`realtime_memory_ingest.py`); trusted user turn + reply → background fact/event extraction (`memory.py`, `aria_memory.py`); each finished conversation summarized once and folded into one bounded life story per resident (`aria_life_memory.py`); 72 h verbatim continuity (`aria_continuity.py`). Owner `/aria` memory is a separate store. |
| How tasks and receipts work | One canonical service layer (`resident_requests`, `task_lifecycle` + `task_actions`, `record_resident_activation`, transportation engine); every state change writes a receipt with actor/authority/before/after chained to the request's origin. `docs/ENGINEERING_CONTRACT.md` (ratified decisions), `AGENTS.md` receipt law. |
| What the simulator does | Exercises the same canonical workflows with explicitly simulated residents/staff on scratch data, with receipts and real-person takeover. `docs/CAOSCARE_OPERATIONS_SIMULATOR.md`. |
| Current staffing assumptions | Owner-approved **simulation** assumptions (not facility measurements): `docs/CAOSCARE_OPERATIONS_SIMULATOR.md` §11. |
| Current queue / what comes next | Owner master queue **issue #166** (one ACTIVE change order; CO-008 — Kitchen v11 reached its engineering acceptance boundary 2026-10-16T00:30Z; #153 slice 2 (`careops-153-drilldown-truth-002`) DONE 2026-10-16 (PR #177 merged `5e63f70`); **active: `public-162-site-redesign-001`** (public site as one system, branch `ui/public-site-162`, stops at owner visual review, no deploy); then #163 unified Aria, #164 simulation clock, #165 Home One hardware; #168 staff work queue follow-up). Operating philosophy (owner, 2026-10-15): the major structure is built; work is department-by-department trim, realism and commissioning in the order Kitchen → Nursing/Care → Housekeeping → Maintenance → Activities → Transportation → Front Office/Administration. Issue #129 is the historical Care-Operations dispatch thread, not the active queue. |
| Room architecture (current) | Central EliteDesk runs CAOSCare + Home Assistant. Room 214 (Michael's home test room) uses the eMeet speakerphone + local "Hey Aria" listener; **Voice PE was rejected by the owner on 2026-10-14** and is no longer the room endpoint. Future room hardware direction is CAOSCare Home One (#165, feasibility only). `docs/CAOSCARE_PRODUCT_BASELINE.md` §2 correction 2026-10-15. |
| What must never be done | No clinical/medical authority; no fabricated facility facts; no action without a receipt, no receipt without provenance; no simulator writes into real data; no production deploy, paid provider, Linode or Room 214 setting change without an explicit owner decision; no self-report as proof. `AGENTS.md`. |

Layer rule: `AGENTS.md` = operating rules · `START_HERE.md` / `CAOSCARE_START_HERE.md` = navigation · this file = current truth/status · `docs/CAOSCARE_PRODUCT_BASELINE.md` (and the still-placeholder `docs/CAOSCARE_BLUEPRINT.md`) = architecture/product · `docs/REPO_MAP.md` = where implementation lives · `docs/reports/` = historical evidence.



## 2026-10-12 05:02 CDT — Therapy permission boundaries ACKED / WORKING

Canonical ACK/WORKING receipt for `careops-therapy-permission-boundaries-001`: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6121965718. Transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6121993580. Living-checklist reconciliation: `1d71b4b9dd88cdc4dee4cf12f528a308a37b0363`.

The ONE current bounded task remains `careops-therapy-permission-boundaries-001`, existing coordinator `caoscare-1-ee`, existing worker `da-e7703038b0`, stage WORKING. ACK arrived before the 300-second deadline. The worker will read the resident-safe projection and every Therapy-touching route, build an isolated HTTP role × action matrix for owner/admin, front desk, Therapy, another department, and resident/public, inspect exactly what reaches residents/Aria, repair only the first proven gap, and browser-check where accounts exist. No clinical record or parallel truth store is authorized.

No new current-task product commit, automated gate, or browser result exists at ACK. Development backend is reported loaded at `468cbc8`; the prior accepted Therapy recurrence gates remain backend 600 passed / 0 failed / 31 skipped, frontend 90 suites / 641 tests, and compiled build; production remains `ff87c22` unchanged.

Latest timestamped host observation Monday, October 12, 2026 — 5:01:04 AM America/Chicago: coordinator `caoscare-1-ee` busy; control-plane service `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. This is host/process evidence; GitHub activity alone is not host-liveness proof.

ETA approximately Monday, October 12, 2026 — 6:29 AM America/Chicago. Existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 5:59:15 AM America/Chicago. Expected completion evidence: exact commits; explicit role/field/action matrix; focused/full gates; labeled desktop and 390 px browser evidence where accounts exist; direct API refusals for unavailable roles; resident/Aria safe truth; linked receipts/history; exact tested/loaded revisions; newest host observation; known cost or UNKNOWN. Blocker NONE. Michael action NOTHING.

## 2026-10-12 — Therapy permission boundaries (careops-therapy-permission-boundaries-001)
`565cfa1`: escalate/review reasons kept out of `notes` (the resident screen's latest update); dialogs say staff only. `7b737ea`: role × action matrix test, report `docs/reports/2026-10-12-therapy-permission-boundaries.md`, screenshots. Backend 601/0/31 + new tests 2/2; frontend 90/641; build compiled. Dev backend `565cfa1` (pid 1470556, log /tmp/room214_backend_565cfa1.log; previous /tmp/room214_backend_468cbc8.log). Open: completion/cancel/reopen dialogs don't yet say their text is resident-visible; no therapy login on dev.


## 2026-10-12 05:30 CDT — Therapy permission boundaries DEV_ACCEPTED; staff conflict detection delivered

Canonical source DONE for `careops-therapy-permission-boundaries-001`: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6122399284. Transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6122412245.

The task is IMPLEMENTED / TESTED / DEV_ACCEPTED, not OWNER_ACCEPTED / DONE. Product `565cfa1` removes staff-only unable-to-complete and supervisor-review reasons from resident-visible notes; the explicit Therapy role × action matrix rejects clinical fields with 422 and proves the operational permission boundary. Backend 601 passed / 0 failed / 31 skipped plus focused 2/2; frontend 90 suites / 641; build compiled. Development browser evidence covered nurse 390 px, resident 390 px, and owner 1280; resident/Aria outputs omitted the staff-only reason. Report `docs/reports/2026-10-12-therapy-permission-boundaries.md` at `7b737ea`. Development backend tested/loaded `565cfa1` (PID 1470556); production remains `ff87c22` unchanged.

Latest timestamped host observation Monday, October 12, 2026 — 5:27:55 AM America/Chicago: existing coordinator idle; control-plane service `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. GitHub activity alone is not host-liveness proof.

The ONE current bounded task is now `careops-therapy-staff-conflict-001`, delivered to existing coordinator `caoscare-1-ee`, stage DELIVERED / awaiting ACK or WORKING within 300 seconds. It will detect same Therapy staff/provider overlap across different residents using canonical planned StaffTask data, expose conflicts in existing Plan/detail/Upcoming surfaces, require an explicit receipted save-anyway override, and preserve recurrence, single-occurrence edits, linked transportation, role boundaries, and resident-safe truth. Expected evidence: overlap/non-overlap, role refusal, desktop/390 px browser, receipt chain, full gates, exact tested/loaded revisions, fresh host observation, and cost or UNKNOWN. Final Therapy staff/resident browser acceptance follows this gap.

ETA UNKNOWN pending ACK. Existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 5:35 AM America/Chicago. Blocker NONE. Michael action NOTHING.


## 2026-10-12 05:34 CDT — Therapy staff conflict detection ACKED / WORKING

Canonical ACK/WORKING receipt for `careops-therapy-staff-conflict-001`: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6122483873. Transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6122520853.

The ONE current bounded task remains `careops-therapy-staff-conflict-001`, existing coordinator `caoscare-1-ee`, worker `da-ed20c907a6`, stage WORKING. ACK arrived before the 300-second deadline. The worker reviewed the existing same-resident overlap logic in `routes/schedule_conflict.py`, its 60-minute slot, 409 + receipted save-anyway flow, the Upcoming conflict line, and canonical `provider_name` / `assigned_to`. It will extend that same path to other residents' open Therapy tasks with the same normalized provider name or assignee and then prove isolated HTTP, full gates, desktop and 390 px.

No new current-task product commit, automated gate, or browser result exists at ACK. Development product remains loaded at `565cfa1` from the accepted permission-boundary task; production remains `ff87c22` unchanged. Latest timestamped host observation Monday, October 12, 2026 — 5:34:18 AM America/Chicago: coordinator `caoscare-1-ee` busy; control-plane service `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. GitHub activity alone is not host-liveness proof.

Expected completion evidence: exact implementation commits; cross-resident provider/assignee overlap and non-overlap; explicit receipted override; recurrence/single-occurrence/linked-ride preservation; authorization/refusal; resident/Aria safe truth; desktop/390 px browser; full backend/frontend/build gates; exact tested/loaded revisions; newest host observation; cost or UNKNOWN. ETA approximately Monday, October 12, 2026 — 6:47 AM America/Chicago. Existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 6:47:20 AM America/Chicago. Blocker NONE. Michael action NOTHING.

## 2026-10-12 — Therapy staff double-booking (careops-therapy-staff-conflict-001)
`b7f6048`: planned-window check also covers the same provider/assignee across residents in the department; PATCH checks before writing; override receipted on schedule or details receipt. Backend 603/0/31, frontend 90/642, build compiled. Dev backend `b7f6048` (pid 1478496, log /tmp/room214_backend_b7f6048.log; previous /tmp/room214_backend_565cfa1.log). Report `docs/reports/2026-10-12-therapy-staff-conflict.md`.


## 2026-10-12 05:43 CDT — Therapy staff conflict DEV_ACCEPTED; final browser acceptance delivered

Canonical source DONE for `careops-therapy-staff-conflict-001`: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6122651596. Transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6122660781.

The task is IMPLEMENTED / TESTED / DEV_ACCEPTED, not OWNER_ACCEPTED / DONE. Product `b7f6048` extends the existing canonical 60-minute conflict check across residents for the same normalized provider name or assignee, refuses overlap with 409 before any write, and reuses the explicit receipted save-anyway path. Resident views carry no conflicts. Tests cover overlap/non-overlap, provider-only changes, assignee, refusal, receipts, Upcoming, resident views, recurrence occurrence, and linked ride. Backend 603 passed / 0 failed / 31 skipped; frontend 90 suites / 642; build compiled. Development browser evidence covered owner 1280 and 390 px with no failed API calls; nurse refusal returned 403; synthetic tasks were cancelled. Development backend tested/loaded `b7f6048`, PID 1478496; production `ff87c22` unchanged. No GitHub workflow runs were attached to `b7f6048`; recorded local gates/browser evidence apply.

Latest timestamped host observation Monday, October 12, 2026 — 5:42:36 AM America/Chicago: existing coordinator idle; control-plane service `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. GitHub activity alone is not host-liveness proof.

The ONE current bounded task is now `careops-therapy-browser-acceptance-001`, delivered to existing coordinator `caoscare-1-ee`, stage DELIVERED / awaiting ACK or WORKING within 300 seconds. Using the development runtime and labeled synthetic data, it must prove owner/admin, front desk, an actual signed-in Therapy role via existing or temporary dev-only auth if safe, resident Home, and Aria across create, plan, claim/start, operational note, completion, cancellation/reopen, recurrence/Upcoming, conflict override, linked ride, receipts/history, role refusal, clinical-field rejection, resident-safe truth, desktop, and 390 px. The completion/cancel/reopen dialogs must explicitly label resident-visible text. Synthetic data/accounts must be cleaned up. If all criteria pass, the full Therapy section becomes READY_FOR_OWNER_REVIEW, not OWNER_ACCEPTED / DONE.

ETA UNKNOWN pending ACK. Existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 5:48 AM America/Chicago. Blocker NONE. Michael action NOTHING.


## 2026-10-12 05:47 CDT — Final Therapy browser acceptance ACKED / WORKING

Canonical ACK/WORKING receipt for `careops-therapy-browser-acceptance-001`: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6122696055. Transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6122727208.

The ONE current bounded task remains `careops-therapy-browser-acceptance-001`, existing coordinator `caoscare-1-ee`, worker `da-13af1cbe1d`, stage WORKING. ACK arrived before the 300-second deadline. Inspection confirmed the first likely gap: complete/cancel/reopen notes reach the resident screen and Aria, but those dialogs do not disclose that fact. The development stack has no Therapy login. The worker will prove and label the wording, create a temporary labeled Therapy account only through the existing owner staff API and delete it after use, then exercise all 12 final criteria across owner/front desk/Therapy/resident in headless browser at 1280 and 390 px, verify Aria via real status/schedule endpoints, run full gates, and clean up synthetic state.

No new current-task product commit, automated gate, or browser result exists at ACK. Development backend remains loaded at `b7f6048`; production remains `ff87c22` unchanged. Latest timestamped host observation Monday, October 12, 2026 — 5:46:58 AM America/Chicago: coordinator `caoscare-1-ee` busy; control-plane service `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. GitHub activity alone is not host-liveness proof.

Expected completion evidence: exact commits; all 12 final criteria across owner/front desk/Therapy/resident/Aria; explicit resident-visible wording; desktop/390 px; clinical-field rejection and role refusal; one canonical receipt/history chain; recurrence/Upcoming/conflict/linked-ride truth; full backend/frontend/build gates; exact tested/loaded revisions; cleanup proof; newest host observation; cost or UNKNOWN; full Therapy section READY_FOR_OWNER_REVIEW only if every criterion passes. ETA approximately Monday, October 12, 2026 — 7:15 AM America/Chicago. Existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 7:15:02 AM America/Chicago. Blocker NONE. Michael action NOTHING.
## 2026-10-12 — Therapy end-to-end acceptance (careops-therapy-browser-acceptance-001)
`db4317f`: complete/cancel/reopen dialogs label resident visibility. 32/32 acceptance checks on dev (temp Therapy login created via staff API and removed). Backend 603/0/31 at `b7f6048`; frontend 90/642; build compiled. Therapy section READY_FOR_OWNER_REVIEW. Report `docs/reports/2026-10-12-therapy-acceptance.md`.


## 2026-10-12 05:51 CDT — Therapy READY_FOR_OWNER_REVIEW; canonical alert state delivered

Canonical DONE for `careops-therapy-browser-acceptance-001`: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6122762572. Correction naming the pushed records commit: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6122766978. Transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6122791597. Living-checklist reconciliation: `df4fe6fa1049cdc05eeab9c6869c85c83416a218`.

The Therapy section is READY_FOR_OWNER_REVIEW, not OWNER_ACCEPTED / DONE. All 12 written criteria passed as 32/32 development checks with zero failed API calls. Product/backend `b7f6048398f3e20c6da74bd59b1d27fde61060ea` remained the tested/loaded backend; frontend `db4317fd1fc5d03dbda57ee4b60d26cd6774466f` labels complete/cancel/reopen text as resident-visible and potentially read by Aria. Backend 603 passed / 0 failed / 31 skipped; frontend 90 suites / 642; build compiled.

Browser acceptance used owner, demo front desk, demo nurse for refusal, a temporary labeled Therapy login created through the existing staff API and deleted afterward, synthetic residents/tasks, resident Home at 1280/390, and Aria's real status/upcoming endpoints. It covered create, plan/reschedule, provider/discipline/location, claim/start, note, complete, reopen/cancel, recurrence/Upcoming, cross-resident conflict refusal plus receipted override, linked ride, one workflow receipt chain, unauthorized refusal, clinical-field rejection, and resident-safe truth. All synthetic requests, ride, recurrence occurrence/series, and the temporary account were deleted. Report/screenshots/script/checklist/project-state records are in corrected commit `8533b2aa9cb0ac5f49496df4fafa475f322e19c4`. Production remains `ff87c22`. Cost UNKNOWN.

Latest timestamped host observation Monday, October 12, 2026 — 5:51:06 AM America/Chicago: existing coordinator `caoscare-1-ee` idle; control-plane service PID 1370098 running `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. This is control-plane host evidence only; GitHub activity is not host-liveness proof.

The ONE current bounded task is `careops-alerts-canonical-state-001`, existing coordinator `caoscare-1-ee`, stage DELIVERED / awaiting ACK or WORKING by Monday, October 12, 2026 — 5:56 AM America/Chicago. Inventory the documented competing alert/task/notification state implementations; select and enforce one canonical receipt-backed contract using existing records; preserve accepted Nursing unclaimed escalation; prove creation, acknowledgement, timer/fallback transition, idempotency, terminal stop conditions, supervisor visibility, role refusal, resident/Aria-safe truth, desktop/390 px, and explicit compatibility/migration handling. Repair only the first proven gap. No new queue, timer service, truth store, coordinator, worker, watchdog, monitor, external delivery, production mutation/deployment, paid service, audio/Hey Aria work, real data, or PR merge.

Ordered remaining current-milestone steps: 1. inventory every current alert, notification, task-escalation state and receipt; 2. publish an explicit canonical state/transition and compatibility matrix; 3. prove accepted Nursing escalation maps cleanly; 4. repair only the first proven conflicting path; 5. prove acknowledgement, timer/fallback, idempotency, stop conditions, supervisor view, refusal, and resident/Aria-safe truth; 6. run focused/full gates plus desktop/390 px browser acceptance; 7. clean synthetic state and record exact tested/loaded revisions, newest host evidence and cost; 8. reconcile checklist, Issue #129, PROJECT_STATE, and receipt.

Ordered upcoming milestones: 1. complete alerts/escalation policy editor, acknowledgements, timers, fallback and section acceptance; 2. remaining Phase 3 department-workspace gaps; 3. Phase 4 scheduling/records/resources; 4. Phase 5 communications; 5. Phase 6 pilot reliability/accessibility; 6. Phase 7 release/deployment/live acceptance.

ETA UNKNOWN pending ACK. Existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 5:56:15 AM America/Chicago. Expected evidence: exact implementation/records commits; state-transition matrix; focused/full gates; labeled API/browser results; receipts/history; tested versus loaded revisions; newest host observation; cleanup; cost or UNKNOWN. Blocker NONE. Michael action NOTHING.


## 2026-10-12 05:57 CDT — Canonical alert state ACKED / WORKING

Canonical ACK/WORKING receipt: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6122858667. Transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6122887366. Living-checklist reconciliation: `fd180cead389d69a8900d8cb194555fed2cd335e`.

The ONE current bounded task remains `careops-alerts-canonical-state-001`, existing coordinator `caoscare-1-ee`, worker `da-2be29b619e`, stage ACKED / WORKING. ACK arrived before the 300-second deadline.

Evidence under review: every writer of Alert `status`, `escalation_level`, `aria_state`, and `live_line_state`; `escalation_tick` as RQ-018's sole escalation authority; notification statuses; StaffTask `needs_review` and accepted unclaimed escalation; canonical receipts. The worker will enumerate all writers, publish the state/transition plus compatibility matrix, prove the accepted Nursing unclaimed escalation maps cleanly, add a failing test for the first conflicting writer before repairing it, run focused/full gates and headless desktop/390 px acceptance, and clean synthetic state.

No new current-task product revision, automated gate, or browser result exists at ACK. Prior accepted development remains backend `b7f6048`, frontend `db4317f`; production remains `ff87c22`.

Latest timestamped host observation Monday, October 12, 2026 — 5:57:31 AM America/Chicago: coordinator `caoscare-1-ee` busy; control-plane service PID 1370098 on `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. This is control-plane host evidence only; GitHub activity is not host-liveness proof.

Ordered remaining current-milestone steps: 1. inventory all alert/notification/escalation state writers and receipts; 2. publish the canonical transition and compatibility matrix; 3. prove Nursing unclaimed escalation maps cleanly; 4. add a failing test and repair only the first conflicting writer; 5. prove acknowledgement, timer/fallback, idempotency, stop conditions, supervisor visibility, refusal, and resident/Aria-safe truth; 6. run focused/full backend/frontend/build gates and desktop/390 px browser acceptance; 7. clean synthetic state and record exact tested/loaded revisions, newest host evidence, and cost; 8. reconcile checklist, Issue #129, PROJECT_STATE, and receipt.

Ordered upcoming milestones: 1. complete alerts/escalation policy editor, acknowledgements, timers, fallback, and section acceptance; 2. remaining Phase 3 department-workspace gaps; 3. Phase 4 scheduling/records/resources; 4. Phase 5 communications; 5. Phase 6 pilot reliability/accessibility; 6. Phase 7 release/deployment/live acceptance.

ETA approximately Monday, October 12, 2026 — 7:35 AM America/Chicago. Existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 7:35:34 AM America/Chicago. Expected completion evidence: exact implementation/records commits; complete state/transition and compatibility matrix; failing-before/fixed-after test for the first conflict; focused/full gates; labeled API/browser results; receipts/history; exact tested/loaded revisions; cleanup; newest timestamped host observation; cost or UNKNOWN. Blocker NONE. Michael action NOTHING.

## 2026-10-12 — Alerts canonical state (careops-alerts-canonical-state-001)
`45bd442`: receipted, history-linked, atomic alert acknowledgement. Contract + inventory in `docs/reports/2026-10-12-alerts-canonical-state.md`. Backend 604/0/31. Dev backend `45bd442` (pid 1489371, log /tmp/room214_backend_45bd442.log; previous /tmp/room214_backend_b7f6048.log). Owner decision needed: which roles may acknowledge a help alert.


## 2026-10-12 06:06 CDT — Canonical alert state DEV_ACCEPTED; close-out receipts delivered

Canonical DONE: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6122992084. Transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6123012360. Living-checklist reconciliation: `c3b3d27708c038c6c4b0728167e18130510f0acc`.

`careops-alerts-canonical-state-001` is IMPLEMENTED / TESTED / DEV_ACCEPTED, not OWNER_ACCEPTED / DONE; the broader Alerts / escalation section remains incomplete. The selected contract is: Alert staff status active → acknowledged → resolved; legacy `escalated` is treated as open but never newly written; RQ-018 `escalation_tick` alone changes escalation level and stops after acknowledgement/resolution; every staff transition must be one guarded atomic write with one actor/authority/before/after receipt and a linked history entry; StaffTask lifecycle and accepted Nursing unclaimed escalation stay separate; Aria/live-line state stays separate.

Product `45bd4427125d07aefa2da3817bbeb903126d02a9` repaired the first proven gap: acknowledgement now performs one guarded atomic write, one `alert_acknowledged` receipt, and one receipt-linked history entry. Repeat acknowledgement returns 404; six concurrent attempts yield one winner, one receipt and one history entry; legacy `escalated` rows are accepted. Backend 604 passed / 0 failed / 31 skipped; focused alert/escalation/dispatch 15/15; frontend unchanged at 90 suites / 642. Headless development browser used a synthetic DEMO alert: nurse 390 px acknowledgement with no overflow or failed API calls; owner 1280 confirmation; receipt `rcpt_43a2883ae8cb` matched history; minimal public status; synthetic alert closed. Records/report/screenshots commit `eef8e8de410b29cbae938130a7f1eac1876c8468`. No PR-triggered GitHub workflow runs attached.

Tested/loaded: development backend `45bd442`, PID 1489371; development frontend unchanged from `db4317f`; production `ff87c22` unchanged. Latest timestamped host observation Monday, October 12, 2026 — 6:05:47 AM America/Chicago: existing coordinator `caoscare-1-ee` idle; control-plane PID 1370098 on `f1db2d358ca1`; repository `cd076d251ab9` newer/not loaded. GitHub activity alone is not host-liveness proof. Cost UNKNOWN.

Open gaps remain: 1. allowed acknowledgement roles require an owner policy decision; 2. close-out receipts omit actor/before-after and close can repeat; 3. wander/wearable/pendant scaffolds insert alerts without coalescing or creation receipts; 4. resolve ignores legacy `escalated` rows. Gap 1 is deferred while compatible work continues; no Michael action is requested in this transition.

The ONE current bounded task is `careops-alerts-close-receipts-001`, existing coordinator `caoscare-1-ee`, stage DELIVERED / awaiting ACK or WORKING by Monday, October 12, 2026 — 6:11 AM America/Chicago. Repair gap 2: make alert resolve/close one status-guarded terminal transition with exactly one receipt and linked history entry containing actor, authority and before/after; refuse or idempotently reject repeat and concurrent close; cover active, acknowledged and legacy `escalated` rows. Preserve canonical acknowledgement, RQ-018 escalation, dispatch, public status, resident/Aria safety and Nursing mapping. Do not decide the deferred role-policy question.

Ordered remaining current-milestone steps: 1. add failing tests for actor-less close-out receipts and repeated/concurrent close; 2. unify resolve/close on one guarded transition; 3. prove active/acknowledged/legacy-escalated compatibility and linked receipt/history; 4. prove refusal and public/resident/Aria safety without widening policy; 5. run focused/full gates plus desktop/390 px browser acceptance; 6. clean synthetic state and record exact tested/loaded revisions, newest host evidence and cost; 7. reconcile checklist, Issue #129, PROJECT_STATE and receipt; 8. continue to direct-insert/coalescing and policy-editor gaps.

Ordered upcoming milestones: 1. finish alert creation/coalescing, policy editor, role policy, timers/fallback and full Alerts section acceptance; 2. remaining Phase 3 department-workspace gaps; 3. Phase 4 scheduling/records/resources; 4. Phase 5 communications; 5. Phase 6 pilot reliability/accessibility; 6. Phase 7 release/deployment/live acceptance.

ETA UNKNOWN pending ACK. Existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 6:11:15 AM America/Chicago. Expected evidence: exact commit; failing-before/fixed-after tests; state compatibility matrix; focused/full gates; labeled API/browser results; linked receipt/history; exact tested/loaded revisions; cleanup; newest host observation; cost or UNKNOWN. Blocker NONE. Michael action NOTHING.


## 2026-10-12 06:10 CDT — Alert close-out receipts ACKED / WORKING

Canonical ACK/WORKING receipt: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6123049176. Transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6123077551. Living-checklist reconciliation: `2d47e6ed75507b783a70dc86d60f79334352dd89`.

The ONE current bounded task remains `careops-alerts-close-receipts-001`, existing coordinator `caoscare-1-ee`, worker `da-6b6a0ace12`, stage ACKED / WORKING. ACK arrived before the 300-second deadline.

Evidence reviewed: `alerts.resolve` filters active/acknowledged and ignores legacy `escalated`; `alerts.close_alert` includes resolved and can re-close while overwriting `resolved_at` / `resolved_by`; `_close_out` calls `update_receipt_status` without actor, before/after, or a history link. The worker will add failing tests first, then use one shared guarded active/acknowledged/escalated → resolved transition for both endpoints, producing exactly one `alert_completed` receipt with actor/authority/before/after and one linked history entry. One concurrent attempt wins; repeats and remaining contenders return 409 without writes. Pattern statistics and dispatch remain untouched, and the deferred acknowledgement-role policy is not decided in this slice.

No new current-task product revision, automated gate, or browser result exists at ACK. Prior accepted development remains backend `45bd442`, frontend `db4317f`; production `ff87c22` unchanged.

Latest timestamped host observation Monday, October 12, 2026 — 6:10:08 AM America/Chicago: coordinator `caoscare-1-ee` busy; control-plane service PID 1370098 on `f1db2d358ca1`; repository `cd076d251ab9` newer and not loaded. This is control-plane host evidence only; GitHub activity is not host-liveness proof.

Ordered remaining current-milestone steps: 1. add failing tests for actor-less and repeated/concurrent close; 2. implement the one shared guarded terminal transition; 3. prove active/acknowledged/legacy-escalated inputs and one linked receipt/history record; 4. prove repeat/concurrent 409 behavior without extra writes; 5. verify pattern stats, dispatch, authorization/refusal, public status and resident/Aria safety remain unchanged; 6. run focused/full backend/frontend/build gates and desktop/390 px browser acceptance; 7. clean synthetic state and record exact tested/loaded revisions, newest host evidence and cost; 8. reconcile checklist, Issue #129, PROJECT_STATE and receipt.

Ordered upcoming milestones: 1. repair direct alert creation/coalescing and receipts; 2. complete Alerts policy editor, role policy, timers/fallback and section acceptance; 3. remaining Phase 3 department-workspace gaps; 4. Phase 4 scheduling/records/resources; 5. Phase 5 communications; 6. Phase 6 pilot reliability/accessibility; 7. Phase 7 release/deployment/live acceptance.

ETA approximately Monday, October 12, 2026 — 7:23 AM America/Chicago. Existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 7:23:11 AM America/Chicago. Expected completion evidence: exact commit; failing-before/fixed-after tests; both endpoints and state compatibility; repeat/concurrent behavior; linked receipt/history; focused/full gates; desktop/390 px browser; exact tested/loaded revisions; cleanup; newest host observation; cost or UNKNOWN. Blocker NONE. Michael action NOTHING.

## 2026-10-12 — Alert close receipts (careops-alerts-close-receipts-001)
`fc9e95b`: `_finish()` shared by resolve/close; receipted, guarded, idempotent. Backend 605/0/31. Dev backend `fc9e95b` (pid 1495849, log /tmp/room214_backend_fc9e95b.log; previous /tmp/room214_backend_45bd442.log).


## 2026-10-12 06:17 CDT — Alert close-out receipts DEV_ACCEPTED; direct ingress receipts DELIVERED

Canonical source DONE for `careops-alerts-close-receipts-001`: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6123167417. Transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6123169312. Living-checklist reconciliation: `067269dc3c1e562c33d948cd87916ab26df46a2b`.

The completed task is IMPLEMENTED / TESTED / DEV_ACCEPTED, not OWNER_ACCEPTED / DONE. Product `fc9e95b638a0e518542ab9a9695c8a82239bdedd` unifies resolve and close as one guarded active/acknowledged/legacy-escalated → resolved transition. It emits exactly one provenance-complete `alert_completed` receipt and linked history entry; repeat and concurrent terminal attempts return 409 with no rewrite. Backend gates passed 605 / 0 / 31. Frontend was unchanged at 90 suites / 642 tests. Development browser acceptance covered nurse 390 px and owner 1280 px, verified the outcome, actor and linked history, proved 409 idempotency, kept public room status minimal, and cleaned synthetic data. Records/report/screenshots are at `1a944bef29f398739ac875d54da215110f5237a1`. No PR-triggered GitHub workflow run is attached; recorded local gates/browser evidence apply.

Tested and loaded development backend is `fc9e95b`, PID 1495849; frontend `db4317f`; production `ff87c22` unchanged. Cost UNKNOWN. Latest timestamped host observation Monday, October 12, 2026 — 6:16:21 AM America/Chicago: existing coordinator `caoscare-1-ee` busy; control-plane PID 1370098 on `f1db2d358ca1`; repository `cd076d251ab9` newer/not loaded. GitHub activity alone is not host-liveness proof.

The ONE current bounded task is now `careops-alerts-ingress-receipts-001`, delivered to the existing coordinator `caoscare-1-ee`, stage DELIVERED / awaiting ACK or WORKING within 300 seconds. It will repair direct wander, wearable and pendant scaffold inserts by routing them through the canonical alert creation/coalescing and receipt path without creating a parallel store, queue, coordinator or worker. Acceptance requires exact commits; failing-before/fixed-after tests; repeated and concurrent source signals coalescing to one alert and one provenance-complete creation receipt; preserved source and parent provenance; unchanged escalation, public status, dispatch, acknowledgement and close flows; authorization/resident/Aria safety; desktop and 390 px browser evidence; cleanup; full gates; exact tested/loaded revisions; newest host observation; and cost or UNKNOWN.

Ordered remaining Alerts-milestone steps: 1. ACK and inspect the three direct-ingress paths; 2. add failing ingress/coalescing/receipt tests; 3. route each path through the canonical helper and prove concurrency/idempotency; 4. verify downstream escalation/dispatch/public/acknowledge/close behavior and safety; 5. run full gates and desktop/390 px browser acceptance; 6. clean synthetic state and reconcile records; 7. finish policy editor, owner role-policy decision, timers/fallback and full Alerts section acceptance.

Ordered upcoming milestones: 1. finish Alerts section acceptance; 2. remaining Phase 3 department-workspace gaps; 3. Phase 4 scheduling/records/resources; 4. Phase 5 communications; 5. Phase 6 pilot reliability/accessibility; 6. Phase 7 release/deployment/live acceptance.

ETA UNKNOWN pending ACK. Existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 6:22:49 AM America/Chicago. Blocker NONE. The acknowledgement/close role policy remains deferred but does not block compatible work. Michael action NOTHING.


## 2026-10-12 06:23 CDT — Direct alert ingress receipts ACKED / WORKING

Canonical ACK/WORKING receipt: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6123235463. Transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6123265495. Living-checklist reconciliation: `c4dac61ea6227c7cac9cd8254a56a8ecb65495b3`.

The ONE current bounded task remains `careops-alerts-ingress-receipts-001`, existing coordinator `caoscare-1-ee`, worker `da-2df56d6a1e`, stage ACKED / WORKING. Automatic intake delivered at Monday, October 12, 2026 — 6:20:40 AM America/Chicago; ACK/WORKING followed at Monday, October 12, 2026 — 6:20:46 AM America/Chicago, six seconds later and before the 300-second deadline.

Evidence reviewed: direct `db.alerts.insert_one` paths exist in `location.py` for wander alerts, `wearables.py`, and `pendants.py`; the canonical `resident_activation.record_resident_activation` path already supplies coalescing and a creation receipt. The worker will first add failing tests for each used source, confirm whether `pendants.py` is mounted/used, then route the applicable paths through the canonical helper while preserving `triggered_by`, device identifiers, source identity and severity rules.

Expected completion evidence remains: exact commits; failing-before/fixed-after source tests; repeated/concurrent signals producing one canonical alert and one provenance-complete creation receipt; preserved source and parent provenance; unchanged escalation, public status, dispatch, acknowledgement and close behavior; authorization/resident/Aria safety; full gates; headless desktop and 390 px browser acceptance; cleanup; exact tested/loaded revisions; newest host observation; and cost or UNKNOWN.

No new current-task product commit, test result or browser result exists at ACK. Prior accepted development remains backend `fc9e95b`, PID 1495849, and frontend `db4317f`; production `ff87c22` unchanged.

Latest timestamped host observation Monday, October 12, 2026 — 6:22:44 AM America/Chicago: existing coordinator `caoscare-1-ee` busy; control-plane service PID 1370098 on `f1db2d358ca1`; repository `cd076d251ab9` newer/not loaded. This is control-plane host evidence; GitHub activity alone is not host-liveness proof.

Ordered remaining Alerts-milestone steps: 1. add failing tests for each mounted/used direct ingress source; 2. prove whether `pendants.py` is mounted; 3. route applicable sources through the canonical helper with source/severity preservation; 4. prove repeated/concurrent coalescing and exactly one creation receipt; 5. verify downstream escalation/dispatch/public/acknowledge/close and safety; 6. run full gates and desktop/390 px browser acceptance; 7. clean synthetic state and reconcile authoritative records; 8. complete policy editor, owner role-policy decision, timers/fallback and full Alerts section acceptance.

Ordered upcoming milestones: 1. finish Alerts section acceptance; 2. remaining Phase 3 department-workspace gaps; 3. Phase 4 scheduling/records/resources; 4. Phase 5 communications; 5. Phase 6 pilot reliability/accessibility; 6. Phase 7 release/deployment/live acceptance.

ETA approximately Monday, October 12, 2026 — 8:00:46 AM America/Chicago. Existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 8:00:46 AM America/Chicago. Blocker NONE. Michael action NOTHING.

## 2026-10-12 — Alert device ingress (careops-alerts-ingress-receipts-001)
`004c158`: wander/wearable/pendant-scaffold through `record_resident_activation` (device signals in `signals[]`), creation-receipt provenance. Backend 606/0/31. Dev backend `004c158` (pid 1506940, log /tmp/room214_backend_004c158.log; previous /tmp/room214_backend_fc9e95b.log).


## 2026-10-12 07:38 CDT — Alert ingress DEV_ACCEPTED; policy editor DELIVERED

Canonical completion source: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6123477972. Product `004c158`; acceptance records `081b12953dbb457f3c5b5f3df7e5899b83365d60`; living-checklist boundary reconciliation `1d622640c822c36c573d265d6021e83110989f75`.

`careops-alerts-ingress-receipts-001` is IMPLEMENTED / TESTED / DEV_ACCEPTED, not OWNER_ACCEPTED / DONE. Geofence, wearable, and pendant-scaffold sources now reuse the canonical one-open-event path. Device signals are distinct from presses and can only raise severity; one creation receipt preserves source/device/authority provenance. Backend 606 passed / 0 failed / 31 skipped. Development browser acceptance covered nurse 390 px and owner 1280 px, kept public status minimal, preserved acknowledge/close, and cleaned synthetic state. Tested and loaded development backend `004c158`, PID 1506940; frontend `db4317f`; production `ff87c22` unchanged. Cost UNKNOWN.

Latest timestamped host observation Monday, October 12, 2026 — 6:36 AM America/Chicago: the existing coordinator receipt reported backend `004c158` loaded as PID 1506940. GitHub activity is not host-liveness proof.

The ONE current bounded task is `careops-alerts-policy-editor-001`, delivered to existing coordinator `caoscare-1-ee`, awaiting ACK / WORKING within 300 seconds. It must inventory and reuse the canonical alert policy store, UI/API and `escalation_tick`; prove one owner/admin edit is provenance-receipted and changes the existing runtime; reject invalid edits and unauthorized roles; preserve defaults/fallback, resident/Aria/public safety, and the existing local timer/watchdog; run focused/full gates and desktop/390 px acceptance; clean synthetic state; and record exact tested/loaded revisions, newest host evidence and cost. It must repair only the first proven gap and must not decide the separate acknowledge/close role policy.

Ordered remaining Alerts steps: 1. ACK and inventory policy configuration/runtime readers; 2. failing tests for policy edit, receipt/history, runtime effect and refusals; 3. first-gap repair; 4. prove edited policy, defaults and fallback through `escalation_tick`; 5. full gates and desktop/390 px browser; 6. cleanup and exact evidence; 7. reconcile checklist/Issue #129/PROJECT_STATE; 8. timer/fallback residue; 9. owner role-policy decision; 10. owner review when the section is complete.

Upcoming milestones: 1. finish Alerts; 2. remaining Phase 3 workspaces; 3. Phase 4 schedules/resources; 4. Phase 5 communications; 5. Phase 6 pilot/reliability/accessibility; 6. Phase 7 release/live acceptance.

ETA UNKNOWN pending ACK. Existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 7:43:39 AM America/Chicago. Blocker NONE for compatible work. Michael action NOTHING now.


## 2026-10-12 07:43 CDT — Alert policy editor ACKED; compliant WORKING correction required

Automatic intake delivered worker `da-a0fcc8aef7` at Monday, October 12, 2026 — 7:43:27 AM America/Chicago: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6124495322. The existing coordinator ACKed `careops-alerts-policy-editor-001` at Monday, October 12, 2026 — 7:43 AM America/Chicago and began inventory: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6124496240. Living-checklist reconciliation: `0f6988134f80214b79b30fbff22001db9d1d0b39`.

Current stage is ACKED / inventory starting through the existing coordinator `caoscare-1-ee`, worker `da-a0fcc8aef7`. The ACK reports development backend `004c158`, PID 1506940; production `ff87c22` untouched; targets are the existing policy store, editor/API and `escalation_tick`. This is the latest coordinator-reported host observation. No new current-task revision, gate or browser result exists yet; frontend remains `db4317f`.

The ACK satisfied pickup timing but omitted the required evidence-based realistic ETA and expected acceptance evidence. Work continues with blocker NONE. The next WORKING receipt must correct those fields, name the evidence reviewed, preserve a precise next_check_at, and state expected acceptance. ETA remains UNKNOWN until that correction. Worker next_check_at is Monday, October 12, 2026 — 8:13 AM America/Chicago. Michael action NOTHING.


## 2026-10-12 07:48 CDT — Alert policy editor WORKING receipt corrected

Canonical WORKING: https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6124535896. Transport-only mirror: https://github.com/caosos/CAOSCARE.COM/pull/131#issuecomment-6124565444. Checklist reconciliation: `e40917673d6b159d825c95bf68d6b400d8330058`.

The ONE current bounded task is `careops-alerts-policy-editor-001`, existing coordinator `caoscare-1-ee`, worker `da-a0fcc8aef7`, stage WORKING. Intake item `da-64918ae4b4` carried the correction and is not a second implementation worker.

Evidence reviewed: the existing escalation GET/PUT/tick routes, sole `escalation_tick` level writer and lifespan loop, canonical facility-keyed `db.escalation_rules` store with 90/150/600 defaults, Admin Escalation editor, and RQ-018/RQ-027/Nursing-unclaimed tests. Inventory confirms one store, editor and runtime reader with owner/admin enforcement.

First failing-before test `tests/test_alert_policy_editor.py` proved an invalid level-3 ≤ level-2 policy returned 200 and policy changes emitted no receipt. The in-progress uncommitted repair adds bounds/ordering validation, optimistic `updated_at` guard, provenance-complete `escalation_rule_changed` receipt/history, and receipt linkage from the rule. Focused gate is 14 passed.

Tested state is an uncommitted worktree based on backend `004c158`; no new revision is loaded. Development remains backend `004c158`, PID 1506940, frontend `db4317f`; production `ff87c22` unchanged. Latest host observation Monday, October 12, 2026 — 7:47:46 AM America/Chicago: coordinator busy; control-plane PID 1370098 on `f1db2d358ca1`; repository `cd076d251ab9` newer/not loaded. Cost UNKNOWN.

Expected acceptance: failing-before/fixed-after proof; exact commit; linked receipt chain; 20-second edited policy reaches level 2 at 30 seconds while a no-rule facility stays level 0; invalid/unauthorized refusals; full gates; desktop/390 px screenshots; cleanup; exact tested/loaded revisions; newest host observation. ETA Monday, October 12, 2026 — 9:15 AM America/Chicago. Existing LOCAL watchdog next_check_at Monday, October 12, 2026 — 8:30 AM America/Chicago. Blocker NONE. Michael action NOTHING.
## 2026-10-12 — Alert policy editor (careops-alerts-policy-editor-001)
`a7c406d` (pre-rebase `7ade644`): escalation policy edits validated (bounds, level 3 after level 2) and receipted (`escalation_rule_changed`, parent chain, rule links receipt). Backend 607/0/31; frontend 91/644; dev backend `7ade644` (pid 1532821, log /tmp/room214_backend_7ade644.log). Report: docs/reports/2026-10-12-alerts-policy-editor.md. Residue: `escalate_unclaimed` reads the first stored rule regardless of facility.

## 2026-10-12 — Unclaimed escalation per-facility rule (careops-alerts-facility-policy-isolation-001)
Unclaimed step now selects each request's own facility rule via `escalation_tick.rule_for` (defaults when none); was first-stored-rule-for-all. Backend 608/0/31. Report: docs/reports/2026-10-12-alerts-facility-policy-isolation.md. Note: tasks/residents/alerts carry no facility_id yet.

## 2026-10-12 — Alerts fallback contract (careops-alerts-fallback-contract-001)
Contract + first gap: escalation tick failure/recovery now receipted (`escalation_tick.tick_once`). Backend 609/0/31. Report: docs/reports/2026-10-12-alerts-fallback-contract.md. Next gap: stopped/disabled loop undetected.

## 2026-10-12 — Escalation loop liveness (careops-alerts-loop-liveness-001)
`/api/health` reports `escalation.state`; disabled-at-startup receipted once (`escalation_tick.start_schedule`). Backend 610/0/31. Report: docs/reports/2026-10-12-alerts-loop-liveness.md.

## 2026-10-12 — Escalation loop death receipt (careops-alerts-loop-death-receipt-001)
`e2e2b1b`: unexpected loop end → one `escalation_schedule_stopped` receipt; shutdown none; schedule/health split into `routes/escalation_schedule.py`. Backend 611/0/31. Report: docs/reports/2026-10-12-alerts-loop-death-receipt.md.

## 2026-10-12 — Full Alerts acceptance (careops-alerts-full-acceptance-001)
No code change; 17/17 dev browser checks; gates 611/0/31, 91/644, build OK. Findings: nurse /staff feed shows 200 legacy alerts (no stale split); ack receipt lacks parent. Owner decision packet in docs/reports/2026-10-12-alerts-full-acceptance.md.

## 2026-10-12 — Nurse Live alerts current vs older (careops-alerts-staff-feed-current-001)
`/alerts/feed` scope=current default (72 h), scope=older on request, stats older_open; nurse banner + Show older. Backend 612/0/31, frontend 92/645. Report: docs/reports/2026-10-12-alerts-staff-feed-current.md.

## 2026-10-12 — Acknowledgement receipt parent link (careops-alerts-ack-parent-link-001)
`d0642ec`: alert_acknowledged.parent_receipt_id = origin receipt. Backend 613/0/31. Only owner role-policy decision remains before Alerts re-acceptance.

## 2026-10-12 — Front desk unified inbox first slice (careops-frontdesk-unified-inbox-inventory-001)
`2604c16`: /front-desk "Needs attention" tab = existing RoutingExceptionsBoard (backend-scoped). Matrix + gaps in docs/reports/2026-10-12-frontdesk-unified-inbox.md. Backend 614/0/31, frontend 93/646.

## 2026-10-12 — Front desk failed deliveries (careops-frontdesk-failed-deliveries-001)
`2278dcf`: /ops/delivery-exceptions (redacted alert-delivery failures, desk + admin) + Needs attention card. Backend 615/0/31, frontend 93/646. Finding: notify_family_for_alert writes no receipt.

## 2026-10-12 — Family alert update receipts (careops-alerts-family-update-receipt-001)
`2079206`: family_alert_update_attempt receipt per attempt, parent = alert origin. Backend 616/0/31. Finding: room-screen repeat presses re-notify family.

## 2026-10-12 — Front desk callback fields (careops-frontdesk-callback-contact-fields-001)
`400b5b3`: callback_phone/callback_window on StaffTask, staff-only, receipted. Backend 617/0/31, frontend 94/648. Report docs/reports/2026-10-12-frontdesk-callback-fields.md.

## 2026-10-12 — Dining menu correction versioning (careops-dining-correction-versioning-001)
`214523f`: published-item corrections are versioned replacements; draft correction no longer removes the live dish. Backend 618/0/31, frontend 95/649. Report docs/reports/2026-10-12-dining-correction-versioning.md.

## 2026-10-12 13:00 CDT — Dining dietary/allergen labels (careops-dining-dietary-allergen-truth-001) + wake recall status
Agent: Claude Code (coordinator caoscare-1-ee, resumed). Branch `integration/2026-09-27`.
`b2faae1`: staff-entered `dietary_labels` / `allergens` on MenuItem, bounded/normalized, through draft/publish/correction/receipts, repeated verbatim to residents/Aria with a no-inference note. Backend 640/2/13 (2 failures pre-existing on HEAD, OpenAI-key tests); frontend 95/652; build OK. Report docs/reports/2026-10-12-dining-dietary-allergen-truth.md. Browser acceptance pending: dev backend :8092 still `214523f` (restart needs Michael + idle room).
Wake (careops-room214-wake-recall-001): shadow 0.01/3.5 live since 12:20; 12:20–12:56 ~30 unlabelled bursts, no shadow_only; one live+shadow hit 12:56:16 (conversation ran). Still needs Michael's 10 labelled tries before changing the live score. No live wake setting changed. Production `ff87c22` unchanged.

## 2026-10-12 14:45 CDT — Public statuses to pilot; light on/off guard; Room 214 findings
Agent: Claude Code (coordinator caoscare-1-ee). Branch `integration/2026-09-27`.
- `ec51a8b` (owner direction): public capability statuses — help, one-press, low vision, staff dashboard, nursing, maintenance, transportation, dining, activities, housekeeping, front desk, administration, escalation, therapy → In pilot with stated limits; stale card text fixed. TV and climate stay In development (Room 214 TV commands all unverified = mock; Midea AC off commands failed). Frontend 95/652 then 96/659; headless render: home 0 "In development". NOT deployed: production `ff87c22` is 324 commits behind; needs Michael's deploy approval.
- `8126a7b`: toggle_light refuses (asks on or off) when the turn's transcript contradicts the model's on/off or asks for no power change. Replay over 146 past Room 214 light calls: 25 blocked incl. every wrong-direction case (09-06, 10-09, 10-10, 10-12 x2) and the 02:04 false wake "Overhead line". Room page rebuilt to `8126a7b` (`ctl.sh rebuild`); kiosk browser needs a reload to load it. Dev backend still `214523f`.
- Findings (Michael 2026-10-12: voice "different", false wake, needed ~3 tries): wrong-direction light commands predate the gpt-realtime-2.1/marin switch; tool-before-transcript ordering also predates it (64/114 Room 214 tool calls) and is already bounded by `realtimeTurnGrounding`. Michael: no rollback yet.
- Open: contrast (HC) button present on kiosk demo — Michael reports it missing on his screen (which screen not yet identified); dining browser acceptance (needs backend restart); wake labelled tries; production deploy.

## 2026-10-12 15:25 CDT — Dining labels DEV_ACCEPTED; dev backend + room page refreshed; HC button fix; release PR #132
- Dev backend restarted (Michael's permission, room idle) → `042ef84`, PID 1828430, log /tmp/room214_backend_042ef84.log (previous 214523f). Room 214 kiosk browser restarted 15:19, page reconnected 15:19:43 on build `8126a7b` (light on/off guard live).
- `careops-dining-dietary-allergen-truth-001` DEV_ACCEPTED: browser 11/11, report updated.
- `042ef84`: room screen top row wraps at phone width (HC button had been pushed off-screen).
- PR #132 (`release/public-pilot-statuses`, 2 commits on prod `ff87c22`: pilot statuses + HC wrap; 66 suites/553 tests, build OK). Merge to main blocked for the agent by Claude Code auto mode; awaiting Michael's merge, then `deploy_caoscare.sh` on caoscare-prod.

## 2026-10-12 16:35 CDT — Aria's opening after "Hey Aria"
`7bac843` (Michael: greeting was the same every call and should be "Hey Michael" with context): new `routes/aria_opening.py` — wake-word start → one short answer to their name instead of the time-of-day greeting; every start names the previous call's first line so she varies it (read from db.conversations; no new store). Tests 5 new; backend gate 645/2/13 (same 2 pre-existing OpenAI-key failures). Dev backend restarted (room idle) → `7bac843`, PID 1916400, log /tmp/room214_backend_7bac843.log. Live check pending Michael's next "Hey Aria".

## 2026-10-12 17:05 CDT — da-a3817b6b9c resident-Aria continuity + goodbye; PR #132 LIVE on caoscare.com
Executing session caoscare-1-64 (b2 notified; ACK https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-6133170717).
- `9f71f10` goodbye: open tool calls answered before the goodbye is requested (fixes "I'm still waiting on that to finish"); goodbye = brief echo ("Okay, bye for now."), nothing else.
- `9d15215` continuity: window 18 h → 72 h (same caps); header lets Aria notice recent/earlier talk in her own words (no script, no invention, never a reopened request); recent-return note invites a warm "didn't I just talk to you?"; age_phrase uses facility calendar days (9 PM last night ≠ "earlier today"). `test_aria_rewake_continuity.py` builds the real prompt for immediate re-wake and next-day. Also fixed the 2 long-failing tests (iter10 configured voice; iter8 auth header).
- Gates: backend 650 passed / 0 failed / 14 skipped; frontend 96 suites / 660.
- Dev: backend `9d15215` PID 1935308 (log /tmp/room214_backend_9d15215.log); Room 214 page rebuilt `9d15215`, kiosk reloaded, reconnected 16:56:28.
- PRODUCTION: PR #132 merged by Michael; deployed `06e7e2b` to caoscare.com 17:03 CDT (backup /opt/caoscare/backups/mongo/20261012-220310-pre-deploy-ff87c22df1dd; rollback `deploy_caoscare.sh ff87c22`). Chrome: home page all In pilot except Building-wide location (Planned); live kiosk 390 px shows HC.
- Open: real-voice evidence in Room 214 for re-wake greeting, next-day continuity, "bye for now".

## 2026-10-12 17:45 CDT — Lifelong resident memory (Michael: "she shouldn't forget what happened 3 days ago")
- `2013d53`, `46b99d4`: `routes/aria_life_memory.py` on the existing `db.memories` store — each finished conversation summarized once (events bin, category `conversation`, `source_session`; nothing-substantive stored archived) and folded into one bounded life story per resident (facts bin, `life_story`, pinned, `covers_sessions`). Loaded every call under "Your story with {name} so far" plus dated moments, facts and the 72 h verbatim recap. Background at session mint; trusted turns only; failures retried. Fold rules forbid invented relationships/labels; story trimmed at a sentence.
- Backfill (real OpenAI, `OPENAI_TEXT_MODEL` gpt-4o-mini) of Room 214 resident res_2425767f4a51: 49 sessions → 34 summaries, 15 nothing-substantive; life story 1155 chars covering 34. First fold invented "his friend Momdani" → rules tightened → rebuilt story states only "someone named Momdani".
- Gates: backend 652/0/13 (before the 46b99d4 prompt tweak; its tests 3/3). Dev backend `46b99d4` PID 1965332.
- Open: real-voice check in Room 214 (re-wake, next day, bye for now, memory references).

## 2026-10-12 18:30 CDT — Room hardware: HA LAN relay live; "Voice PE" on USB was the XIAO IR Mate
- `bcfeae7`: `room-node/ha_lan_proxy` (user service `ha-lan-proxy`, owner-approved) exposes the HA VM (192.168.122.137:8123, libvirt NAT) at http://192.168.1.151:8123; verified 200 from the LAN address. Undo: `systemctl --user disable --now ha-lan-proxy`.
- The small unmarked device Michael plugged into the EliteDesk (USB 303a:1001, /dev/ttyACM0, ESPHome firmware) is an **ESP32-C3** (esptool chip-id; MAC ac:27:6e:81:2d:fc) = the Seeed XIAO IR Mate, not the Voice PE (ESP32-S3). Michael confirmed. Temporary ACL on /dev/ttyACM0 for caoscare-1 (cleared on replug). Nothing written to the device.
- HA cannot discover BLE devices itself (VM has no Bluetooth); Wi-Fi provisioning goes through a phone/laptop (improv-wifi.com or the HA app) with Michael entering the Wi-Fi password.
- Voice PE: not yet located / arrived. Next: Voice PE stock-firmware bring-up when it is in hand; IR Mate setup (TV/AC) as a separate task.

## 2026-10-12 18:50 CDT — XIAO IR Mate set up (Wi-Fi + Home Assistant)
Factory reset (Michael), Wi-Fi provisioned by Michael via its hotspot page. On LAN at 192.168.1.160 (MAC ac:27:6e:81:2d:fc, DHCP - reserve it on the router), Seeed firmware xiao.smart-ir-mate 2.0 (ESPHome 2025.7.0-dev). Added to HA via the ESPHome config flow (HA_TOKEN): entry "XIAO Smart IR Mate 812dfc". Entities: select …_signal_select (Signal0–9), button …_learn, button …_send, switch …_is_learned_signal, switch …_vibration_device, light …_wifi_rgb_light. No signals learned yet. Not yet wired to CAOSCare's TV device (Room 214 TV is still a mock device).

## 2026-10-12 19:25 CDT — IR Mate firmware + system-wide ir_blaster TV adapter; Room 214 TV is real
- `f198372` room-node/ir_mate/caoscare_ir_mate.yaml: Seeed IR Mate config + HA actions send_sony/nec/samsung/lg/rc5/pronto/raw + receiver dump; ESPHome 2025.7.5; OTA to 192.168.1.160 (Wi-Fi kept). HA services esphome.xiao_smart_ir_mate_812dfc_send_*.
- Live (Michael watching): Sony discrete power on (0x750) / off (0xF50) / on all worked; volume 100 down + 50 up worked. Learned-signal replay had failed (truncated capture, idle 65.5 ms). The IR Mate's top is a touch sensor that sends slot 0 + vibrates (explains vibration when picked up).
- `ffeca1a`: backend ir_codesets.py (sony_sirc12) + device_ir_adapter.py (protocol ir_blaster; verified=False always; volume estimate only after a reset/absolute set); Aria adjust_tv_volume on volume_step TVs sends presses and asks, never names a level. Backend 661/0/13; frontend 96/661.
- Room 214 TV dev_c32e59817eed switched from protocol mock to ir_blaster (endpoint esphome.xiao_smart_ir_mate_812dfc, codeset sony_sirc12, caps power/volume/volume_step/mute; previous: mock, caps power/volume/input). Room command path test: volume_step +3/-3 executed, verified=false. Gap noted: PUT /devices/{id} writes no receipt.
- Next: Bravia network control (HA braviatv, Michael sets PSK) for verified read-back; disable IR Mate touch-send; reserve 192.168.1.160 on router.

## 2026-10-12 20:35 CDT — Receipt law for device records; call-start TV duck (platform-wide)
- `61506b1`: device registry create/update/delete receipted (`device_record_*`, actor/authority/before/after), owner/admin only (anon PUT → 401 on dev). Backend 662/0/13. Backfilled receipt `rcpt_fe312748ba12` for the 19:09 direct DB switch of the Room 214 TV (mock → ir_blaster), actor_type system, "Claude Code coordinator caoscare-1-64, on Michael's instruction".
- `bff666b` + `ea8e70c`: `frontend/src/lib/callAudioDuck.js` — calls turn TVs/speakers DOWN 15 (IR: steps; known volume: exact level), never off, restored on every call end; duck runs alongside the greeting. Live Room 214 20:23:47: volume_step −15 at wake, +15 at call close 20:24:02, both receipted `resident_aria_device_command` completed/unverified; greeting was 5 s late before `ea8e70c`. Frontend 98/666. Room page `ea8e70c`; dev backend `61506b1`.

## 2026-10-12 21:00 CDT — Call-start TV mute proven (platform-wide `816f5f2`)
Live Room 214, 6 calls 20:38–20:58: each sent exactly one mute at wake and one at call end (12 executed, receipted, unverified), including a 13 s call; greeting audio 3–4 s after wake (breakdown 20:38: session mint 1.7 s, WebRTC 0.9 s, first model audio 1.5 s). Next: faster wake response (pre-mint/pre-connect, shorter opener), labelled wake tries, Bravia network control, IR Mate touch-send off, Voice PE, production release.

## 2026-10-12 22:02 CDT — EliteDesk GitHub runner bridge proven; exact-SHA deployment workflow proposed

- **Agent/tool used:** Codex Work; GitHub connector; GitHub Actions runner `elitedesk-caoscare`.
- **Branch/ref:** `chore/elitedesk-caoscare-bridge`, PR #133 targeting `integration/2026-09-27`.
- **What changed:** added a read-only EliteDesk inventory/proof workflow and a separately gated exact-SHA deployment workflow. The deployment workflow is manual/tag-triggered only, accepts only a full commit in the authorized integration history, refuses tracked host changes or dependency-file changes, uses the existing guarded backend restart and room-page rebuild controls, and publishes a durable receipt.
- **What was verified:** runner `elitedesk-caoscare` version 2.337.0 ran on `caoscare1-hp-elitedesk` as `caoscare-1`; read-only run 38339790348 succeeded at 2026-10-13T03:02:45Z and preserved an artifact. Deployment-workflow validation run 38340115845 succeeded; the real deployment job was skipped on the PR as designed.
- **Runtime evidence:** `/home/caoscare-1/CAOSCARE-INTEGRATION` was clean at `e3636d016027c06fcc39f26429d63d5e094bd04e`. Live ports: backend `:8092` health 200, room page `:3002` health 200, wake listener `:8765`, Home Assistant `:8123`, frontend dev server `:3000`; old `:8000`/`:8001` backends absent. The live backend reported `CAOSCARE_RUNTIME_SHA=61506b1`, so the loaded backend revision is verified stale relative to the clean integration checkout. `aria-wake.service`, `aria-wake-page.service`, `aria-wake-kiosk.service`, and `caoscare-frontend-dev.service` were active. Disk: 38 GiB free / 83% used; swap: 2.0 GiB used of 2.0 GiB.
- **No deployment performed:** no application checkout was changed, no CAOSCare service was restarted, and Linode was not accessed.
- **Blocked at this timestamp:** PR #133 was not merged. A real deployment additionally required an exact approved integration SHA and an explicit dispatch confirmation or an owner-authorized `elitedesk-caoscare-deploy-*` tag.
- **Next safe step at this timestamp:** carry the proven bridge files into the authorized integration revision, run `verify-only`, then perform the guarded backend and room-page deployment.

## 2026-10-12 22:26 CDT — RQ-047 live-search privacy and cost provenance hardening

Agent: Codex. Branch `fix/rq047-private-live-search`, based on `integration/2026-09-27` at `e3636d0`.

- Existing RQ-047 architecture was preserved: Realtime `research_topic` calls the backend Responses API `web_search` provider; no duplicate provider or tool path was created.
- Provider requests now set `store: false` and explicit `external_web_access: true`.
- Private `research_lookup` evidence now records citation details, provider response ID, search-call count and sanitized input/output/total token counts. The resident question remains excluded; only its existing short hash and length are logged.
- Failing-before proof: `test_live_success_with_citations` failed on missing usage provenance before the implementation. Focused after-proof: `backend/tests/test_rq047_openai_web_search.py` = 14 passed.
- Modified implementation line counts: `research_openai_search.py` 155; `research.py` 170. Both remain below the repository split threshold.
- Runtime: NOT CHANGED. No paid call, backend restart, Room 214 setting change, or deployment occurred. Latest independently verified bridge observation remains backend runtime SHA `61506b1`; host proof after this branch does not exist yet.
- Blocked decision before a paid smoke/live switch: select `OPENAI_RESEARCH_MODEL`; then one isolated owner-authorized lookup must prove `live=true`, citations, natural spoken delivery and the new usage receipt. Room 214 enablement remains a separate guarded restart decision.

HANDOFF CAPSULE
- Objective: harden, smoke-test and then enable truthful live web lookup for Room 214.
- Branch: `fix/rq047-private-live-search`.
- Lane / ownership: RQ-047 provider privacy/provenance only; do not change wake, TV/audio, personality or operational workflows in this branch.
- Last proven state: focused mocked provider test 14/14; runtime unchanged.
- Commits: pending at this entry.
- Runtime state: backend runtime SHA `61506b1` per latest bridge inventory; this branch not loaded.
- Unresolved proven defects: historical Realtime usage was not logged, so prior-call cost can only be estimated; live research remains disabled.
- Product invariants that matter here: truthful `live` flag requires real search + citation; resident privacy; receipt provenance; no restart during a live lease.
- Do NOT change: wake thresholds, TV ducking, Realtime model, Linode, PR #41/#42.
- Next safe action: commit/push this branch, run CI, select the research model, then perform one isolated capped smoke call before any Room 214 switch.

## 2026-10-12 23:00 CDT — IR Mate touch decision + current Aria completion boundary

**Owner decision:** keep the XIAO Smart IR Mate's top touch behavior and configure it as local TV power
through learned `Signal0`; do not disable touch. This supersedes the 19:25/21:00 “disable touch-send”
next-step notes above without erasing that history. The firmware sends the currently selected learned
slot (initially Signal0), so setup must put TV power in Signal0, leave Signal0 selected, warn that pickup
can trigger it, and physically prove it before acceptance. The exact hardware/setup/read-back reference
is now `room-node/ir_mate/README.md`. This entry documents the decision only; no firmware, device,
Home Assistant, Room 214 runtime, merge, or deployment was changed.

Current task checklist — checked means the work product exists, not that pending live/release gates pass:

- [x] **Audit complete:** 31 recent Room 214 sessions (224 stored turns, 185 completed responses) plus
  wake/greeting, goodbye, TV command grounding, one-way IR truth, audio duck/restore, and profile paths
  were reviewed against current source and the owner's reported physical behavior. Unsuccessful wake-word
  attempts are not present in conversation rows and still require separate labeled listener evidence.
- [x] **Historical voice-cost estimate complete:** observed speech/playback plus current Realtime pricing
  supports a likely $1.43–$2.89 total for the 31 sessions and a deliberately pessimistic $14.40 planning
  ceiling. This is an estimate, not an actual-usage receipt, because historical `response.done` usage was
  not persisted. The live-search smoke has a separate proposed cap below $0.05 and is still pending owner
  authorization.
- [x] **Code/PR preparation done:** draft PR #135 contains the bounded truth/conversation fixes; backend
  smoke and the full frontend check pass at remote revision `7449dbf`. This checkbox does not claim merge,
  deployment, or live loading.
- [ ] **Paid live-search smoke pending:** no paid call, verified `live=true` result, URL-citation evidence,
  provider usage receipt, or production enablement was produced in this task.
- [ ] **Merge/deploy pending:** the current branch changes are not claimed merged, deployed, or loaded.
- [ ] **Room 214 acceptance pending:** Michael physically reported that pickup/top touch vibrates and
  toggles the TV, confirming the desired feature informally. Formal acceptance still requires labeled
  normal-voice wake, greeting, first-utterance goodbye, touch/pickup behavior, truthful command wording,
  mute/restore, and rapid close→wake tests against the exact loaded revision with receipts and timestamps.
- [ ] **Exact Realtime usage logging pending:** persist actual per-session `response.done` usage/model data
  and compute cost only from provider-reported units and a verified current price table. Estimates are not
  usage evidence.
- [ ] **Verified owner profile and personality profiles pending:** prove Michael's selected owner/home
  behavior and each supported resident interaction/personality profile through the authoritative saved
  record, prompt/session load, and labeled live behavior. Code/config existence alone is insufficient.
- [ ] **Installer manual completion pending:** the IR Mate README now records exact puck behavior and an
  interim checklist, but the full multi-device installer manual still needs provisioning screenshots,
  site survey/mounting standards, network/fleet naming, rollback/replacement, privacy/safety handoff,
  acceptance receipts, and owner approval.

## 2026-10-12 23:28 CDT — Owner-authorized Aria integration, live-search proof, and EliteDesk load

- **Authorization:** Michael directed Codex to finish without routine permission stops at 23:18 CDT and
  approved use of the existing OpenAI key, `gpt-4.1-mini`, the bounded live-search proof, integration,
  and guarded EliteDesk loading. Linode remained excluded.
- **Merged revision:** PR #135 merged to `integration/2026-09-27` as
  `e13b78492e536a337601db21c3b3e444c8ad2565`. It reconciles the normal greeting/goodbye and truthful TV
  controls, private live-search receipts, exact puck literature, and the proven EliteDesk bridge. The
  superseded PR #133 and #134 threads were linked to #135 and closed without separate merges.
- **Repository gates:** backend smoke passed; full frontend check passed; EliteDesk workflow validation
  passed; read-only inventory passed; focused research tests 14/14; focused frontend tests 93/93;
  end-call regression tests 64/64.
- **Paid live-search proof:** runs 38346316253 and 38346385004 each returned `live=true`, one URL citation,
  one search call, and sanitized provider usage from `gpt-4.1-mini-2025-04-14`. The first recorded 8,629
  input + 81 output tokens; the second 8,629 input + 64 output tokens. Branch creation and the subsequent
  trigger commit each fired the one-shot workflow, so two bounded calls ran instead of the intended one.
  Estimated combined cost is about $0.027, within the $0.05 cap. The temporary workflow was removed from
  the branch after proof; it cannot run again from that branch.
- **Guarded EliteDesk load:** run 38346538110 passed the no-live-lease/recent-activity guard, moved the
  controlled checkout from `e3636d016027c06fcc39f26429d63d5e094bd04e` to exact integrated revision
  `e13b78492e536a337601db21c3b3e444c8ad2565`, set provider `openai_web_search` and model
  `gpt-4.1-mini`, and retained a mode-0600 configuration backup at
  `/home/caoscare-1/caoscare-config-backups/backend.env.20261013T042755Z.before-live-search`.
- **Loaded proof:** backend health passed with `CAOSCARE_RUNTIME_SHA=e13b784`; the Room 214 page bundle
  changed from `main.ac24e887.js` to `main.70fa6eac.js`; `aria-wake`, `aria-wake-page`, and
  `aria-wake-kiosk` were active; room-page health passed. The temporary deployment workflow was removed
  from its branch after the successful receipted run.
- **Checklist reconciliation:** paid live-search proof, integration merge, and guarded EliteDesk loading
  are complete. Still not accepted: Michael's labeled physical Room 214 wake/greeting/search/TV/goodbye
  observations; missed-wake measurement; exact Realtime voice usage persistence; verified owner/personality
  profiles; and the completed multi-device installer manual.
- **Michael action:** run the short labeled Room 214 physical acceptance script supplied by Codex and
  report what was heard and what the TV did. No terminal or GitHub work is required.


## 2026-10-12 11:44 PM America/Chicago — Room 214 wake outage diagnosed, recovered, and deployment defect fixed

- **Owner observation:** eight normal-volume `Hey, Aria` attempts with the TV off produced no visible response.
- **Proven cause:** the microphone and wake engine were healthy. The listener recorded strong speech and multiple exact `HEY_ARIA` detections, but each reported `detection_no_client`. GitHub Actions deployment run `38346538110` had started backend PID `2110321`, then runner post-job cleanup terminated that descendant. Port `:8092` disappeared, the room-page `:3002` API proxy returned 502, the kiosk's one-shot initialization failed, and no wake WebSocket client remained.
- **Recovery:** restart was performed only after the lease/activity guard proved zero live calls. The backend was relaunched without `RUNNER_TRACKING_ID`; wake, page, and kiosk services were restarted in order after backend and proxy health returned.
- **Acceptance evidence:** [recovery run 38347856164](https://github.com/caosos/CAOSCARE.COM/actions/runs/38347856164) passed after the previous job had completed: backend health 200, room-page health 200, `aria-wake`, `aria-wake-page`, and `aria-wake-kiosk` active, fresh audio capture, fresh `client_connected`, and `backend_survived_runner_cleanup=passed`.
- **Permanent fix:** [PR #137](https://github.com/caosos/CAOSCARE.COM/pull/137) merged as `e79b1b8e3e991a54f9b1f56177839eaa66a28502`. The persistent backend launch now strips only the Actions ownership marker while retaining the existing no-live-call guard, PID ownership, exact runtime SHA, clean-tree, and health proofs. Backend smoke run `38347944180` passed, including the new regression test.
- **Rollback decision:** no application rollback. The `e3636d0..e13b784` diff did not modify wake detection, microphone capture, wake WebSocket, model, threshold, or kiosk service code. Rolling back would not address the proven process-lifecycle defect.
- **Loaded runtime:** application code remains `e13b78492e536a337601db21c3b3e444c8ad2565`; the merged `e79b1b8` change is deployment tooling/tests and does not require a room runtime reload.
- **Remaining physical acceptance:** one normal-volume Room 214 `Hey, Aria` observation, then the already-defined greeting/search/TV/goodbye sequence. Software readiness is proven; physical acoustic behavior still requires Michael's observation.
- **Blocker:** physical Room 214 observation only.
- **Michael must do:** say `Hey, Aria` once at normal volume and report whether she answers. No terminal or GitHub action is required.


## 2026-10-12 11:51 PM America/Chicago — Room 214 wake recovery physically accepted; resident guidance profiles clarified

- **Physical observation:** Michael said `Hey, Aria` once at normal volume after recovery. Aria picked it up immediately.
- **Conversation observation:** Aria did not sound clingy. This is the desired behavior for Michael's personal profile.
- **Profile requirement:** Michael's profile stays concise, natural, context-aware, and avoids unnecessary return/availability commentary. The default **80-plus profile** provides more hand-holding: clearer choices, brief confirmation of what happened, and simple next-step instruction when the resident may not know how to continue.
- **Invariant:** extra guidance is selected by the resident/profile and situation. It is not a second operating system and must not make every response verbose.
- **Acceptance status:** wake recovery physical acceptance PASSED for one normal-volume attempt. The broader search/TV/goodbye sequence remains separately testable; this receipt does not invent results for those steps.
- **Michael must do:** NOTHING for this accepted wake/profile observation.


## 2026-10-12 11:53 PM America/Chicago — Room 214 wake/TV/close chain physically accepted

- **Negative wake test:** saying `Aria` alone did not wake the system. This is required because Michael discusses Aria frequently.
- **Positive wake test:** saying `Hey Aria` woke the system immediately.
- **Physical behavior:** the TV muted when the conversation opened and unmuted after the conversation closed.
- **Close behavior:** Michael said `Goodbye`; Aria answered exactly `Okay, bye for now.` and the session ended.
- **Acceptance:** the complete observed chain—wake phrase discrimination, wake delivery, TV duck, conversation, concise goodbye, session close, and TV restore—PASSED in Room 214.
- **Product observation:** Michael expects residents to value this interaction and the puck's touch-to-TV-power feature, especially when the puck is placed beside a chair or stand within reach. Keep touch-to-TV-power; document reachable placement in installation literature.
- **Remaining personal-profile polish:** Aria also said, `I'm here if you want to chat, or we can just sit quietly for a bit. Your call, Michael.` That is still over-helpful for Michael's concise profile and remains an exact wording defect to remove there. It may remain appropriate in the 80-plus hand-holding profile.
- **Blocker:** NONE for the recovered wake/TV/close chain.
- **Michael must do:** NOTHING for this acceptance receipt.


## Tuesday, October 13, 2026 — 12:23 AM America/Chicago — Aria recovery, profiles, and governed TV setup ready to merge

- **Current phase/milestone:** Room 214 reliability and resident personalization; repository verification is complete and guarded EliteDesk loading is the next bounded stage.
- **Work completed since the prior check:** fixed the malformed persistent-backend launch; added the static regression guard; made the wake listener return to listening after its final client disconnects; added a content-free capture heartbeat and transient kiosk-bootstrap retry; implemented `supportive_guided` and `concise_natural` resident profiles; added a session-bound, explicitly confirmed TV remote setup flow; corrected infrared truth labeling; linked live research to resident/session provenance; captured sanitized Realtime token usage; added post-runner-cleanup survival proof; and reconciled the demo/self-install literature.
- **Evidence and provenance:** [PR #141](https://github.com/caosos/CAOSCARE.COM/pull/141), head `9e7a453b56f1271dfd043312aa28344f5a322dc6`; [frontend run 38350801781](https://github.com/caosos/CAOSCARE.COM/actions/runs/38350801781) passed; [backend run 38350801755](https://github.com/caosos/CAOSCARE.COM/actions/runs/38350801755) passed, including compile/import and the deployment restart regression suite; [deployment-workflow validation run 38350801764](https://github.com/caosos/CAOSCARE.COM/actions/runs/38350801764) passed. Local focused evidence: wake 16 passed; governed remote/profile 6 passed; focused frontend 35 passed; affected Realtime 26 passed; production frontend build passed. Tested revision: `9e7a453b56f1271dfd043312aa28344f5a322dc6`. Loaded revision: `e13b78492e536a337601db21c3b3e444c8ad2565`. Latest host observation: the previously accepted Room 214 `Hey Aria` → TV mute → conversation → `Okay, bye for now.` → TV restore chain; no newer host runtime proof is claimed in this entry.
- **ONE current bounded task:** merge the green PR through the existing CAOSCare repository path, then load the resulting exact integration SHA through the existing self-hosted `elitedesk-caoscare` runner with the no-live-call guard. Responsible coordinator/worker: CAOSCare coordinator / Codex. Stage: repository gates passed; authoritative-state reconciliation in progress.
- **Remaining steps for this milestone:** (1) commit this authoritative state entry to PR #141; (2) rerun and verify required repository gates; (3) merge the exact reviewed head; (4) run the guarded EliteDesk backend-and-room-page deployment; (5) verify the post-cleanup backend-survival job, runtime SHA, room-page health, fresh capture heartbeat, and connected wake client; (6) resolve Michael's exact resident record and save `concise_natural` with a receipt; (7) perform one short spoken acceptance covering wake, natural greeting, live lookup, governed TV setup wording, goodbye, and TV restore.
- **Upcoming milestones:** second-room installation repeatability; production-grade IR catalog/physical slot-write support; supported state-reporting TV/numeric-volume integrations; per-device production provisioning and replacement procedure.
- **ETA:** UNKNOWN. Repository gates are green, but deployment duration and the no-live-call guard outcome cannot be invented.
- **next_check_at:** MISSING. Progress continues immediately and event receipts are authoritative.
- **Blocker:** NONE for merge preparation. EliteDesk loading must stop if an active/recent resident call is detected.
- **Michael must do:** NOTHING during merge and guarded loading. The final physical spoken acceptance remains a Michael observation and will not be claimed from software evidence.


## Tuesday, October 13, 2026 — 12:30 AM America/Chicago — Guarded EliteDesk load stopped before mutation

- **Transition:** PR #141 merged to `integration/2026-09-27` as `ccab481b628288dc92ee01fb4d1b54116c07f617` after fresh frontend, backend, and deployment-validation checks passed.
- **Deployment receipt:** [run 38351708656](https://github.com/caosos/CAOSCARE.COM/actions/runs/38351708656) accepted the exact SHA and authorization, then stopped in the pre-deploy test step before host-state verification or loading. The repository test gate required `MONGO_URL`, `DB_NAME`, and `JWT_SECRET` in the pytest process environment; the self-hosted deployment job had not supplied them.
- **Host evidence:** the failure receipt recorded `host_head=e13b78492e536a337601db21c3b3e444c8ad2565`. No checkout load, service restart, resident-profile write, or Room 214 runtime change occurred.
- **Current bounded task:** add the same non-production test environment used by repository CI to the deployment job, verify through a new PR, merge, and rerun the existing exact-SHA guarded workflow. Responsible coordinator/worker: CAOSCare coordinator / Codex. Stage: workflow correction in progress.
- **ETA:** UNKNOWN.
- **next_check_at:** MISSING; work continues immediately.
- **Blocker:** deployment workflow test environment incomplete. This is a workflow defect, not a wake, microphone, Aria, or EliteDesk runtime failure.
- **Michael must do:** NOTHING.


## Tuesday, October 13, 2026 — 12:57 AM America/Chicago — New runtime and wake services loaded; journal timestamp proof failed

- **Transition:** PR #144 merged as `86759d30b8bea2b0f297aaf13582118fa398b6ef`; [deployment run 38353670980](https://github.com/caosos/CAOSCARE.COM/actions/runs/38353670980) passed all pre-deploy tests, host health, clean-checkout and no-live-call guards, exact revision load, and backend restart.
- **Loaded evidence:** controlled checkout and backend runtime are exact `86759d30b8bea2b0f297aaf13582118fa398b6ef`; backend PID `2139668`, runtime SHA `86759d3`, health passed. Frontend rebuilt successfully as `main.78489bba.js`. The guarded full wake/page/kiosk restart command and immediate service/health/listener checks completed before the proof loop.
- **Incomplete proof:** the host's `journalctl` rejected `2026-10-13T00:56:13-05:00` as a `--since` timestamp. The step stopped before checking fresh `capture_alive` and connected-client records, and the dependent backend-survival job was skipped.
- **Current bounded task:** use the host-supported `YYYY-MM-DD HH:MM:SS` journal timestamp, verify through PR, and rerun the exact-SHA guarded proof. Responsible coordinator/worker: CAOSCare coordinator / Codex. Stage: one-line workflow correction in progress.
- **ETA:** UNKNOWN.
- **next_check_at:** MISSING; work continues immediately.
- **Blocker:** proof-script timestamp compatibility only. No current application, build, or service failure is established.
- **Michael must do:** NOTHING.


## Tuesday, October 13, 2026 — 12:47 AM America/Chicago — Exact revision loaded; fresh wake proof incomplete

- **Transition:** PR #143 merged as `5b571b3bad0f759cf052defb0c5ae3ef7511a11f`; [deployment run 38352764203](https://github.com/caosos/CAOSCARE.COM/actions/runs/38352764203) passed 17 backend restart tests, 16 wake tests, the room-page server test, current-host health, the clean-checkout guard, and the no-live-call guard.
- **Loaded evidence:** the controlled EliteDesk checkout moved from `e13b78492e536a337601db21c3b3e444c8ad2565` to exact `5b571b3bad0f759cf052defb0c5ae3ef7511a11f`. Backend restart passed with PID `2135089`, runtime SHA `5b571b3`, zero live leases, zero recent calls, and health passed. The production frontend compiled as `main.78489bba.js` and was placed in the wake-page build directory.
- **Incomplete proof:** the room-page step restarted only the page and kiosk, then required the new `capture_alive` event from `aria-wake`. Because the wake service itself was still the pre-deploy process, the new heartbeat code was not loaded; the step failed and the dependent post-cleanup survival job was skipped. This is missing acceptance evidence, not proof that the new wake code failed.
- **Current bounded task:** change the guarded room-page load to restart `aria-wake`, page, and kiosk together, then poll only post-restart journal evidence for a fresh capture heartbeat and connected client before declaring success. Responsible coordinator/worker: CAOSCare coordinator / Codex. Stage: workflow correction in progress.
- **ETA:** UNKNOWN.
- **next_check_at:** MISSING; work continues immediately.
- **Blocker:** fresh wake-service heartbeat/client proof and post-runner-cleanup backend survival proof are not yet complete.
- **Michael must do:** NOTHING.


## Tuesday, October 13, 2026 — 12:38 AM America/Chicago — Wake-test interpreter mismatch stopped second load

- **Transition:** PR #142 merged the bounded test environment as `4744e0df0c995d8b6250d74d883b4bf4b1617d37`; its deployment-workflow validation passed.
- **Deployment receipt:** [run 38352121463](https://github.com/caosos/CAOSCARE.COM/actions/runs/38352121463) passed all 17 backend restart regression tests on the EliteDesk, then stopped during wake-test collection because the workflow invoked the backend virtual environment, which does not include the wake service's `websockets` dependency.
- **Host evidence:** the failure receipt again recorded `host_head=e13b78492e536a337601db21c3b3e444c8ad2565`. Host verification, checkout loading, restart, and runtime mutation were skipped.
- **Current bounded task:** run wake tests with the controlled integration checkout's existing wake-service interpreter at `room-node/aria_wake/.venv/bin/python`, fail closed if it is absent, verify through PR, merge, and repeat the guarded load. Responsible coordinator/worker: CAOSCare coordinator / Codex. Stage: workflow correction in progress.
- **ETA:** UNKNOWN.
- **next_check_at:** MISSING; work continues immediately.
- **Blocker:** pre-deploy wake tests used the wrong existing virtual environment. No package installation or runtime workaround is authorized or needed.
- **Michael must do:** NOTHING.


## Tuesday, October 13, 2026 — 1:05 AM America/Chicago — Living Community Simulator foundation isolated and tested

- **Owner direction:** build the Care App ourselves while another builder works in tandem; communicate exact file lanes first and do not use or dispatch the historical Claude Code workflow.
- **Coordination:** Issue #129 received the Living Community Simulator requisition/non-overlap notice and a correction naming Michael plus the current Care App builders as the active builders. Branch `feature/living-community-simulator` owns only the new community simulator modules, read-only simulator routes/UI, focused tests, and requisition report. No merge or deployment is authorized by this entry.
- **Declared scale:** deterministic blueprint for 80 apartments, 70 occupied apartments, 75 target residents, a 10-resident single-occupancy burn-in, and 50 simulated workers across Nursing/Care, Dining, Housekeeping, Maintenance, Transportation, Activities, Front Desk, and Administration/Leadership.
- **Planning implemented:** 90-day deterministic staffing projection; first-day 153-event resident routine plan; planned refusals and linked reschedules; projected clock-in, handoff, clock-out, and coverage-gap events. Every outcome and shift event is marked planned/not executed and cannot serve as a receipt.
- **Truth boundaries:** medication is reminder-only; meals never imply consumption; transportation and family contact remain coordination-only; external calls, resource booking, alerts, and content publishing stay blocked until simulation-isolated. Simulated workers are synthetic actors, never fake User/login records.
- **Admin Work-as foundation:** signed, short-lived work context keeps the real owner/admin as principal and records acting role, acting department, and work-context ID separately. It is not routed into production authorization yet.
- **UI/API:** owner/admin read-only community overview and preview routes feed Live Operations with declared counts, coverage gaps, planned routines/outcomes, shift-event counts, and blocked capabilities. The existing two demo-room scenarios remain the only runnable simulator actions; the UI explicitly says autonomous community execution is not yet running.
- **Verification:** 32 pure simulator tests passed locally. Python compilation and repository whitespace checks passed. Frontend tests and Work-as runtime tests were not executed in this container because frontend dependencies and PyJWT were not installed; PyJWT is already an existing backend requirement. No MongoDB, provider, production runtime, EliteDesk service, or resident record was changed.
- **Next bounded slice:** publish this isolated branch and draft PR; run repository CI; then add canonical, receipted burn-in provisioning and execution behind explicit reset/cleanup guarantees before enabling any autonomous run.
- **Michael must do:** NOTHING for this foundation slice.


## Tuesday, October 13, 2026 — 1:22 AM America/Chicago — Community false-empty guard merged; simulator P1A remains isolated

- **Observed live-UI problem:** the Admin page displayed “No community set up yet” after a shared-runtime interruption even though the department views remained present. The simulator branch had not been deployed and had made no database writes.
- **Proven UI defect:** `Admin.jsx` treated a failed or malformed `GET /facilities` response as a completed empty read. That made a backend restart or transient API failure look like deletion. No evidence established that the Conway facility record was deleted.
- **Fix:** PR #147 merged as `643e57891b3e395ec21a0d99e3fc940fceb6e5eb` after frontend CI passed. The UI now distinguishes loading, confirmed empty, and read failure; a failure says the community could not be verified, retains last-known facilities, and offers retry. It never creates or changes facility data. This merge has not been claimed loaded on the EliteDesk.
- **Coordination rule:** Issue #129 now forbids unannounced live-service restarts, database seeds, facility mutations or migrations. Any shared-runtime mutation must post its exact SHA, services/data affected, guard and rollback first.
- **Simulator P1A added to draft PR #146:** an idempotent ten-resident canonical provisioning service preflights resident-ID/room/pendant collisions, refuses unmarked or ambiguous records, creates/reuses canonical receipts, and never creates worker User accounts. A separate PAUSED-only adapter can create one shower-help request through the existing resident-request service and acknowledge it through the existing task lifecycle with an on-shift synthetic Nursing/Care actor and chained receipts.
- **Execution boundary:** neither P1A service has an HTTP mutation route or has been called against live data. The broader community is still planning-only and has not been deployed.
- **Verification:** 63 focused tests passed in the canonical dependency environment, including anonymous/staff rejection and owner/admin access for both read-only community endpoints, plus signed Work-as context tamper/expiry/principal tests. Frontend CI for the simulator head passed after its test alias correction; new-head backend/frontend CI remained in progress at this entry.
- **Next bounded work:** finish current CI, add guarded owner/admin mutation routes only after reset/replay and side-by-side real-record protections are proven, then review before any live load.
- **Michael must do:** NOTHING.


## Tuesday, October 13, 2026 — 1:33 AM America/Chicago — Simulator safety review closed two critical provenance gaps

- **Safe progress:** the planning-only workforce now gives all 50 synthetic workers one daily state across 90 days (32 scheduled / 18 off duty in the declared load model). Scheduled sessions contain planned login, clock-in, assignment acceptance, handoff and clock-out milestones; login explicitly creates no User or authentication token. Live Operations exposes counts only and still labels every milestone unexecuted/unreceipted.
- **Isolation evidence:** a side-by-side test keeps selected real resident/request/receipt rows byte-identical while one synthetic shower request is created, replayed, acknowledged and replayed through canonical service seams. No production data or provider was touched.
- **Narrow cleanup:** synthetic resident cleanup now requires an authenticated real owner/admin, exact living-community markers on all ten stable identities, all-record preflight before deletion, exact-match delete filters and append-only request/outcome receipts. It is resident-only cleanup, not a complete community reset, and has no mounted route.
- **Guarded control foundation:** the separate burn-in provisioning router defaults to dry-run, requires a PAUSED run, a principal/run/plan-bound five-minute confirmation and a default-off server execution flag. The router remains intentionally unregistered and undeployed.
- **Critical review fix:** living-community residents, runs, tasks, receipts and suppressed notifications now preserve server-derived `simulation_scope=living_community`, `simulation_community_id=sim:community:living-80-v1` and run ID. Demo or wrong-community synthetic identities/runs are refused. Legacy demo-room fallback remains compatible. Reprovision after cleanup now creates a fresh creation receipt for every new resident generation instead of reusing historical evidence.
- **Verification:** 99 focused simulator/work-context tests passed; compileall and whitespace checks passed. Frontend dependencies are absent locally, so the attendance UI test must be proven by GitHub CI after publication. The Mongo integration provenance test was added but could not complete in this scratch runtime because no reachable test MongoDB was available; pure scope/model/provider-suppression tests passed.
- **Still blocked from execution:** no three-month unattended executor, durable cursor/lease/restart recovery, dependency-aware reset, run-state concurrency guard, synthetic-row shared-reader audit, generic resident CRUD protection, active Work-as route/UI, or observed-versus-planned state read exists. Routine dispatch has five Administration family-call events after that shift ends, and attendance/shift planners currently duplicate clock/handoff/clock-out plans. These are explicit acceptance gates, not hidden claims.
- **Runtime boundary:** no simulator route was mounted, no branch was merged, no EliteDesk service was restarted, no database/provider was mutated, and no autonomous simulation ran.
- **Next safe action:** make reset dependency-aware and bind mutation to a durable living-community run lease; then remove duplicate shift streams and require an on-shift assignment before any routine can execute. Do not enable the dormant mutation control before those gates pass.
- **Michael must do:** NOTHING.


## Tuesday, October 13, 2026 — 1:48 AM America/Chicago — Simulator cross-boundary interference guards verified

- **Published checkpoint:** draft PR #146 heads `30273c851e377bebb7f746c4a161945705aaee22` and `f3a5575b21d6f7a05b96cb45a4238c44d33a5c2b` each passed both GitHub frontend and backend checks. Issue #129 contains the standing tandem-builder file-lane and no-unannounced-runtime-mutation handoff. Work added after `f3a5575` remains on the isolated feature branch pending its own CI.
- **Durable execution foundation:** a living-community-only Mongo lease boundary now gives each executor acquisition a monotonically increasing fence, requires the exact live owner for heartbeat, refuses PAUSED/stale/expired owners, and advances the run cursor by exact compare-and-swap. It is not connected to a loop or route.
- **Reset safety:** resident cleanup now refuses before its first receipt or delete when canonical tasks, notifications or run evidence still depends on any burn-in identity. It does not cascade-delete evidence. Cleanup and provisioning/control receipts have searchable top-level community/scope/run markers while retaining the authenticated human as the real actor.
- **Schedule truth:** the 75-resident routine plan keeps minute-of-day in `0..1439`, records explicit day rollover, and lets day-89 work drain into day 90. Clock-in/handoff/clock-out now have one canonical shift-event stream; attendance owns only login and assignment acceptance and references the canonical shift milestones.
- **Shared-code isolation:** generic resident PUT, DELETE, public preferred-name PATCH, and delegated admin-assistant edits now refuse living-community records at pre-read and atomic mutation filters. Always-on alert/task escalations exclude exact living-community records at selection and claim. Family alert SMS/email derives simulation provenance from server-owned resident truth and suppresses provider calls; real residents and legacy demo behavior remain unchanged.
- **Additional guarded planning:** recurring task templates refuse or skip living-community residents, and automatic haiku generation refuses before any OpenAI call. Uncovered routines remain explicitly queued/unassigned; the five after-hours Administration family-call events wait until next-day coverage instead of claiming work occurred. Department preflight derives all eight required slugs, returns an immutable digest and distinguishes missing/inactive rows. The current default catalog is missing `front_desk`, so start must remain blocked until that canonical department exists and is active.
- **Rota truth:** all 50 identities remain stable and every worker now receives at least one rest day in every rolling seven-day window. This exposes a real shortage: with three maintenance identities covering three daily slots, one maintenance shift is unfilled each day once days off are honored. Daily planned attendance is therefore 31, not the previously claimed 32, until staffing is increased or the coverage requirement is changed.
- **Verification:** 169 focused simulator, resident-guard, recurrence, escalation-exclusion, provider-suppression, haiku-boundary, access-control, and Work-as tests passed together; compileall and whitespace checks passed. No reachable local MongoDB exists for the direct integration provenance tail, so that remains a CI/integration requirement.
- **Runtime boundary:** no simulator route was mounted, no execution flag was enabled, no feature commit was merged or deployed, no EliteDesk service restarted, and no live database/provider call was made.
- **Remaining gates:** no unattended executor, restart catch-up/reconciliation or complete atomic reset exists; memory/classifier, seed, location, insights and other bulk processors still need living-community policy; planned-vs-observed database truth is not yet separated in the UI; resident-specific synthetic care plans are not yet modeled; `front_desk` is missing from the default canonical department catalog; maintenance and several departments do not meet continuous 24-hour coverage with the current 50-person roster; Work-as is not integrated into department UI/routes; and current feature-head CI must pass.
- **Next safe action:** publish this second guarded tree to draft PR #146, verify both CI checks, then add department/preflight and controlled on-shift queue semantics before wiring any executor.
- **Michael must do:** NOTHING.


## Tuesday, October 13, 2026 — 10:44 AM America/Chicago — Observed community truth and remaining isolation guards completed

- **Integration reconciliation:** `feature/living-community-simulator` now includes the current
  `integration/2026-09-27` facility false-empty and guarded-deployment work. The merge was confined to the
  feature branch; no integration branch, runtime, service, database, or facility record was changed.
- **Observed truth:** `community_observed_state.py` reads canonical residents, tasks, notifications, and
  simulator runs and reports `loaded`, `unknown`, or `error`. A ten-resident burn-in is classified only from
  exact stable resident ID, room, pendant, and living-community markers as `not_provisioned`, `partial`,
  `provisioned`, or `inconsistent`. Failed reads remain null/unknown and can never become a false zero.
- **Read-only API/UI:** owner/admin `GET /api/simulator/community/observed` returns counts only when every
  required source loaded; otherwise it returns 503 without counts. Live Operations keeps the planning preview
  separate from observed records. Initial failure says observed state is unknown, and a later refresh failure
  preserves and labels the last verified snapshot instead of replacing it with zero.
- **Resident planning:** every one of the 75 synthetic blueprint residents has a deterministic, varied,
  planning-only preference and assistance profile. The source explicitly says it is synthetic, non-clinical,
  unconfirmed, and not evidence of consent, an order, an assessed need, or completed care. It is not connected
  to execution or the database.
- **Remaining shared-code guards:** legacy demo seed, mock location, and bulk insight paths exclude exact and
  malformed living-community identities. Automatic memory extraction and alert AI classification fail closed
  before provider use when server-owned identity belongs to this community. Real residents and the legacy
  `demo_room` path remain unchanged.
- **Verification:** 214 focused backend simulator, access, Work-as, resident/template/bulk, memory/classifier,
  family/provider, and observed-truth tests passed together; 12 focused frontend tests passed; the production
  frontend build compiled; Python compilation and repository whitespace checks passed. Earlier direct restart
  tests had five local port-ownership timing failures in this scratch environment; those deployment-lane tests
  are unchanged by this slice and current GitHub CI remains the clean-environment authority. No reachable local
  MongoDB was used, so no direct-database or browser runtime acceptance is claimed.
- **Runtime boundary:** no mutation route was enabled, no simulator run was started, no seed or cleanup ran,
  no provider was called, no branch was merged or deployed, no EliteDesk service was restarted, and no live
  facility/resident record was changed.
- **Remaining gates:** the community still needs its unattended fenced executor, restart catch-up and
  reconciliation, complete dependency-aware atomic reset, canonical `front_desk` department, an explicit
  staffing decision for uncovered 24-hour shifts, active Work-as route/UI integration, direct-Mongo proof, and
  current feature-head CI. The existing demo-room scenarios remain the only runnable actions.
- **Michael must do:** NOTHING while the isolated draft branch is verified.
## 2026-10-13 — Living-community unattended-loop core (isolated lane)

HANDOFF CAPSULE
- Objective: Drive the fenced living-community runner continuously, one due event at a time, with a durable accelerated clock and observable loop truth.
- Branch: `lane/community-loop`
- Lane / ownership: New loop core and focused tests only; no route, startup hook, default database, provider path, deployment, or live mutation.
- Last proven state: 61 focused loop/runner/timeline/executor tests pass; pause/resume, graceful cancellation, process-local non-overlap, restart receipt catch-up, blocked/error backoff, serialized ticks, and exact 90-day completion are covered.
- Commits: recorded in the branch commit that contains this capsule.
- Runtime state: No server, loop, database, provider, or deployment was started.
- Unresolved proven defects: none in this bounded loop core; integration still requires a reviewed durable clock advancer and explicit control-route wiring.
- Product invariants that matter here: same canonical event/receipt path; one fenced event per tick; no action without durable provenance; stopped/paused runs cannot execute; full horizon is 90 days.
- Do NOT change: Do not auto-start this loop, select a live database, attach a route/startup hook, or enable providers from this lane.
- Next safe action: Review and integrate the commit, then supply a separately tested atomic persisted-clock adapter before any control-surface wiring.

## 2026-10-13 — Living-community canonical live-activity projection (isolated lane)

HANDOFF CAPSULE
- Objective: Let an owner/admin watch recent exact-run canonical simulated tickets and their receipt-backed state transitions in Live Operations.
- Branch: `lane/community-live-activity`
- Lane / ownership: Read-only activity projection, existing runtime API composition, focused UI, and tests only; no lifecycle, executor, loop, provider, startup, deployment, or database mutation.
- Last proven state: 15 focused backend runtime/activity/API tests and 7 focused frontend tests pass; the production frontend build compiles. Wrong-run, wrong-scope, non-simulated tasks and non-synthetic resident identities are excluded; failed reads remain unknown rather than empty.
- Commits: recorded in the branch commit that contains this capsule.
- Runtime state: No server, simulator, database, provider, service, or deployment was started.
- Unresolved proven defects: The current executor may create and complete a ticket inside one tick; this read lane exposes the canonical completed task and both receipts but cannot itself create observable dwell time between states.
- Product invariants that matter here: canonical `staff_tasks` and receipts only; exact living-community/run scope; synthetic identity boundary; owner/admin read-only access; no action without provenance.
- Do NOT change: Do not add simulator mutations, executor staging, providers, startup hooks, or live data access from this lane.
- Next safe action: Integrate this projection, then separately stage canonical ticket lifecycle transitions across executor ticks so polling can visibly observe open, claimed/in-progress, and completed states.

## Tuesday, October 13, 2026 — 1:58 PM America/Chicago — Living-community runtime and observable ticket movement integrated

- **Branch/ref:** `work/living-community-operations`; isolated draft PR #146 remains unmerged and undeployed. This entry covers local commits through `5a954f2`; the last published remote checkpoint remains the earlier CI-green operations core.
- **Durable runtime:** exact-plan run creation, owner/admin PAUSED/RUNNING/STOPPED transitions, named-system accelerated clock, fenced one-event execution, restart receipt reconciliation, cancellable unattended loop, and receipt-backed automatic completion at the exact 90-day boundary are integrated. Automatic clock/completion receipts are system-attributed; Michael is never named as the autonomous actor.
- **Visible community:** the owner/admin Live Operations runtime panel polls every two seconds while running and shows persisted simulated time, exact cursor/progress, on-shift departmental coverage, canonical ticket counts, recent exact-run tickets, and recent task transition receipts. Failed reads remain unknown rather than false zeroes, and tickets open into the existing canonical request-detail UI.
- **Observable ticket lifecycle:** every resident routine now produces three deterministic canonical StaffTask phases: OPEN at T, CLAIM/START at T+5 simulated minutes, and COMPLETE at T+15. At the default 60x speed this is about five real seconds pending and ten real seconds in progress, longer than the UI polling interval. OPEN is attributed to the synthetic resident; later phases independently select an on-shift departmental worker, including truthful shift-boundary handoff. Medication remains reminder-only.
- **Plan fingerprint:** `living-community-timeline-v2-ticket-dwell`, 51,570 events (41,310 ticket phases plus 10,260 shift milestones), SHA-256 `c6984f5f1ec38a84a87d110336813ba5f7c0635715d38a13bd4bcf18427ffeb6`.
- **Reset truth:** reset receipts now have deterministic Mongo identities; retry/replay cannot silently duplicate logical evidence; confirmed abort is distinct from unknown commit outcome; an ambiguous commit must reconcile exact receipts and empty exact-scope state before success is claimed.
- **Guarded controls foundation:** injection-only service composition supports create-PAUSED, readiness preflight, resume/start loop, graceful pause, stop, and guarded one-event step. No mutation route, startup hook, live database connection, feature enablement, deployment, provider call, or simulator run was performed.
- **Verification:** local integrated slices include 335 broad simulator/safety tests passed for staged execution, 290 community tests passed before staging, 106 focused timeline/executor/runner/reconciliation tests passed after staging, 41 reset/runtime/lifecycle/view tests passed after reset hardening, seven runtime frontend tests passed, and the production frontend build compiled. Direct MongoDB and browser runtime acceptance are not yet claimed.
- **Proven blocker:** repository evidence does not establish whether the EliteDesk MongoDB supports multi-document transactions. Lifecycle and atomic reset must remain disabled until a read-only topology/transaction probe and isolated scratch-database acceptance pass. The currently mounted new route is GET-only runtime truth.
- **Next safe action:** finish bounded per-tick recovery for the 51,570-event plan, then integrate a default-off transaction-gated control API/UI and atomic run-bound resident provisioning. Do not enable, deploy, restart services, or mutate live data before direct database and browser acceptance plus exact-SHA owner authorization.
- **Michael must do:** NOTHING during this isolated build slice.

## 2026-10-13 — Living-community bounded runner recovery (isolated lane)

HANDOFF CAPSULE
- Objective: Keep the 51,570-event unattended runner viable at 60x by making every tick cursor-local while preserving crash recovery and receipt safety.
- Branch: `lane/community-runner-bounded`
- Lane / ownership: Runner hot path, durable timeline read adapter, one-event execution seam, and focused tests only; no route, startup hook, provider, database default, deployment, or live mutation.
- Last proven state: 105 focused runner/timeline/executor/loop/runtime-acceptance/reconciliation tests pass. A 51,570-event non-iterable-plan test proves a tick uses indexed cursor reads and never invokes full event/receipt loaders. A 1,000-tick fake-store benchmark measured 0.158 ms/tick for a 51,570-event contract versus 0.154 ms/tick for one event (1.029x; storage latency excluded).
- Commits: recorded in the branch commit that contains this capsule.
- Runtime state: No server, simulator loop, database, provider, service, or deployment was started.
- Unresolved proven defects: none in the bounded recovery lane; direct Mongo acceptance remains an integration gate.
- Product invariants that matter here: exact plan fingerprint and cursor; prior/current/future-gap evidence is bounded and provenance-validated; a terminal crash receipt advances without re-execution; duplicates, nonterminal evidence, wrong scope/community, cursor/event mismatch, and future-gap receipts fail closed; paused/stopped and fenced-lease behavior is preserved.
- Do NOT change: Do not replace the exact receipt queries with a run-wide scan, bypass last-evidence validation, auto-start the loop, select a live database, mount a route, or enable providers from this lane.
- Next safe action: Review and integrate this commit, then run the complete in-memory suite and direct-Mongo acceptance from the coordinator branch before any guarded control-route activation.

## 2026-10-13 — Living-community direct-Mongo acceptance tool (isolated lane)

HANDOFF CAPSULE
- Objective: Safely classify Mongo topology, prove a real read-only transaction/abort, and run the remaining provision/execute/pause/reconnect/resume/reset acceptance only in an explicitly confirmed disposable database.
- Branch: `lane/mongo-acceptance-tool`
- Lane / ownership: Operator CLI, safety/probe modules, fake-backed tests, and runbook only; no route, startup hook, provider, deployment, SSH, or live database access.
- Last proven state: 68 focused acceptance/lifecycle/provisioning/runner/reset/control tests pass (including five new fake-backed tool tests); Python compilation and whitespace checks pass. An omitted confirmation stops before database import/use, exits nonzero, and does not expose a deliberately credential-bearing test URI.
- Commits: recorded in the branch commit that contains this capsule.
- Runtime state: No MongoDB, SSH host, server, provider, simulator loop, or deployment was contacted or changed.
- Unresolved proven defects: The tool has not yet been run against a real replica set/sharded MongoDB; its output will be the direct-database evidence. It does not prove an EliteDesk service restart or browser acceptance.
- Product invariants that matter here: read-only by default; explicit disposable name plus confirmation for writes; exact scratch database binding before/reopen; all mutations use receipt-backed canonical services; credentials and raw connection errors are never printed.
- Do NOT change: Do not relax the scratch prefix/empty-database/production-name guards, add database deletion, default a mutation mode, auto-run it, or point it at the shared `caoscare` database.
- Next safe action: Review and integrate this commit, then run the read-only command on EliteDesk; only after that passes, run a separately named pristine scratch acceptance with explicit owner authorization.

## 2026-10-13 — Fresh lease revalidation before simulator cursor commit

HANDOFF CAPSULE
- Objective: Prevent an executor from advancing the durable community cursor after its lease expires or another holder takes ownership during canonical event work or crash-receipt recovery.
- Branch: `fix/community-runner-lease-revalidation`
- Lane / ownership: Shared cursor-commit lease guard, bounded runner/step, legacy executor compatibility, loop/control/startup clock injection, focused tests, and historical requisition note only; no routes, live database, provider, deployment, or runtime mutation.
- Last proven state: 86 focused executor/lease/runner/loop/startup tests passed; a broader 127-test executor/adapter/runner/timeline/loop/control/startup/runtime-acceptance set passed; Python compilation and repository whitespace checks passed. Expiry during service work and prior-receipt recovery leaves cursor and last-evidence metadata unchanged.
- Commits: recorded in the branch commit containing this capsule.
- Runtime state: No server, simulator loop, database, provider, service, or deployment was started.
- Unresolved proven defects: Direct Mongo concurrency acceptance remains an integration gate; no new defect was found in this bounded fix.
- Product invariants that matter here: one exact fenced owner; fresh timezone-aware lease proof after durable evidence reload and before cursor CAS; receipt-backed cursor movement only; expired/stale ownership cannot change cursor metadata.
- Do NOT change: Do not weaken exact holder/fence/TTL matching, reuse the tick-start timestamp after service work, enable routes, touch live data, call providers, or deploy from this lane.
- Next safe action: Integrate this commit onto the living-community operations branch, rerun the combined simulator suite, and keep direct-Mongo/browser acceptance gated.

## 2026-10-13 — Guarded stopped-run reset controls

- **Agent/tool used:** Codex reset-controls lane
- **Branch/ref:** `lane/community-reset-controls`, rebased onto integrated simulator head `63d2862`
- **What changed:** Added a separate default-off owner/admin reset endpoint and typed-confirmation UI for one exact stopped Living Community run. Reset now refuses an active durable execution lease, checks process-local loop ownership, binds the stable operation key to the authenticated actor and run, and preserves historical receipts, real residents, and unrelated simulator scopes.
- **What was verified:** Before integration, the 393-test community backend suite passed. After rebasing onto resident provisioning controls, 83 focused backend coexistence tests and 10 focused frontend control tests passed; the optimized frontend production build compiled successfully. Gate failures, confirmation/state mismatches, active-loop refusal, exact-run matching, idempotent retry, and the UI confirmation flow are covered.
- **What is blocked:** No live database, startup, deployment, or provider action was performed. Mutation remains unavailable unless the explicit environment flag, real transaction probe, and all six named indexes pass.
- **Next safe step:** Integrate this commit after the provisioning-controls lane, rerun the combined focused suites, and keep deployment disabled pending direct MongoDB acceptance.

HANDOFF CAPSULE
- Objective: Wire the hardened exact-scope reset into guarded owner/admin controls.
- Branch: `lane/community-reset-controls`
- Lane / ownership: Separate reset route, component, client helper, and tests; avoided the shared provisioning control files.
- Last proven state: Post-rebase backend 83/83, frontend 10/10, and the production frontend build are green; earlier full community backend suite was 393/393.
- Commits: See branch head after commit.
- Runtime state: No services started; no live database or provider touched.
- Unresolved proven defects: None in this bounded lane.
- Product invariants that matter here: Reset is manual, exact-scope, transactional, receipt-preserving, and real-data-safe.
- Do NOT change: Default-off transaction/index gate; append-only historical receipts; real/unrelated data boundaries.
- Next safe action: Cherry-pick after provisioning controls, resolve only server/Live Operations registration if needed, then rerun combined tests.

## Tuesday, October 13, 2026 — 3:09 PM America/Chicago — Running-community simulator integration checkpoint

- **Branch/ref:** `work/living-community-operations` at `bfbbd8970364f01d85555d54a19f7f018b938c08`; draft PR #146 remains isolated, unmerged, and undeployed.
- **Owner-visible outcome:** Live Operations can poll every two seconds while RUNNING and show canonical simulated tickets opening, being claimed/in progress, and completing. Each transition is tied to the exact run, resident, on-shift departmental worker, simulated time, and durable receipt. Pause freezes movement; resume continues it; restart recovery reconciles missed work without deliberately duplicating it.
- **Complete community plan:** 80 apartments, 70 occupied apartments, 75 synthetic residents, 50 stable synthetic workers, eight departments, deterministic 90-day schedules, resident-specific plans, staffing shifts, coverage gaps, and daily work in every department. Current plan fingerprint is `living-community-timeline-v3-department-activity`, 52,110 events (41,850 ticket phases plus 10,260 shift milestones), SHA-256 `35ee4c75c8f08ebb24ffe058baa1fa4095f03f4ab5e0da2aaa6062b727d70970`.
- **Department activity:** Nursing, Kitchen, Housekeeping, Activities, Administration, Transportation, Maintenance, and Front Desk all produce canonical work. Front Desk follow-up remains provider-fenced and claims neither an outbound call nor resident contact.
- **Controls and safety:** Owner/admin create, provision-ten-resident burn-in, resume, pause, stop, and exact stopped-run reset controls are default-off behind the transaction/index capability gate. Real residents, unrelated runs, historical receipts, and real providers remain isolated. Medication is reminder-only. Real admin Work-as retains Michael's authenticated identity and never impersonates a synthetic worker.
- **Runtime hardening:** bounded cursor-local reads, fenced ownership, fresh lease revalidation immediately before cursor commits, restart reconciliation, receipt-backed index preparation, atomic resident provisioning, and exact-scope reset are integrated. Startup recovery is implemented but intentionally unmounted pending direct-database acceptance and reviewed service wiring.
- **Verification:** the complete `backend/tests/test_sim_community*.py` suite passed 428/428 in 617.71 seconds; focused frontend suites passed 25/25 and 23/23; the optimized frontend production build compiled; Python compilation and repository whitespace checks pass. No live server, database, provider, deployment, or simulator run was started.
- **Remaining gates:** run the read-only Mongo topology/transaction probe; run the explicitly confirmed isolated scratch-database provision/execute/pause/reconnect/resume/stop/reset acceptance; mount the single startup/service coordinator only after those pass; deploy an exact reviewed SHA to a test environment; perform browser acceptance for CREATE, PROVISION, RESUME, live ticket movement, PAUSE, restart recovery, STOP, and RESET; then obtain owner approval before any larger 75-resident accelerated run.
- **Next safe action:** publish this exact verified tree to the isolated draft branch without force, update PR #146 and issue #129 for the tandem builder, then wait for exact-head CI. Do not merge, deploy, restart, enable controls, or touch a live database from this checkpoint.

## 2026-10-13 — Living-community browser-visible lifecycle coverage (isolated lane)

HANDOFF CAPSULE
- Objective: Prove at the Live Operations page boundary that an owner can visibly follow one canonical ticket from open to in progress to complete, pause without autonomous movement, resume, inspect provenance, and see truthful disabled controls.
- Branch: `lane/browser-acceptance-coverage`, based on published simulator commit `d90af0bd4ed23d483363a7112bc2c75647bb3bf4`.
- Lane / ownership: Deterministic frontend/browser-DOM acceptance coverage and bounded runtime-status wording only; no backend, route, deployment, database, server, provider, or live browser mutation.
- Last proven state: The page-level test drives RUNNING open → RUNNING in progress → PAUSED in progress for a ten-second poll → RUNNING in progress → RUNNING completed, verifies resident/worker/source/authority/receipt provenance, opens the canonical ticket detail seam, and verifies all controls remain disabled when the safety gate refuses mutations. Six focused suites pass (25 tests total), and the optimized production frontend build compiles.
- Commits: Recorded in the branch commit containing this capsule.
- Runtime state: No server, database, simulator, provider, deployment, authenticated account, or live browser was opened or changed.
- Unresolved proven defects: No defect in the deterministic UI contract. This is automated browser-DOM evidence, not deployed browser acceptance; exact-SHA test deployment plus real API/database operation remains required.
- Product invariants that matter here: canonical StaffTask/receipt truth; explicit simulated identity; paused autonomous work does not move; real-human actions may still appear; unavailable reads never become false zeroes; mutation controls fail closed.
- Do NOT change: Do not treat this test as proof of Mongo transactions, startup wiring, deployment, or a live three-month run.
- Next safe action: Integrate this commit, then run the remaining isolated Mongo acceptance and exact-SHA deployed browser acceptance before enabling Living Community controls.

## 2026-10-13 — Kitchen and Activities specialized Work-as slice (isolated lane)

HANDOFF CAPSULE
- Objective: Let a real owner/admin enter Kitchen or Activities through Work-as and use the existing menu or schedule workspace with explicit dual-identity receipts.
- Branch: `lane/department-workas-safe`, based on published simulator head `d90af0bd4ed23d483363a7112bc2c75647bb3bf4`.
- Lane / ownership: Kitchen menu and Activities schedule routes, their existing ingest/review endpoints, shared content-receipt authority, Department Workspace selection, and focused tests only. No Transportation, Front Desk, Nursing alert, provider, simulator runtime, database, deployment, or server changes.
- Last proven state: All 20 signed-in menu/schedule endpoints revalidate the short-lived Work-as header; wrong-department scope remains 403; receipts retain Michael's authenticated owner/admin identity and separately name the temporary staff department authority; the specialized Kitchen/Activities UI renders while Work-as is active. Nine focused backend tests and 14 focused frontend tests passed; the optimized frontend production build compiled; Python compilation and repository whitespace checks passed.
- Commits: Recorded in the branch commit containing this capsule.
- Runtime state: No server, database, provider, simulator loop, deployment, or live resident/community record was contacted or changed.
- Unresolved proven defects: Transportation still uses separate operator/coordinator dependencies and can notify a real provider path; Front Desk-wide tools do not consume Work-as provenance; Nursing alert actions are not department-scoped Work-as routes and carry care-safety implications. Those surfaces must remain on the generic canonical task queue from Work-as until separately hardened.
- Product invariants that matter here: Real identity never becomes a simulated worker; each content mutation has a durable dual-provenance receipt; department scope is revalidated on every request; only published content reaches residents/Aria.
- Do NOT change: Do not broaden Work-as globally, bypass specialized route dependencies, expose another department's content controls, send notifications, or infer clinical authority.
- Next safe action: Integrate this focused slice, then separately harden Transportation read-only calendar access before considering any ride mutation or notification path.

## 2026-10-13 — Default-off shared startup/runtime composition

HANDOFF CAPSULE
- Objective: Mount living-community restart recovery without creating a second loop manager or allowing disabled startup to touch simulator storage.
- Branch: `audit/startup-wiring` from published simulator commit `d90af0bd4ed23d483363a7112bc2c75647bb3bf4`.
- Lane / ownership: Application lifespan, process-local control/loop registry, startup capability short-circuit, graceful loop shutdown, and focused tests only.
- Last proven state: the complete simulator suite passes 435/435 in 729.22 seconds; the focused startup/loop/control/reset/API slice passes 52/52; Python compilation and whitespace checks pass. HTTP controls and startup recovery use one exact service/manager. Startup defaults off; startup-enabled/controls-disabled performs no composition or capability/storage probe. Both explicit flags still require the existing real read-only transaction and six-index proof before recovery can load or mutate a run.
- Commits: recorded in the branch commit containing this capsule.
- Runtime state: No server, database, simulator, provider, SSH target, deployment, or service restart was touched.
- Unresolved proven defects: Direct Mongo scratch acceptance and real server/browser restart acceptance remain required before either feature flag is enabled.
- Product invariants that matter here: one process registry; durable cross-process fenced lease; exact-run receipts; no simulator storage access while startup or controls are disabled; graceful cancellation on server shutdown.
- Do NOT change: Keep both flags default-off; do not replace the transaction/index proof, silently create indexes, enable a provider, or treat process-local ownership as cross-process exclusivity.
- Next safe action: Review/cherry-pick this bounded commit, rerun the complete simulator suite, then exercise it only in the explicitly confirmed isolated Mongo scratch acceptance before test deployment.

## 2026-10-13 — Durable owner/admin manual STEP (isolated lane)

HANDOFF CAPSULE
- Objective: Enable one owner/admin STEP without allowing another process or autonomous loop to execute concurrently.
- Branch: `lane/community-step-exclusivity`, based exactly on published simulator commit `d90af0bd4ed23d483363a7112bc2c75647bb3bf4`.
- Lane / ownership: Manual STEP lease mode, receipt-backed orchestration, guarded API/UI enablement, and focused tests only; no startup hook, database selection, provider, deployment, or live mutation.
- Last proven state: 148 impacted backend tests and 11 focused frontend tests pass; the optimized frontend production build compiles. STEP uses the canonical run document's atomic execution lease with exact holder, monotonically increasing fence, TTL, PAUSED state, cursor, clock, scope, and manual mode. The run remains PAUSED while one canonical event is reconciled/executed and cursor-committed.
- Commits: Recorded at this lane's committed head.
- Runtime state: No server, database, provider, simulator loop, SSH session, service, or deployment was contacted or changed.
- Unresolved proven defects: Direct Mongo concurrency acceptance remains an integration gate; fake-backed tests prove query/CAS semantics but are not topology evidence.
- Product invariants that matter here: default-off transaction/index capability gate; no action without receipt/provenance; one exact fenced owner; stale/expired ownership cannot advance the cursor; manual STEP cannot leave the community autonomously RUNNING.
- Do NOT change: Do not make STEP bypass resident readiness, transaction/index gates, exact PAUSED coordinates, lease mode/holder/fence/TTL checks, or provider fences.
- Next safe action: Integrate after current startup-control changes, resolve only route/capability overlap, rerun combined simulator tests, then include STEP in isolated direct-Mongo and browser acceptance before enabling controls.

## Tuesday, October 13, 2026 — 4:08 PM America/Chicago — Running-community controls integrated and green

- **Integrated outcome:** Live Operations has deterministic page-level proof of canonical ticket movement from OPEN to IN PROGRESS to COMPLETED, including pause freeze, resume, provenance, receipt evidence, and canonical ticket drill-in. Owner/admin STEP now executes one exact event while the run remains PAUSED under a durable `manual_step` lease. Startup recovery and HTTP controls share one process runtime and loop manager.
- **Work-as expansion:** Kitchen Menu and Activities Schedule are available through Work-as with the real authenticated owner/admin identity and separately signed acting department authority on every supporting request and receipt. Transportation mutation/notification, Front Desk-wide communication, and Nursing alert surfaces remain intentionally gated.
- **Default-off runtime:** startup performs no simulator composition or storage probe unless both `CAOSCARE_LIVING_COMMUNITY_STARTUP_RECOVERY=true` and `CAOSCARE_LIVING_COMMUNITY_CONTROLS=true`. Transaction and six-index proof remain mandatory. Shutdown cancels loops owned by the shared manager.
- **Manual STEP proof:** atomic lease acquisition matches exact run/scope/PAUSED/cursor/minute and absent-or-expired lease; every heartbeat, lifecycle write, event execution, and cursor commit requires exact holder/fence/TTL/mode. Human request/completion receipts link to canonical event evidence. The run is never temporarily exposed as autonomously RUNNING.
- **Combined verification:** complete `backend/tests/test_sim_community*.py` suite 437/437 in 599.14 seconds; combined frontend page/control/workspace slice 19/19; optimized frontend production build compiled; Python compilation, whitespace checks, and modified production file-size checks passed.
- **Runtime state:** no live database, provider, service, SSH session, deployment, service restart, or simulator run was contacted or changed.
- **Remaining activation gates:** read-only target-Mongo topology/transaction proof; explicitly confirmed disposable scratch-Mongo acceptance including concurrent STEP, provision, run, pause, reconnect, resume, stop, and reset; exact-SHA test deployment; real browser acceptance; owner review of ten-resident burn-in; owner authorization before merge or any live enablement.
- **Next safe action:** publish this exact green tree to draft PR #146, update tandem-builder coordination on #129, verify exact-head CI, and keep all controls disabled until the environment gates pass.

## Tuesday, October 13, 2026 — 11:40 PM America/Chicago — SIM-003 real-MongoDB acceptance PASSED (four defects fixed)

- **Agent/tool:** Claude Code session caoscare-1-64 at Michael's instruction (SIM-003). **Branch:** `fix/sim-003-mongo-truthiness` from PR #146 head `7b1af81a8e945927c88476593e314a5faadedd90`; worktree `/home/caoscare-1/CAOSCARE-SIM003`. PR #146 branch itself not modified.
- **Defects found only against real MongoDB (EliteDesk replica set `rs0`, see SIM-002) and fixed:**
  1. `store or _default_store()` at 8 sites (provisioning, cleanup, reset, department preflight, run lease ×4) → `NotImplementedError` (pymongo Database refuses `bool()`). Now explicit `is not None`.
  2. Scratch acceptance never seeded the department catalog → `Unsupported request category: nursing`. Harness now runs the server's own `seed_default_departments` (CLI `seed_catalog`) then `preflight_living_community_run_start` before any mutation.
  3. Acceptance ticks used the run's frozen start time while the cursor commit revalidates the lease with live time → `lease heartbeat refused`. Ticks now share one clock with the lease revalidation (live in real runs, frozen only when a test injects `now`).
  4. `PersistedRunClock` anchored on `updated_at`, which every lease acquire/heartbeat/release refreshes → simulated clock froze while the real loop polled (90 "future" ticks, 0 events). New `sim_clock_at` written only where `sim_minute` is set (create + lifecycle `_mutate`); clock reads it, falling back to `updated_at` for older rows.
- **Regression tests:** test fake stores now reject `bool()` like pymongo (55 tests fail without fix 1, 65/65 pass with it); department preflight before mutation; clock anchor test fails before / passes after fix 4.
- **Gates:** living-community suite (`test_sim_community*`, `test_living_community_*`, haiku/family boundaries) **494 passed / 0 failed**. Full backend gate: 1150 passed / 21 failed / 31 skipped; all 21 also fail on unmodified `7b1af81` (legacy SIM-1/3/4, demo continuity, SC-16/17 "Unknown simulation run", one realtime tool count) — pre-existing, not introduced.
- **Real MongoDB acceptance:** shipped tool `check_community_mongo_acceptance.py` PASSED in `caoscare_sim_acceptance_sim003e20261013`. Extended two-process check through `CommunityProcessRuntime` in `caoscare_sim_acceptance_sim003z20261013`: six indexes + receipts; run created; 10 residents provisioned; concurrent STEP (one wins, one refused by fenced lease, cursor 0→1, stays PAUSED); RESUME with real loop; ticket `task_a6dd21b8a5cd` pending → in_progress (`sim:staff:nursing:care_aide:13`) → completed in 16.8 s with chained receipts; SIGKILL while RUNNING; new process startup recovery `started`, reconcile `executed`, cursor 15→30, 0 duplicate event receipts; PAUSE froze cursor/clock/tasks 10 s; STOP; run-scoped RESET left 0 mutable rows, 117 receipts preserved, unrelated sentinel resident and departments kept. Live `caoscare` unchanged (37 residents, 1 facility).
- **Not done / blocked:** the executable 90-day plan covers only the 10 burn-in residents; provisioning, readiness, cleanup and atomic provisioning require exactly 10. A 75-resident run needs a 75-resident executable plan and provisioning, plus the known staffing-coverage decision. Nothing deployed; no flag enabled on the live backend.
- **Next safe step:** integrate this branch into PR #146 (owner of PR #146: session `caoscare-integration-b2`), rerun CI, then build the 75-resident executable plan/provisioning slice.

## Wednesday, October 14, 2026 — SIM-005A realistic community staffing (owner direction)

- **Agent/tool:** Claude Code session caoscare-1-64 at Michael's instruction. **Branch:** `feature/sim-005a-staffing` from PR #146 head `4f17fed`; worktree `/home/caoscare-1/CAOSCARE-SIM005A`. Lane notice: issue #129.
- **Owner direction (Michael, 2026-10-13):** 80-apartment, budget-constrained assisted living; keep the 50 stable employees; overnight 2–3 care staff on site; maintenance normal hours plus after-hours ON CALL (never on site 24 h); other departments realistic hours; show ON DUTY / OFF DUTY / CLOSED / ON CALL / UNCOVERED truthfully; never claim an off-site worker is present.
- **Model (`community_staffing.py`):** Nursing 24 h (day 4 aides + RN + med tech; evening 3 aides + RN + med tech; **night 3 care aides on site, RN on call**). Maintenance on site 07:00–15:30, **on call 15:30–07:00**. Kitchen 05:30–20:00, Housekeeping 08:00–16:30, Transportation 07:30–17:30, Activities 09:00–20:00, Front Desk 07:00–23:00, Administration 08:00–17:00; closed otherwise. 27 on-site shifts + 2 on-call duties per day; same 50 workers.
- **Status (`community_coverage.py`, new):** department `on_duty` / `on_call` / `closed` / `uncovered` (uncovered only when it should be staffed and nobody is); worker `on_duty` / `on_call` / `off_duty` (`worker_statuses`). On-call workers never clock in, never appear as present, and have no shift milestones; their attendance state is `on_call`.
- **Shift events:** coverage observations are now truthful status changes (`department_status_changed`, plus `coverage_gap_*` only for UNCOVERED); handoffs name incoming on-site staff, else the on-call worker, else the department closes.
- **Defect found and fixed:** `community_shift_execution` accepted only `day|evening|night` shift names, so the live executor would have refused the new `early/late/business` shifts. Executable names now come from the staffing table (`ON_SITE_SHIFTS`); on-call duty is never executable.
- **Plan:** `living-community-timeline-v4-realistic-staffing`, 49,140 events (41,850 ticket phases unchanged + 7,290 shift milestones), SHA-256 `6eb13c98d0d550061bb8f45a1116c7cb1a029a74831b46cf5ecc90caec6c6a4c`.
- **UI:** Live Operations shows each department's status, on-site/on-call counts and hours; closed/on-call are no longer shown as gaps; the planning overview shows operating hours and after-hours on-call.
- **Verified:** rota over 90 days: all 50 workers used, 0 UNCOVERED windows, 2–3 (exactly 3) care staff on site every overnight minute, maintenance never on site after hours with exactly one on-call, ≥24 h between any worker's duties, ≤6 duties per rolling 7 days. Living-community backend suite **501 passed / 0 failed**; frontend 111 suites / 731 tests; production build compiled. Real MongoDB (scratch `caoscare_sim_acceptance_sim005a20261014` shipped acceptance passed; `…sim005b20261014` real loop at 600×: 43 events, 0 errors, night handoffs/clock-outs, kitchen `early` and 06:00 day clock-ins receipted, 0 on-call milestones, reset clean).
- **Not changed:** resident provisioning (still 10), no deployment, no live data, Room 214 untouched.
- **Next (SIM-005B):** 75-resident executable timeline + provisioning; see the #129 receipt for the file list and the open owner questions.

### 2026-10-14 correction (Michael): med techs work 7-7
Med techs now work 12-hour shifts 07:00–19:00 and 19:00–07:00 (one always on site); night care is 2 care aides + the night med tech = 3 on site (2–3 rule kept). This supersedes the 8-hour med-tech rows above and answers SIM-005B question (a): evening reminders after 19:00 fall in the night med tech's shift. Plan `living-community-timeline-v5-med-tech-7-to-7`, 48,870 events (41,850 ticket phases + 7,020 shift milestones), SHA-256 `f1ac6b54904d1ede8f017ffce7200ff892fbc29c3052baf0bebf1b443172bc58`. Living-community suite 502/0; frontend 111/731. Real MongoDB loop (scratch `caoscare_sim_acceptance_sim005c20261014`, 600×): 79 events, 0 errors, `med_tech_night` handoff/clock-out and `med_tech_day` clock-in receipted, 0 on-call milestones, reset clean.

## Wednesday, October 14, 2026 — SIM-005B: all 75 residents executable

- **Agent/tool:** Claude Code session caoscare-1-64 at Michael's instruction. **Branch:** `feature/sim-005b-75-residents` from PR #146 head `6c1286b`; worktree `/home/caoscare-1/CAOSCARE-SIM005B`. Lane notice: #129.
- **Cohorts (`community_cohort.py`):** `community_75` (runtime default) and `burn_in_10` (optional test configuration). The plan revision names the cohort (`living-community-timeline-v6-community_75` / `-burn_in_10`), so a run's persisted fingerprint decides which residents are provisioned, checked, executed and observed. Selected with `CAOSCARE_LIVING_COMMUNITY_COHORT` or the acceptance CLI's `--cohort`. Unit tests pin the burn-in through `tests/conftest.py`; `test_sim_community_cohort.py` proves the full default.
- **Removed the hard-coded ten** from provisioning, atomic provisioning, readiness view, run lifecycle (`cohort` + `resident_count` on the run), control-service readiness/start guard, cleanup, observed state, runtime view and planning overview. Reset was already scope-based.
- **Routines:** the existing daily recipes now run for all 75 residents; optional routines repeat every ten residents (so the burn-in day is identical to residents 1–10 of the full day).
- **Family-call routing (`community_family_call_routing.py`, owner rule):** Administration until 17:00 when it can finish before closing; Front Desk 17:00–23:00 (and late-afternoon calls Administration cannot finish); otherwise queued for the next staffed period; urgent → on-duty care team. Coordination only, never claims a call.
- **Defects found and fixed:**
  1. Dispatch only checked staffing at a ticket's open time, so a 15:15 maintenance check would be completed after Maintenance closed at 15:30 ("ticket phase has no on-shift actor"). A ticket is now dispatched only when its department is staffed through open, claim and completion.
  2. Double-occupancy rooms (residents 066–075, five shared rooms) were classified as identity collisions by observed state and by provisioning's collision check, so a 75-resident run could never pass the start guard and a re-provision/cleanup would refuse. Blueprint room-mates (`is_room_mate`) are no longer collisions; a stranger in the room still is.
  3. Worker capacity: each ticket phase went to the alphabetically first on-site worker (one aide held up to 15 tickets at once at 75 residents; only 29/50 workers used). New `community_ticket_assignment.py` gives each ticket to the least-loaded on-site worker and lets the claimer complete it while on shift (46/50 used; worst simultaneous load 10).
- **Performance:** rota cached per day; plan built and digested once per cohort per process; `validate_timeline` no longer rebuilds. Plans: burn-in 48,870 events (3.6 s); full 321,030 events (314,010 ticket phases + 7,020 shift milestones), build ≈28 s, validation 0.3 s, ≈805 MB peak RSS. Living-community suite time fell from ≈12.5 min to ≈1 min.
- **Selectable speed:** `CAOSCARE_LIVING_COMMUNITY_SPEED` ∈ {1, 10, 60 (default), 600}; speed changes the simulated clock only — every event and receipt still executes.
- **Verified:** living-community suite **510 passed / 0 failed**; simulator frontend 27/27. Real MongoDB: shipped acceptance with 75 residents PASSED (`caoscare_sim_acceptance_sim005b75a20261014`) and with `--cohort burn_in_10` PASSED (`…sim005b10a20261014`); two-process 75-resident check (`…sim005b75y20261014`): 75 provisioned, concurrent STEP one-wins, live ticket lifecycle with chained receipts, SIGKILL + startup recovery (cursor 15→85), PAUSE freeze, STOP, run-scoped RESET (296 receipts kept, sentinel kept), 86 events = 86 receipts, 0 duplicates. Live `caoscare` unchanged (37 residents, 1 facility).
- **Throughput (EliteDesk, real MongoDB, 75 residents):** 3.29 events/s sustained (≈0.3 s per fully receipted, transactional event), 0 errors. Demand: mean 2.48 and peak 17 events per simulated minute. 90-day estimate: 60× ≈ 36 h (keeps up on average; lags then catches up at peak minutes), 600× ≈ 27 h (throughput-bound), 10× 9 days, 1× 90 days.
- **Remaining:** true worker capacity (one ticket per worker at a time, so tickets wait instead of overlapping); per-event latency (~0.3 s) bounds 600×; routines are not yet driven by each resident's care-plan preferences (e.g. shower days).
- **Next bounded task:** worker-capacity simulation — claim when a worker is free, record waiting time, and keep receipts truthful.

## Wednesday, October 14, 2026 — SIM-006: real worker capacity and visible queues

- **Agent/tool:** Claude Code (Opus 5.5) at Michael's instruction. **Branch:** `feature/sim-006-worker-capacity` from PR #146 head `e344179`; worktree `/home/caoscare-1/CAOSCARE-SIM006`. Coordination: #129.
- **Capacity model (`community_capacity_schedule.py`, `community_day_queue.py`):** every ticket of the 90-day plan is claimed only by a free on-site worker of its department whose shift covers the whole job; one active ticket per worker; excess waits in the canonical queue in deterministic order (priority, request time, id). The claim records the original request minute, the actual wait and why: `waiting_for_available_staff`, `waiting_for_department_opening`, `waiting_for_on_site_staff_on_call_only` (maintenance after hours), or `still_waiting_at_simulation_end` (no claim/complete is invented past day 90). Work never runs after a worker leaves, so no ticket is silently finished after a shift ends. The 50 workers and shifts are unchanged. Superseded `community_ticket_assignment.py` (least-loaded) and the fixed-offset `plan_ticket_phases` were retired.
- **Hands-on minutes (`community_ticket_plan.ROUTINE_WORK_MINUTES`) are labelled simulation assumptions**, not facility data: room checks and reminders 3, plated meal service 3 per resident, toileting/transfer 8, shower 20, everything else 10. Under the old uniform 10 minutes the 75-resident demand exceeded capacity (kitchen 234%, nursing 100%) and the backlog grew without bound (12,025 tickets unclaimed by day 90). Now queues build at peaks and drain daily: 104,640 tickets, longest wait 1,113 simulated minutes (late requests waiting overnight for opening), 105 still waiting at day 90 and shown as such.
- **Persisted enforcement:** new required index `living_tasks_one_active_per_worker` (partial unique on `staff_tasks` (`simulation_run_id`, `assigned_to`) where `status=in_progress`, simulated, living scope) in the shared index contract, inspection and receipted preparation; plus a pre-claim check in the execution adapter. Both fail closed with no receipt and no cursor advance.
- **Live Operations:** `community_queue_view.py` (in `GET /api/simulator/community/runtime`) and `SimCommunityQueue.jsx`: waiting tickets with simulated wait and overdue flag (>60 min, a display threshold), backlog/longest wait per department with ON DUTY/ON CALL/CLOSED status, busy/free on-site workers with ticket drill-in, broken-rule anomalies, and executor lag behind the clock (the queue is shown as of the last executed moment, so lag is never shown as resident waiting).
- **Defects found and fixed (three were pre-existing and halted every 75-resident run; earlier runs never got that far):**
  1. The runner treated any event carrying `blocked_capability` (medication reminders, activities, family calls, transport and front-desk follow-ups — capabilities the ticket deliberately does not invoke) as a blocked event, so every run stopped forever at day 0, 07:50. Now only an event whose own adapter is blocked is refused; the runtime view labels it the same way.
  2. Within one minute, a worker's next claim could sort before the completion that frees them; the persisted guard refused it (61 fail-closed retries, no receipt). Completions now order first within a minute (one shared `event_sort_key`).
  3. The canonical request service merged a new scheduled routine into an earlier one still open for the same resident and department (yesterday's night check still in progress at 00:30 absorbed today's overnight check). The run stopped at day 1, 00:30, and each retry wrote a re-request receipt (3,683 on the overnight scratch DB, kept as evidence). In-process simulator requests now deduplicate only within the same scheduled event; real resident requests are unchanged.
- **Verified:** living-community suite (`test_sim_community_*`, `test_living_community_*`, haiku boundary) **522 passed / 0 failed**; frontend **112 suites / 735 tests passed**, production build OK. `test_sim1/sim3/sim4/test_sim_provenance` have 17 failures identical on base `e344179` (fixture "Unknown simulation run", not touched here).
- **Real MongoDB (new scratch DBs, 75 residents, 8 departments, 80 apartments):** shipped acceptance PASSED (`caoscare_sim_acceptance_sim006a20261014`: 320,730-event plan, restart → PAUSED, STOP, reset kept 91 receipts). Two-process (`…sim006b20261014`): 7 required indexes ready, concurrent STEP one wins, live open→claim→complete by one aide, SIGKILL + startup recovery (cursor 8→66), PAUSE freeze, STOP, run-scoped RESET (250 receipts and sentinel kept), 0 duplicate receipts.
- **60× benchmark (`…sim006bench60z`, 15 real minutes, 00:00→13:12 simulated incl. the morning peak):** 1,616 events, 0 errors, at most 13 events behind the clock; peak queue 56, longest wait 91 min (kitchen breakfast); peak active tickets per worker exactly 1 (live and reconstructed from receipts); 1,617 executor receipts = 1,617 events, 0 duplicates; canonical starts/completions = claim/complete receipts; every claim's wait fields match the plan; a direct second in-progress insert for one worker was refused by MongoDB; pause froze; reset left 0 run tasks and kept 4,086 receipts and an unrelated sentinel. Production `caoscare` unchanged (37 residents, no living runs, no conflicting rows for the new index).
- **60× verdict:** sustainable for the measured window (peak demand 20 events/simulated minute was absorbed with ≤13 events of lag). Not yet proven for a whole 90-day run: lunch/dinner peaks after 13:12 and multi-day drift were not measured; the simulated clock advanced ≈0.88× nominal while ticks executed. Executor throughput ≈1.8 events/s here.
- **Blockers / remaining:** full-length run evidence (an overnight 60× run on `caoscare_sim_acceptance_live20261014b` started 2026-10-14 10:55 CDT); a refused event that reaches the canonical request service before validation can still mutate state on retry (now closed for dedup, not generically); `community_dispatch`/`community_outcomes` planning preview still uses fixed offsets (labelled planned-only); care-plan preference scheduling not started (out of scope).
- **Next safe step:** watch the overnight run through day 1+, then merge into `feature/living-community-simulator`.

### 2026-10-14 addendum (Michael): real staff fill in shifts in the running community

- **Direction:** "the whole idea is for me to sign in as one of the staff in every department… I'm just filling in a shift."
- **Cover shift** (`simulation/community_shift_cover.py`, `POST /api/simulator/community/shift-cover` and `/end`, owner/admin): pick an on-site simulated worker in Live Operations → *Cover shift*. While covered, that worker's planned claims and completions are `cancelled` executor receipts ("…is covering the shift; the ticket stays in the queue for them"), and the tickets wait in the department queue for the person covering, who works them through the existing **Work as <department>** workspace. *End cover* hands the worker back. Start and end are receipted with the real person as actor (receipt law: the record says who really did the work). Cover records are kept by run reset, like receipts, as audit evidence.
- **Per-ticket takeover** (`simulation/community_human_handoff.py`): any real-human state change on a simulated ticket (not a note) makes the simulated worker yield the remaining phases with `cancelled` receipts; a planned completion whose claim was given up records "never claimed; still waiting" instead of halting the run.
- **Verified:** living-community suite **530 passed / 0 failed**; frontend **738 passed**. Real MongoDB: takeover proof (`…sim006takeover1`: Michael-as-operator started a ticket, the aide's claim and completion yielded, Michael completed it, run continued with 0 errors) and cover proof (`…sim006cover1`: Care Aide 14 covered from 00:20, 9 phases yielded, 5 tickets left in the queue, one worked to completion by the real person, cover ended 01:01, run continued 41→68 with 0 errors).
- **Still needed to use it on the overnight stack:** a sign-in for Michael in that scratch DB (the repo's `scripts/bootstrap_owner.py`, run by Michael so the password is never seen by an agent).

## Wednesday, October 14, 2026 — SIM-007A: new Live Operations dashboard (issue #155)

- **Agent/tool:** Claude Code (Opus 5.5) at Michael's instruction. **Branch:** `feature/sim-007a-live-dashboard` from `feature/living-community-simulator` @ `261dfa8`; worktree `/home/caoscare-1/CAOSCARE-SIM007A`. Task #155, coordination #129.
- **What changed:** Live Operations now opens on a management dashboard for the running 75-resident community (`frontend/src/components/dashboard/`): simulated day/time, run state, measured pace, executor lag stated plainly, counts (staff on duty, residents, waiting, in progress, completed, overdue, on call), eight clickable department boxes, Staff and Residents lists. Drill-in: department (on duty / on call / off duty with shifts incl. overnight carry-over, today's shifts, Overdue / Waiting / In progress / Completed today, Upcoming = planned only), worker (position, shift today/tomorrow, availability, current ticket, next planned work, completed history, Cover shift), resident (profile, today's care, waiting/in progress/completed requests, link to the resident page), ticket (what, requested by, simulated request/start/finish times, wait and work duration labelled simulated or real-staff, outcome or reason unfinished, every receipt, action history, and the existing ticket-actions dialog). All previous panels (plan preview, observed records, run controls, reset, raw runtime and queue, legacy demo-room simulator) moved unchanged into a collapsed **Engineering details** section.
- **Backend (read-only, owner/admin):** `GET /api/simulator/community/dashboard`, `/departments/{slug}`, `/workers/{id}`, `/residents/{id}`, `/tickets/{id}` (`routes/community_dashboard.py`; `simulation/community_dashboard_{common,view,detail}.py`, `community_ticket_view.py`). Truth rules: counts are exact canonical reads; staffing/upcoming come from the rota and plan and are labelled planned; simulated phase times only from executor receipts that executed; real-staff work shows real timestamps; everything is shown as of the last executed event.
- **Fixed labels:** "75 of 10 burn-in target" → "Residents in this plan · Full community"; "Summary unavailable" → the task's own description (the queue view read a field tasks never had); no fake speed control — measured pace only (the run does not record its configured speed; SIM-007B).
- **Verified:** living-community backend **540 passed / 0 failed**; frontend **113 suites / 743 tests**; production build compiled. Browser (Michael's signed-in Chrome, `http://localhost:3006`, SIM-007A build against the running community `simrun:living:68d9abcc9c60b096a6c1`): all eight department boxes opened their own view; worker (Med Tech 03: busy, night shift Day 6 19:00–07:00, 337 completed); completed ticket (requested 02:06, waited 26 min for staff, 02:32→02:35, 3 min simulated work, 6 chained receipts); resident 049; waiting ticket (Resident 036) that moved to In progress with Care Aide 11 while being watched; the existing ticket-actions dialog opened (no action taken); 390 px layout without horizontal overflow (rendered in a same-origin 390 px frame because the window manager refused a resize). Screenshots: `docs/reports/2026-10-14-sim007a-screens/` (one with an email address deliberately excluded).
- **Defects found in browser and fixed:** overnight shifts started the day before showed "Not scheduled today"; "planned today" lists included tomorrow.
- **Incident:** a broad `pkill -f "craco start"` while switching the test stack also stopped the shared dev frontend `caoscare-frontend-dev.service` (:3000); systemd restarted it within a minute (NRestarts=1, 13:43:19 CDT, verified 200). Processes are now stopped only by exact PID.
- **Test environment:** view backend `127.0.0.1:8096` and static frontend `127.0.0.1:3006` run SIM-007A against `caoscare_sim_acceptance_live20261014b`; controls and startup recovery off; the executor (`resume_run.py`, code `261dfa8`) untouched.
- **Finding for SIM-007B:** the running community's executor is ~11–15 simulated hours behind its 60× clock on day 7 (measured pace ~47–54× while tickets accumulate); a ticket's canonical receipts lookup has no `related_object_id` index yet.

## Wednesday, October 14, 2026 — #168: every task tells its simulated clock and next step

- **Agent/tool:** Claude Code (Opus 5.5) worker. **Branch:** `co008/task-detail` from `feature/co008-request-sources` @ `d466ca9`.
- **What changed:** `GET /api/tasks/{id}/detail` now returns `origin` (kind + label, `routes.task_origin.kind_of`) for every task and a read-only `simulation` block for a living-community ticket (`simulation_run_id` + `simulator:event:` session): simulated request time (executor OPEN receipt's `requested_at_minute`, else the run's plan), simulated start/finish only from executed CLAIM/COMPLETE receipts, wait reason and recorded wait (CLAIM receipt queue fields), expected work minutes (`community_ticket_plan.work_minutes(routine)`), who raised it (OPEN receipt actor), the run's executed position, and elapsed waiting/working minutes against it. A missing run is stated (`run_found: false`), never guessed; real tasks get `simulation: null`. It reuses the Live Operations ticket reading (`community_ticket_view.timeline` / `executor_receipts`, now shared), so both views agree. Frontend: the queue row's expanded view and **My tasks today** (new *Details, notes and receipts* section) render the same facts via `components/TaskFacts.jsx` + `lib/taskFacts.js` (simulated time beside the real receipt time, expected, waited/working, raised by, why, next permitted step); expanded titles wrap.
- **Verified:** new `tests/test_task_detail_simulation.py` (3) + task-detail visibility + work rules through the gate; `test_sim_community_*` + `test_ops_metrics` 511 passed; frontend 118 suites / 768 tests; production build OK. Not browser-verified against a running community.
- **Next safe step:** review/merge into `feature/co008-request-sources`; check the expanded row against the running community in the browser.
## Thursday, October 15, 2026 — CO-008 plan realism: living-community plan v9

- **Agent/tool:** Claude Code (Opus 5.5) subagent. **Branch:** `co008/plan-realism` from `feature/co008-request-sources` @ `232d9a0` (isolated worktree). Fixes the 2026-10-15 staffing/capacity audit (`CAOSCARE-OPS-WORKSPACE/docs/reports/2026-10-15-co008-staffing-capacity-audit.md`).
- **What changed:** (1) one routine → eligible job-role table (`simulation/community_role_eligibility.py`): reminders med tech → RN, never care aides; hands-on care aides → med tech → RN; no qualified worker on site → the ticket waits (`waiting_for_qualified_staff`). (2) high/urgent tickets with no qualified worker on site call in the on-call worker after a response delay (maintenance 40, RN 30 simulated min, assumptions), claim receipt `called_in_on_call: true`, never two tickets at once, not present before the claim (`community_on_call.py`). (3) `wait_breakdown` minutes per blocker over the whole wait, `wait_reason` = dominant (`community_wait_blockers.py`). (4) dinner (19:30) and afternoon activity (18:00) expire unserved via a new `expire` phase: the department lead skips the canonical task through `task_actions.skip` (`community_service_windows.py`, `community_ticket_phase.py`). Durations unchanged. Plan revision `living-community-timeline-v9-plan-realism-<cohort>`; community_75 344,524 events, burn_in_10 52,873.
- **Verified:** living-community suite 579 passed / 0 failed (561 before + 18 new, one DB-direct on `caoscare_test_unit`). Before/after metrics and the duration proposal / pre-start design note: `docs/reports/2026-10-15-co008-plan-realism.md` (evening reminders med-tech share 11.6% → 63.6%, 0 to care aides; maintenance median wait 553 → 50; 0 dinners/activities served next day, 5,637 closed not served).
- **Blocked / decision:** v9 code cannot load a v8 run (one revision per cohort); the owner must stop the running v8 run (`simrun:living:f24c347040991ddde766`) and start a v9 run before deploying this to the executing process. Durations and breakfast/lunch windows await owner decision. Nothing deployed; no service restarted; no shared database touched.
- **Next safe step:** owner review; cut over to a v9 run; then the start-minute-parameterized schedule (design note) as its own slice.

## Thursday, October 15, 2026 — 01:30 CDT — CO-008 worker workflow: outcomes, escalation and task detail integrated

- **Agent/tool:** Claude Code (Opus 5.5), CAOSCare session. **Branch:** `feature/co008-request-sources` @ `5f5ae16` (pushed); v9 candidate `co008/v9-candidate` @ `be8d0cb` (pushed). Receipts: #168 comments 6185742758, 6185877020, 6185922618.
- **What changed:** merged the escalation monitor (`97c619b`) and task detail (`26c7eb0`); escalated simulated tickets count as overdue with an "Escalated · level N" badge (`58999d1`); history names a simulated escalation correctly (`f3bed01`); reassign / release / handoff are distinct receipted outcomes that require a reason, and a handoff returns in-progress work to waiting (`aa12f85`, `task_work_rules.assignment_kind`, `components/useAssignWithReason.jsx`); the assign box shows a holder who is not on the roster (`5f5ae16`). v9 candidate: plan realism merged (`bc08062`), wait-by-cause and call-in in task detail, called-in on-call workers no longer flagged as off-site anomalies (`be8d0cb`).
- **Verified:** frontend 119 suites / 774 tests; simulator suites 565 passed; assignment-related backend suites 19/19; full backend gate 1260 passed / 29 failed (27 known baseline + 2 date-bound tests: `test_housekeeping_recurrence` hard-codes 2026-10-13, `test_aria_rewake_continuity`). v9 candidate: simulator 584 passed, frontend 775, real-MongoDB shipped acceptance passed on `caoscare_sim_acceptance_co008v9a20261015` (75 residents). Chrome as the test operator (Nursing / Care Work-as) on the 1x run: escalation badges, overdue count, task detail fields, claim → start → hand off with reason → restart → complete with outcome on `task_2dd2f3b6aa62`, all receipted under the test operator.
- **Runtime:** test stack backend :8096 `aa12f85` (transient user unit `caoscare-dashboard-backend`, DB `caoscare_sim_acceptance_live20261014b`, 1x run `simrun:living:f24c347040991ddde766` resumed by startup recovery), frontend :3006 `main.3d513551.js`. Room 214 and the real `caoscare` DB untouched by CO-008 work.
- **Blocked on Michael:** v9 cutover (stop the v8 run, deploy `co008/v9-candidate`, start a v9 run at 1x); duration/staffing choices (38% dinners and 45% activity offers not served under v9 with current staffing).
- **Next safe step:** on Michael's go, cut over to v9 and verify a dinner expiry and an on-call call-in in Chrome.

## Thursday, October 15, 2026 — 02:45 CDT — CO-008 service model (plan v10), owner decision 2

- **Agent/tool:** Claude Code (Opus 5.5), CAOSCare session, no subagents (owner: none after 2 AM). **Branch:** `co008/service-model` from `co008/v9-candidate`.
- **Owner direction:** fix the dining and activities service model before adding staff; no shortened durations; realistic evening staffing; keep shortages visible.
- **What changed:** new `simulation/community_service_model.py` (one source of truth). Kitchen splits into cooks, who hold prep, plating and dish work, and dining servers, who serve in parallel; seatings span one hour; about 1 in 8 residents eats in the apartment (8 min). Activities: synthetic mobility means only escort-needing attendees (8 min) and one-to-one visits (20 min) take staff time, and independent residents attend on their own. Staffing is 57 workers / 31 on-site shifts a day (cook 3, dining server 6, activities assistant 2 added). Plan `living-community-timeline-v10-service-model`.
- **Verified:** simulator suites 602 passed; frontend 775. Dinners not served 38% → 0.1%; activity tickets not served 45% → 0. The remaining waits are classified in `docs/reports/2026-10-15-co008-service-model.md` (dinner/breakfast median 29 min = genuine shortage with 2 servers; housekeeping/front-desk waits = modelling artifacts of the daily volume).
- **Next safe step:** real-Mongo acceptance on a fresh scratch DB, then cut over the test stack from the v9 run (kept) to a v10 run at 1x and verify in Chrome.

## Thursday, October 15, 2026 — CO-008 room delivery (plan v11), owner correction

- **Agent/tool:** Claude Code (Opus 5.5), CAOSCare session, no subagents. **Branch:** `co008/room-delivery` from `co008/service-model` @ `8a7a845`; worktree `/home/caoscare-1/CAOSCARE-CO008-RD`. Product commit `58e719b`.
- **Owner direction (chat, 2026-10-15):** about 30 of 75 residents have meals delivered. Model the full delivery trip (pickup, walk, hand-off/setup, return), keep dining-room service parallel, determine the staffing needed, and show any shortage honestly. The v10 run is preserved.
- **What changed:** 30/75 residents have deliveries (deterministic, resident-specific). Each delivery is 13 min (2 + 4 + 3 + 4, labelled assumptions). New kitchen role `meal_delivery_aide` (9 people; 07:15–13:15 ×3, 16:45–19:45 ×3). Deliveries prefer aides and dining servers help; the dining room is the reverse. 66 workers / 37 on-site shifts. Plan `living-community-timeline-v11-room-delivery`. `meal_of()` no longer calls `housekeeping_room_service` a meal.
- **Results (90 days):** every meal served, 0 not served. Waits, median / p90 / max: breakfast 14/27/35, lunch 5/6/9, dinner 14/26/34. With v10 staffing and 30 deliveries, 43% of dinners are not served and breakfast waits 91 min (median). Staffing sweep and classification are in `docs/reports/2026-10-15-co008-room-delivery.md`.
- **Verified:** simulator suites 603 passed / 0 failed. Full backend gate on `58e719b`: 1,314 passed / 0 failed / 13 skipped (exit 0). Real-Mongo scratch acceptance passed on `caoscare_sim_acceptance_co008v11a20261015` (75 residents, run `simrun:living:ae98ba005787554575d9`, reset kept 91 receipts). No frontend change.
- **Not done:** runtime cutover. The #168 owner direction (comment 6200729443) says not to stop the v10 run or switch until the owner authorizes it. The v10 run `simrun:living:bcc6e54a0a4e54e7aeb8` is still RUNNING on `8a7a845`.
- **Next safe step:** owner decision on the cutover, then stop v10 (kept), load `co008/room-delivery` and start a v11 run at 1x.

## Thursday, October 15, 2026 — Staff On Duty → worker detail + owner role corrections (plan v12), first #153 slice

- **Agent/tool:** Claude Code (Opus 5.5), CAOSCare session, no subagents. **Branch:** `co008/workspace-staff-drilldown` from exact `eaa1c23` (`co008/room-delivery`); worktree `/home/caoscare-1/CAOSCARE-CO008-STAFF`. Product commit `6c55337`.
- **Owner direction (2026-10-15, #166/#153):** every Staff On Duty name opens a truthful worker detail. Role corrections: one activities coordinator and no assistant; one normal maintenance worker; two housekeepers, A Mon–Fri and B Wed–Sun; business office manager, administrator and executive director; nursing unchanged. Do not load into :8096/:3006 or create a run until this slice is advanced to runtime acceptance.
- **What changed:**
  - **Worker detail** (`simulation/community_worker_detail.py`, behind the existing admin-only `GET /api/simulator/community/dashboard/workers/{id}`):
    - simulated marker, role, shift and 7-day rota;
    - state: working / free / on call / called in / off duty / covered;
    - today's assigned and completed tickets;
    - role facts: meal service, rides, housekeeping zone, residents cared for, maintenance queue;
    - breaks and location are reported as unknown, never guessed.
  - **Staff On Duty records** (`routes/ops_widgets.py`, `RecordsDialog.jsx`) are buttons that open the worker view; `WorkerFacts.jsx` renders the new facts.
  - **Staffing:**
    - shift rows can name weekdays and a fixed person; department hours are weekday-aware (`community_coverage.OPERATING_DAYS`, Day 1 = Monday);
    - on-call maintenance alternates nights and weekends between 2 on-call technicians;
    - family calls go to the Front Desk when Administration is closed;
    - no coordinator-run activities on weekends.
  - Plan `living-community-timeline-v12-staff-roles` (community_75: 328,751 events).
- **Visible consequences (not hidden, not fixed by adding staff):**
  - Housekeeping can't keep up with a daily full clean of all 75 apartments: median wait 8.9 days, 1,584 still waiting at day 90. This is the known daily-clean artifact plus 1–2 housekeepers.
  - Maintenance: median wait 2.8 days, 145 still waiting at day 90.
  - 247 activity escorts are not served (one coordinator).
- **Verified:** simulator suites 614 passed / 0 failed (new `test_sim_community_staff_detail.py`, 9 tests). Frontend 120 suites / 777 tests (new `staffOnDutyWorker.test.jsx`). Full backend gate on `6c55337`: 1,325 passed / 0 failed / 13 skipped.
- **Not done:** browser acceptance (needs the branch loaded and a run, both held by the owner's runtime rule); real-Mongo scratch acceptance of v12.
- **Next safe step:** owner review of the role schedules and the housekeeping/maintenance shortage; on advance, load into the test stack, start a v12 run, and click Dining Server / Driver / Housekeeper / Care Aide in Chrome.

### 2026-10-15 addendum — v12 staffing finalized (owner decisions), commit `0aa2fa0`

- **Maintenance:** the two invented on-call technicians are removed. There is ONE maintenance technician: on site Mon–Fri 07:00–15:30, and the same person's after-hours and weekend on-call duty. Rest rules apply to on-site shifts only. Fixed an attendance bug where the evening on-call duty overwrote the on-site shift as the day's state. Outside vendors are not staff and are not modelled.
- **Housekeeping:** one 45-minute full clean (an assumption) per occupied apartment per week, by fixed territory (`community_housekeeping.py`).
  - SIM-001–040: 40 occupied, Mon–Fri, 8 cleans per shift.
  - SIM-041–080: 30 occupied, Wed–Sun, 6 cleans per shift. Vacant apartments get no clean.
  - Only the territory's housekeeper takes its cleans. Housekeeper and department detail show today's cleans (completed / in progress / remaining).
  - Before → after: 6,750 → 904 full cleans; 1,584 → 0 still waiting at day 90; median wait 8.9 days → 15 min for cleans and 47 min for all housekeeping.
- **File size:** static data moved to `community_staffing_data.py`; `community_staffing.py` went from 336 to 251 lines.
- **Workers:** 55, i.e. v11's 66 minus housekeeping 2, maintenance 3, activities 5 and administration 1. Kitchen v11 staffing and service model unchanged (regression test).
- **Verified:** simulator suites 620 passed / 0 failed; frontend 120 suites / 777 tests; full backend gate on `0aa2fa0` 1,331 passed / 0 failed / 13 skipped.
- **Plan:** community_75 has 314,363 events. The burn_in_10 digest is `0c777af0…faaf6`.
- **Still visible:** maintenance median wait 2.8 days and 145 jobs open at day 90 with one person; 247 activity escorts missed.
- **Not loaded:** waits for Kitchen acceptance and the owner's cutover.

### 2026-10-15 addendum — full clean is 30 minutes (owner decision, #166 comment 6203700924)

- Michael set a 30-minute full clean as an owner-approved, conservative simulation assumption; staff may take 15–20. This supersedes the 45 minutes above. Cleans are spaced 35 minutes apart. The weekly clean and the territories are unchanged, and no staff were added.
- 90 days: 904 cleans, all completed, 0 still waiting. Clean wait median / p90 / max: 10 / 55 / 90 min. All housekeeping work: 28 min / 13.9 h / 20.9 h. Last clean finishes by 14:15 (Housekeeper 01) and 13:15 (Housekeeper 02).
- Plan counts are unchanged; the burn_in_10 digest is now `035d6a30…50a3`. Simulator suites 620 passed / 0 failed. Not loaded.

## 2026-10-15 16:10 CDT — Room 214 Aria read-only self-code inspection (owner feature)

Agent: Claude Code (Fable 5.1), branch `feature/room214-self-code-inspection` from `37cccd7`, worktree `~/CAOSCARE-BOUNDED/room214-self-code`. Feature commit `3230b792b08c4ceeb9fc7039171dfff08032b69a`.

- **What changed:** only the verified Room 214 session may read the approved CAOSCare source about herself (`inspect_own_code`, `search_own_code`, `read_own_code`). Identity proven server-side on every call from the backend's own records (canonical Room 214 kiosk + pinned resident, the live lease written at mint, loopback origin from the room page proxy); caller-supplied room/resident/kiosk/arguments are ignored; fail closed with reason codes; `CAOSCARE_SELF_INSPECT=off` kill switch. Fixed allow-list, traversal/symlink/secret/binary denies, 120-line bounded reads, capped literal search, inspected-vs-loaded SHA truth (`CAOSCARE_RUNTIME_SHA`), page build SHA embedded by `ctl.sh`. One receipt per attempt, allowed or refused, never source text. Tools + one prompt block are declared only at a Room 214 mint; personality, memory, wake, voice and operational authority untouched. Contract: `docs/ROOM214_SELF_CODE_INSPECTION.md`.
- **Verified:** backend gate on this branch 712 passed / 6 failed / 13 skipped; the 46 self-code tests pass (gate rerun 46/46). Of the 6: five (`iter10 test_session_default`, `iter11 test_research_haiku…`, `iter11 …nine_tools…`, `test_housekeeping_recurrence::test_weekly…`, `test_realtime_aria_session_auth::…unchanged_public…`) fail identically on untouched `37cccd7` (extra `configure_tv_remote` tool / paid research guard / recurrence) — pre-existing; the sixth was this branch's own HTTP test tripping on a commit made mid-run (HEAD moved), passes on rerun and is now deterministic. Frontend 103 suites / 703 tests. Proven in tests: Room 214 session allowed with exact HEAD SHA; Room 215, Room 215 claiming room=214, owner token, admin token, demo room, bare caller all 403 and receipted; owner/phone/admin/base tool catalogs never declare the tools; `.env`, `../`, absolute, `/proc`, symlink file and symlink directory escapes refused; reads clamped; loaded-vs-repository mismatch reported truthfully; only three POST routes exist and no write/shell/db-mutation token appears in the four modules.
- **Line counts:** self_code_identity 137, self_code_inspection 138, self_code_source 230, self_code_tools 90, realtime_resident_session 199 (+7), realtimeSelfCodeTools.js 55, realtimeMessageHandler.js 447 (+1, already over guideline; one import + one dispatch entry).
- **Not done / blocked:** live Room 214 spoken acceptance (needs this SHA loaded on dev :8092 via `scripts/restart_dev_backend.sh` with the room idle, the room page rebuilt with `ctl.sh rebuild`, then Michael's two questions — script in the contract doc). No runtime was changed by this entry; dev backend still `37cccd7`.
- **Next safe step:** merge the PR into `integration/2026-09-27`, load the merged SHA on :8092 and rebuild the room page when Room 214 is idle, run the spoken acceptance, post the receipts.

## 2026-10-15 17:40 CDT — Room 214 self-code inspection LIVE ACCEPTED (PR #169 merged, loaded, spoken test passed)

Agent: Claude Code (Fable 5.1). Owner-authorized merge of PR #169 → `integration/2026-09-27` = `1f60a58fbd5e06989798705bd085ca6c5559e7ea`. Dev backend :8092 restarted by `scripts/restart_dev_backend.sh` → pid 3341053, `CAOSCARE_RUNTIME_SHA=1f60a58`; Room page rebuilt (`main.b13c2b0d.js`, embeds the merged SHA) and page+kiosk restarted; wake listener untouched. Focused live-backend probe and the full receipt trail are on PR #169 (comments). Live Room 214 session `rt_lnrab36x_1792103482825` (wake word, 17:31–17:33 CDT): Michael asked her to look at her own code and explain how she remembers conversations → inspect, 3 searches, reads of `realtime_memory_ingest.py`, `aria_life_memory.py`, `aria_memory.py` (receipts rcpt_4db65bb7ec9f … rcpt_ec3da3c6d7f1, backend/frontend match true), accurate explanation prefixed "I checked the code I'm currently running"; "Can you change your code?" → No, read-only, no tool or authority. Non-214 refusal receipt rcpt_cda44a691c5e. No other Aria context received the tools. Runtime note: `~/CAOSCARE-INTEGRATION` left detached at `1f60a58`; the other lane's two local commits remain on `fix/room214-tv-possessive` (origin `bb657da`) — `git switch integration/2026-09-27` + rebase when that lane resumes. Blocked: nothing. Next safe step: none for this lane (owner said STOP).

## 2026-10-15 19:45 CDT — Live voice model → `gpt-realtime-2.1-mini` (owner cost-control decision)

Agent: Claude Code (Fable 5.1, "Claude 2" cost-control lane), branch `fix/realtime-mini-default`, worktree `~/CAOSCARE-BOUNDED/realtime-mini`. Owner finding: ~89% of OpenAI spend was full Realtime (`gpt-realtime-2.1` / `gpt-realtime-2025-08-28`).
- **Before:** `backend/routes/realtime.py` default `gpt-realtime`; `backend/.env` on the EliteDesk `OPENAI_REALTIME_MODEL=gpt-realtime-2.1` (set 2026-10-12 with voice `marin`); runtime evidence `response_done` rows carried `model: gpt-realtime-2.1`. Session-creating paths, all reading the one constant: resident room mint (`realtime_resident_session._mint`), owner `/aria-session` (`realtime.py`), SIP phone bridge (`phone_aria.py`); `ai.py` defines the same variable unused. Fallback: an empty variable fell back to the full `gpt-realtime`. No Realtime usage in Desktop-Agent (its `gpt-*-sol/astra` tiers are its own reasoning path, untouched).
- **Change:** code default `DEFAULT_REALTIME_MODEL = "gpt-realtime-2.1-mini"` (empty env → mini, never the full model); `.env.example` and Product Baseline §5a updated; each minted resident session now records the provider-reported model (`activation_events` event `session_provider_model` with requested vs provider model and voice; `_caos.diagnostics.provider_model` for both resident and owner sessions). Strong-model/text paths (`OPENAI_TEXT_MODEL` gpt-4o-mini, `OPENAI_RESEARCH_MODEL` gpt-4.1-mini) unchanged. Frontend unchanged (no page rebuild needed).
- **Verified (pre-load):** provider `GET /v1/models/gpt-realtime-2.1-mini` 200; free `client_secrets` mints on mini with voices `marin` and `cedar` → 200, provider `session.model = gpt-realtime-2.1-mini`. Gate (`-k` realtime/self-code/owner sets): 58 passed, 3 failed = the pre-existing `configure_tv_remote` count tests. New tests `backend/tests/test_realtime_model_default.py` (3).
- **Load + runtime proof:** recorded in the next entry / PR receipt (dev `.env` line + guarded restart + provider-model evidence from a real session). Live voice/barge-in/tool checks are Michael's spoken acceptance in Room 214.

## 2026-10-15 22:12 CDT — Always-on coordination watch INSTALLED and RUNNING (owner directive 2026-10-16)

- **Agent/tool:** Claude 2 (Claude Code session `caoscare-1-44`), worktree `~/CAOSCARE-COORDINATION`.
- **Branch/ref:** `feature/coordination-watch` (e944e9f, 750b42f, 087ada3, 6813688; draft PR #173), based on integration 58a8958. No product code; no runtime change.
- **What changed:** `scripts/owner_intake/coord_host.py` (session registry + `/proc` host verdicts, duplicate guard) and `docs/status/COORDINATION_QUEUE.json` (queue mirror; #166 authoritative) written; dry run (`CAOS_COORD_DRY_RUN=1`) made non-persistent; test field list aligned with the owner's 15 receipt fields; runbook `docs/COORDINATION_WATCH.md` updated.
- **Verified:** 6/6 tests pass; `caoscare-coordination-watch.service` installed under `~/.config/systemd/user/`, enabled, active (linger yes); first live tick delivered `coord-test-001` (TEST ONLY — NO PRODUCT ACTION) to #166 (comment 6207165097) with the mirror receipt on PR #131 (6207165333); Main Claude's own `gh_watch.sh` consumed it (cursor advanced 03:09:38Z, process exited to re-invoke the session); receipt dedupe (second publish skipped), dispatched-item exclusion, release-boundary gate holding `careops-153-drilldown-truth-002`; service restart → new PID, parent systemd, state preserved, still exactly one delivery; exactly one watcher process, no new Claude session (registry unchanged: caoscare-1-ec busy, caoscare-1-44, caoscare-integration-b2 idle); $0 model API (gh only).
- **Live handoff proof (03:09–03:25Z):** `coord-test-001` delivered (#166 comment 6207165097) and consumed by Main Claude's `gh_watch.sh`; at 03:12Z the gate opened on a mis-matched #153 comment ("not deployed" matched DEPLOYED) and delivered the real next item `careops-153-drilldown-truth-002` (#166 comment 6207212820). The genuine release boundary (#168 FINAL PRODUCTION RELEASE RECEIPT, comment 6206912205, 02:48Z) had already passed, so the dispatch matched the #166 order; the matching was corrected in 25ee0fa (header-based, negation-aware, #166/#168 only, every earlier delivery ACKed first) and the state re-grounded on the #168 receipt. Main Claude ACKed the real item at 03:25:19Z (#166 comment 6207381341); the watcher detected it (`ack-careops-153-drilldown-truth-002`, mirror on PR #131) and a real ACK now implicitly acknowledges earlier test deliveries (ab69493). 8/8 tests.
- **Blocked:** `gh pr edit/ready` was refused by the classifier earlier (retried at close-out).
- **Next safe step:** merge PR #173 (coordination tooling/docs only) into `integration/2026-09-27` after reconciling onto c4225221; the installed service keeps running the merged code from `~/CAOSCARE-COORDINATION`. The watcher, not an interactive session, owns future monitoring. Status: `python3 scripts/owner_intake/coordination_watch.py --status`.

## 2026-10-16 02:30 CDT — Room Aria runtime truth fixes (aria-room-runtime-fixes-001) READY_FOR_OWNER_REVIEW

- **Agent/tool:** Claude Code session `caoscare-1-e7` (parallel owner-authorized runtime lane; not #162). **Branch:** `runtime/aria-room-truth-fixes` from `ecf7334`, worktree `~/CAOSCARE-ARIA-RUNTIME`. ACK #166 c6209685901.
- **What changed (platform-wide):**
  1. Memory: rules for "what do you know / remember about me / what do I usually ask / my preferences" (answer from life story, facts, recent moments with 3-5 concrete examples, no generic personality talk) plus a counted "What {name} usually asks you for" block from conversation summaries (`realtime_memory_recall.py`).
  2. Owner/creator context only in the verified Room 214 mint (`owner_room_context.py`, same proof as self-code inspection + the single owner account); never in other rooms.
  3. Room device inventory `GET /devices/public/room/{room}/inventory` behind `get_room_status`: connected devices, actions per capability, state only where the transport reports it, supported-but-absent types (motorized blinds), offline devices.
  4. Goodbye: comma-joined farewells ("I'll talk to you later, goodbye.") now end the call deterministically (`endIntent.js`).
  5. TV/speaker duck: persisted per-press restore ledger, `recover()` on mount, restore on unmount, one retry, idempotent; `call_audio_*` activation events. Defect found in live acceptance and fixed: the room screen's talk/help buttons (`triggerEmergency`) started calls without the duck; they now use `beginConversation`. Simulator gained `mute` (toggle) and `volume_step`.
  6. Say-a-limitation-once rule. 7. No email/ticket tool: say so; removed the "I'll let the team know you asked" over-promise and "confirm a caregiver is on the way". 8. `check_medication_status` (`POST /medications/public/status-check`): schedule + only staff-confirmed status of an open medication request, else a HIGH Nursing request via `create_resident_request` with receipt; never "on the way". 9. WebRTC call-quality windows (5 s samples, one post per 30 s + final) graded GOOD/DEGRADED/BAD server-side with evidence and causes (network / local_page / provider_latency); one receipt per call. 10. Wake phrase untouched. 11. Blinds: inventory lists open/close/set; a one-way or queued blinds command is reported as sent, not as moved.
- **Verified:** frontend 127 suites / 830 tests (baseline `ecf7334` 124 / 792), production build compiled. Backend gate 1384 passed / 3 failed / 31 skipped; the 3 are identical on baseline `ecf7334` (1366 / 3 / 31: `test_ops_metrics` ×2, `test_therapy_recurrence` weekly).
- **Live local acceptance (scratch stack only):** branch backend :8098 on scratch DB `caoscare_aria_accept_e7` (Room 214 kiosk/resident/memories/owner name copied read-only from the dev DB; all devices switched to simulated `mock`; no HA, email, SMS or live research), branch build :3008, headless Chrome speaking the owner's script through a fake microphone into real `gpt-realtime-2.1-mini` calls (`rt_1ic5du7s_1792134401501`, `rt_4gnzzym0_1792134755970`, `rt_6af4kofd_1792134992618`). Memory, devices, blinds, email, medication, goodbye passed on the first call; the creator answer was generic, the owner block was strengthened, and the rerun answered "considering you're the one who built and owns CAOS Care". TV: one mute at call start, one at hang-up, final state unmuted, 2 device receipts. All leases released. "Hey Aria" wake was not exercised (the listener belongs to the real Room 214 page). Real Room 214 runtime (:8092), its page and the `caoscare` DB were not changed.
- **Not done:** merge, load on Room 214 `:8092`/room page, Michael's spoken acceptance in Room 214. Noted, not fixed (out of scope): `medications/due/by-room` matches reminders against server UTC, not facility time; the first live greeting in two calls was odd ("Got it, I'm going with Michael").
- **Next safe step:** owner review of the PR; after merge, guarded load on the EliteDesk with the room idle and Michael's spoken check of A–F.

## 2026-10-15 22:15 CDT — Owner polish: Customize Layout removed (#153) + public landing redesign (#162)

- **Agent/tool:** Claude Code (Opus 5.5), CAOSCare session. **Branch:** `ui/owner-polish-2026-10-15` from release `c4225221`; worktree `~/CAOSCARE-UI-POLISH`. Frontend/public UI only; no simulator, Room 214, Aria model, database or deploy-infrastructure change.
- **Owner direction (2026-10-15 review of caoscare.com):** remove the visible "Customize Layout" button (supersedes "shrink it"); redesign the public landing page product-first and truthfully.
- **Operations:** the button and its dialog are gone. Hide (card eye), resize (⋮), drag, Add a widget and Restore hidden boxes were already on the page; "Reset to default layout" is now a small link inside the existing Add-a-widget dialog. Saved layout and drag are unchanged code.
- **Landing:** a product-first hero with a real Operations workspace screenshot, then resident → staff → receipt with real screens, then a status board read from `lib/capabilities/status.js`, the existing video library, and paths (Residents & families, Communities, Explore a room, Room screen demo, Staff sign in). Every image is captioned with its data source: the simulated community (synthetic) or the public demo room. The stale stock photo is retired, and so is the old room-screen image, whose wording the live screen no longer uses. The brand mark is now one shared component.
- **Verified:** frontend 124 suites / 788 tests (2 new suites); production build OK.
  - Chrome on the test stack (:3006 serving this branch against :8096 scratch DB):
    - desktop and 390 px: no horizontal overflow, 0 console errors;
    - every public link loads;
    - Customize Layout absent at desktop and 390 px;
    - drag reorders, the save survives a reload, original order restored;
    - Staff On Duty "View details" opens normally.
  - Evidence: `docs/reports/2026-10-15-owner-polish-screens/`.
- **Findings, not fixed (out of scope):**
  1. Simulated ticket "task created" receipts name a different worker as actor than the requester or the assignee (e.g. Care Aide 06 on Resident 020's ticket worked by Care Aide 07). This is a simulator provenance-display question.
  2. Public status `tv: in_development` predates the 2026-10-12 IR TV control in Room 214. This is an owner status decision.
- **Not deployed.** Next: owner review of the staged page, then the normal GitHub → Linode release path.

## 2026-10-16 03:15 CDT — #162 public site rebuilt as one product-first system (READY FOR OWNER VISUAL REVIEW, not deployed)

- **Agent/tool:** Main Claude `caoscare-1-4e` (session `6a466243`), worktree `~/CAOSCARE-162-PUBLIC`, branch `ui/public-site-162` from integration `ecf7334`; PR #175 (`5bf97537`) reconciled in, not deployed as-is. Queue item `public-162-site-redesign-001` (#166 delivery c6208980297, ACK c6208994718/c6209242110).
- **Scope:** public surfaces only (`/`, `/for-residents`, `/for-communities`, `/experience`, `/kiosk/demo` fallback, shared nav/footer/cards). The authenticated Care App is unchanged.
- **What changed:** one public shell and status style; voice-first request journey on every page; home follows the owner's 2026-10-16 message order (Aria your personal helper → everyday room life → community help → platform proof); 22 current product screens and 9 capability drawings replace the 2026-09 command-centre screens, stock photos and placeholders; low vision shown with the real high-contrast and 160% room screen; `/kiosk/demo` with no demo room shows a public preview instead of "No public demo kiosk is configured yet."
- **Status re-audit (evidence in `frontend/src/lib/capabilities/status.js`):** `tv` in_development → pilot (Room 214 Sony TV by IR, one-way); `phone`, `front_desk_calls` planned → in_development (call code exists, no phone system, no call placed); `family_call` stays planned, reframed as authorized-family updates. Nothing is "working".
- **Screens provenance:** scratch DB `caoscare_pub162` (demo seed, sample facility, demo room via `scripts/setup_demo_room.py`, simulated demo devices, one sample staff per department, paused simulated run `simrun:living:44e75afa1e940f8e3cdc` at day 2 14:56). No production or dev data.
- **Open finding (owner decision):** production's public demo kiosk is room 401 "MOCK Eleanor Whitfield" (greets "Hello, Mo."), not the demo-only room of 2026-10-03; `scripts/setup_demo_room.py` on production would switch it.
- **Verified:** frontend suite and production build; Chrome at 1440 px and 390 px on all public pages (no overflow, no broken images, keyboard open/close with focus return). See the PR for evidence.

## 2026-10-16 04:30 CDT — #162 owner-approved final changes (PR #181), release candidate

- **Agent/tool:** Main Claude `caoscare-1-4e` (session `6a466243`), worktree `~/CAOSCARE-162-PUBLIC`, branch `ui/public-site-162` (start `fcb1bab`). Owner directive: PR #181 comment 6211957665 (design approved; final changes; merge and deploy authorized after acceptance). ACK: PR #181 comment 6212025832.
- **Status policy (owner, 2026-10-16):** In pilot = proven to work in the CAOSCare product/pilot architecture, not necessarily installed in every room. The public site shows only Working / In pilot; unproven capabilities are removed, not relabelled. `status.js`: climate → pilot, blinds → pilot (evidence: Aria `adjust_room_temperature` / `set_blinds` + room command path, proven on the demo room's thermostat and blinds with read-back — scratch run 2026-10-16 09:09Z `verified: true`; limits stated: Room 214's test AC unreliable, no blinds installed in Room 214); front desk stays pilot. Removed from the public site: phone and calling, calls to the front desk, family connection, building-wide location, approved wearables, beauty shop (and their concept drawings). `STATUS_META` holds only working / pilot.
- **Room screen demo (`/kiosk/demo`):** public palette on the demo only (`.kiosk-public`, CSS variables; real room screens incl. Room 214 unchanged); `DemoSiteBar` with Back to Explore a Room / CAOSCare home and "Try high contrast for low vision"; high contrast covers every demo panel. Room-screen screenshots retaken in the new palette.
- **Verified:** frontend 127 suites / 807 tests; production build compiled; Chrome (headless, :3006 against scratch backend :8097) at 1440 and 390 px on `/`, `/for-residents`, `/for-communities`, `/experience`, `/kiosk/demo`: no horizontal scroll, every image loaded, every link 200, only `pilot` statuses, no "Planned"/"In development" text; keyboard: Tab to a tile, Enter opens panel, Escape returns focus; on the demo Tab → Back to Explore a Room → Enter lands on `/experience`, Tab → Try high contrast → Enter toggles it. Evidence: `docs/reports/2026-10-16-public-site-162/`.
- **Release plan:** merge #181 into `integration/2026-09-27`; production = the #181 branch head (descendant of production `c4225221`, excludes the parallel Aria-runtime PR #182), fast-forward `main`, `scripts/deploy_caoscare.sh <sha>` on caoscare-prod; rollback `deploy_caoscare.sh c4225221ead08f8fc8063c68bcb639a2b954d9a6`. Receipts on #166 and PR #181.
- **Open owner choice (not blocking):** apply the same public palette to real room screens, or keep the forest/bone room palette in resident rooms.

## 2026-10-16 04:35 CDT — Room Aria follow-up: medication facility clock + call opening (aria-room-followup-truth-001)

- **Agent/tool:** Claude Code session `caoscare-1-e7`. **Branch:** `runtime/aria-room-followup-truth` from `43983cf` (PR #182 merge), worktree `~/CAOSCARE-ARIA-FOLLOWUP`. ACK #166 c6212466948.
- **Medication clock:** `/medications/due/by-room/{room}` and `/medications/ack/{id}` used server UTC for the minute, the weekday and `med_ack.day`, so a Chicago 18:00 reminder fired at 13:00 CDT / 12:00 CST, evening reminders checked the wrong weekday, and an evening acknowledgement counted against the next local day. Both now use `facility_clock()` (`routes/facility_local_time.py`) on the canonical facility timezone (`db.facilities.timezone` → `FACILITY_TZ`); acknowledgements are matched on the UTC `at` timestamp within the facility-local day (23/25 h on DST days), so pre-fix rows keyed by the UTC date are still judged correctly. `check_medication_status` reads the same clock and the same ack lookup (`medications.acked_on`); its truthful staff-status behaviour is unchanged.
- **Call opening:** the greeting is a bare `response.create` with no user turn, so the model answers the last text of its instructions. In the Room 214 mint the self-code and owner blocks were appended after `## How this call opens`; with the owner block last ("be direct, skip hand-holding…") scratch calls opened "Got it, I'm going with Michael. Nice and simple." and "Sure thing, Michael — let me think this through with a clear, steady voice." Room-specific context now goes in through `_build_companion_instructions(room_context=…)`, before the opening block, which always closes the prompt and tells Aria her first words are spoken to the resident (never "Got it"/"Sure thing", never which name she will use or how she will sound). No canned greeting was added; tap calls keep the existing greeting rules, "Hey Aria" calls keep the short answer to their name. Name Aria and the wake phrase are unchanged.
- **Verified:** backend gate 1401 passed / 3 failed / 31 skipped (the same 3 as the #182 baseline: `test_ops_metrics` ×2, `test_therapy_recurrence` weekly). No frontend change. Scratch stack (branch backend :8098 on `caoscare_aria_accept_e7`, simulated devices, no HA/email/SMS): a reminder at the Chicago minute was due and one at the UTC minute was not, the ack stored `day` 2026-10-16 / `tz` America/Chicago and removed it from the due list; three talk-button calls (`rt_10s3ng43_1792142773769`, `rt_uvqmiwa5_1792142815409`, `rt_9h57dbcg_1792142856903`) with the owner and self-code blocks present all opened "I'm here, Michael." and hung up on "Goodbye."
- **Not done:** merge; load on Room 214 (only after merge). Noted, not changed: three consecutive tap calls opened with the same words despite the "previous call opened with" hint; one goodbye reply was "let me take care of that for you now".

## 2026-10-16 06:30 CDT — Room Aria conversation cleanup: varied openings, goodbye cut-off (aria-room-conversation-cleanup-002)

- **Agent/tool:** Claude Code session `caoscare-1-e7`. **Branch:** `runtime/aria-room-conversation-cleanup` from `171751c` (PR #183 merge), worktree `~/CAOSCARE-ARIA-CLEANUP`. ACK #166 c6214328573.
- **Repeated openings:** three consecutive tap calls on the scratch Room 214 copy opened "I'm here, Michael." although the previous opening was quoted in the prompt. The prompt itself suggested "I'm here" twice — the night greeting note ("try 'I'm here' instead") and the help-button line ("a quiet 'I'm here' is enough") — against one "vary your words". Both hints are gone; `resolve_opening` now returns the last three calls' first lines (`recent_openings`), and `## How this call opens` offers up to three short natural openings (`WAKE_OPENINGS` / `TAP_OPENINGS`, plus "Good {part of day}" on tap calls outside the night) minus any whose lead words a recent call used, so suggestions rotate deterministically. "Hey Aria" stays one short line with the name; the opening block still closes the prompt.
- **Goodbye cut-off:** in `rt_10s3ng43_1792142773769` the server auto-response to "Thanks, that will be all. Goodbye." started before the transcript arrived; the model was narrating its `end_call` ("Okay, thanks for the chat—let me take care of that for you now."). The local goodbye cancelled it ~200 ms in, but its full text was shown and saved as Aria's turn (also feeding memory summaries and the next opening hint). `endController` now records the response it cut (`wasCut`); the handler logs that text as `assistant_transcript_cut_by_goodbye` (diagnostics) and never shows or saves it. The close itself was already deterministic (scripted "Okay, bye for now.", hang-up, `stop()` releases the lease, `onEndCall` restores TV/speaker).
- **Verified:** frontend 131 suites / 855 tests; production build compiled; backend gate 1408 passed / 3 failed / 31 skipped (the same 3 as the #182/#183 baseline: `test_ops_metrics` ×2, `test_therapy_recurrence` weekly). Regression tests: `backend/tests/test_aria_opening_rotation.py` (six consecutive tap and wake calls through real `resolve_opening` + render never reuse a recent lead; the real triple repeat), `frontend/src/lib/__tests__/goodbyeCutResponse.test.js` (the scratch sequence replayed through the real hook + handler; eight goodbye phrasings; all 10 fail on the unfixed handler). Scratch Room 214 (branch backend :8098 on `caoscare_aria_accept_e7`, simulated devices): three consecutive tap calls `rt_tkjlgm00_1792149900857`, `rt_r7hvalv0_1792149942710`, `rt_xx21o2yd_1792149984797` opened "Good morning, Michael." / "Hi, Michael." / "There you are, Michael."; "Thanks, that will be all. Goodbye." / "Okay, goodnight." / "Alright, talk to you later." each ended with one "Okay, bye for now.", lease released (`resident_end_call`), TV duck/restore pair simulated, final TV unmuted.
- **Not done:** merge; Room 214 load (needs merge + owner authorization).

## 2026-10-17 — Low-cost Aria voice (draft PR #192), audition stage

- **Agent/tool:** Claude Code (Opus 5.5), solo.
- **Branch:** `proto/aria-low-cost-streaming-voice-001` (draft PR #192, not merged, not loaded). Paid-API receipt coverage merged first: PR #191 `4cb892e` (not loaded).
- **What changed:** cascade transport behind the room page's data-channel seam (mic → local Silero VAD → gpt-4o-mini-transcribe → gpt-4o-mini with the room session's own instructions + 34 tools → gpt-4o-mini-tts in the kiosk-picker voice). No Realtime model, no second prompt; the old Turn mode is not revived (`docs/ARIA_LOW_COST_VOICE_PROTOTYPE.md`). Kiosk voice picker drives the voice (marin/cedar added; preview plays the same speech path). Reload/close of the page now hangs up (room lease + paid session freed at once) — this also applies to the Realtime path.
- **Owner decisions (Michael, 2026-10-17):** Piper rejected ("robotic"); voice chosen by listening — nova is the default; Realtime set aside for now; future: people choose their experience (Realtime vs low-cost) with the cost difference shown. Cost rule: genuine personal use ≤ $10/month (≤ $15 acceptable, $20 hard ceiling), not a resident-facing cutoff.
- **Verified:** real calls on a DB snapshot (`caoscare_aria_voice_audition`): care-request tool used, speech end → audio 1.7–2.0 s (gpt-4o-mini-tts), barge-in clears playback in ~5 ms after detection; every call receipted (test budgets `aria-low-cost-voice-001`/`001b`, $0.0168 + $0.0826, no unknowns). Backend aria_voice/paid_api suites pass; frontend 868/868; room-node 2/2. Genuine use (classified sessions 10-13…10-17) ≈ 9.7 min/day → ≈ $5–7/month.
- **Blocked / open:** the cheaper text model tends to close replies with "anything else… I'm here to chat" (canonical prompt unchanged); found and fixed a model-price prefix bug that under-priced gpt-4o-mini-tts/-transcribe (correction receipts in the ledger).
- **Next safe step:** owner audition via SSH tunnel (ports 3005 + 8794); load on Room 214 only on explicit owner approval.

```
HANDOFF CAPSULE
- Objective:        low-cost Aria (same Aria, cheaper transport) ready for owner audition
- Branch:           proto/aria-low-cost-streaming-voice-001 (draft PR #192)
- Lane / ownership: aria_voice backend route, cascadeTransport.js, room-node/aria_voice, paid-API pricing for these models
- Last proven state:real-call runs on the audition snapshot; tests listed above
- Commits:          see PR #192
- Runtime state:    audition backend 127.0.0.1:8097 (snapshot DB), page :3005, VAD :8794; live :8092/:3002/wake untouched
- Unresolved proven defects: repeated closing line on gpt-4o-mini
- Product invariants that matter here: one Aria prompt; receipts for every paid call; no change to live Room 214 without owner approval
- Do NOT change:    live Room 214 runtime, wake thresholds, Drive exporter, simulator, Linode
- Next safe action: owner listens and decides whether to load the low-cost path on Room 214
```

## 2026-10-19 — Wake broadcast send timestamp prepared for EliteDesk call correlation (not loaded)

- **Agent/tool:** Codex, owner-directed EliteDesk wake-to-call latency investigation. **Branch:** `measure/elite-wake-call-correlation` from `9fe4ce9`; isolated clone `/home/caoscare-1/CAOSCARE-wake-call-correlation`. Live Room 214/EliteDesk listener, EMEET route, thresholds, page, backend, Home Assistant and Linode were not changed or restarted.
- **Change:** `aria_wake.Server.broadcast()` now adds metadata-only `sent_at` to wake frames and logs `wake_send_started` / `wake_sent` with only wake id, timestamp and client count. This supplies the missing source-side timestamp that the separate Desktop Agent helper correlates with recognition, receipt, readiness, click and LIVE evidence. No audio, speech, page text or credentials are recorded.
- **Verified offline:** wake listener unit suite `17 passed in 0.65 s`, including exact frame/log correlation. No microphone, socket service, call, approval or paid provider was exercised.
- **Boundary/rollback:** not loaded or pushed. Rollback remains `9fe4ce9`; loading later must occur only as part of the reviewed two-branch instrumentation change while the call state is freshly verified idle. The six-tool CAOSCare Home Assistant lane remains untouched.

```text
HANDOFF CAPSULE
- Objective:        provide the exact listener event-send timestamp for wake-to-call correlation
- Branch:           measure/elite-wake-call-correlation from 9fe4ce9
- Lane / ownership: metadata-only wake listener instrumentation; Desktop Agent owns call control
- Last proven state:17/17 offline listener tests; no live validation
- Commits:          local review commit recorded at final handoff; nothing loaded
- Runtime state:    live listener untouched
- Unresolved proven defects: source timestamp is not available live until this reviewed commit is staged
- Product invariants that matter here: EMEET route and wake detection unchanged; localhost-only; no audio/content logging
- Do NOT change:    thresholds, model, runtime service, Room 214 page/backend, HA six-tool lane, Linode
- Next safe action: review alongside the Desktop Agent latency commit; do not stage without verified idle
```

## 2026-10-19 03:17 CDT — Dot Aria bounded CAOSCare channel (review package, default off)

- **Agent/tool:** Codex, direct Michael session. **Checkout:** `/home/michaelos/CAOSCARE-arya-call-integration`. **Branch:** `feature/dot-aria-caoscare-channel`, based on unchanged `bc79f9eb0dbe02735e2d9b5d7b49994e1a96f01c`. No push, merge, load, Home Assistant change, credential, resident-production action, paid model call or Linode action.
- **Built:** default-off `/api/dot-aria/*` channel plus a review-only Home Assistant package with six response-returning scripts: configured test profile, departments, approved menu, published schedule/services, receipted request creation and exact-ID request status. Backend authorization requires a dedicated token hash, exact Home Assistant source IP, an existing owner account and one server-configured approved test profile. No tool input can select a resident by name, room or resident ID.
- **Write truth:** request acceptance returns a request ID, receipt ID, status, duplicate marker and notification delivery evidence. It explicitly does not claim that service started or completed. Duplicate open requests reuse the same task while each delivery gets a distinct receipt. Exact status is restricted to the configured profile and covers open or closed tasks.
- **Verified:** focused canonical gate **10 passed / 1,517 deselected**; HA package parsed as 6 REST commands + 6 scripts; health script syntax valid. Final full backend gate **1,472 passed / 11 failed / 31 skipped / 13 deselected**. A matching run on detached unchanged base `bc79f9e` reproduced the exact 11: `test_ops_metrics` ×2 (5 expected, 4 observed), `test_restart_dev_backend` ×8 (`/tmp/restart_dev_backend.candidate.log` owned by `caoscare-1`, unwritable by `michaelos`), and weekly therapy recurrence ×1. These are baseline failures, not hidden and not called green.
- **Production-file sizes:** new `routes/dot_aria_channel.py` 166 lines; modified `routes/actor_context.py` 92; `routes/task_lifecycle.py` 263; legacy `server.py` 350 (+2); legacy `resident_requests.py` 463 (+19 net); schema-heavy legacy `models.py` 1,881 (+0 net). No new oversized implementation file was created.
- **Not installed/live:** no HA package, secret, Assist exposure, backend environment or runtime was changed; Arya is not connected to these tools. Existing wake, Playwright call control, EMEET audio and spoken hang-up remain outside this change.
- **Review/activation:** `docs/ops/dot-aria/START_HERE.md` is the canonical checklist, including secure local credential entry, exact six entity IDs, health checks, rollback and one supervised meal → test maintenance request → same-ID status acceptance.

```text
HANDOFF CAPSULE
- Objective:        activate and prove the six bounded Dot Aria CAOSCare tools after owner review
- Branch:           feature/dot-aria-caoscare-channel from bc79f9eb0dbe02735e2d9b5d7b49994e1a96f01c
- Lane / ownership: Dot Aria backend channel + review-only HA package; do not alter the live wake/call stack or another checkout
- Last proven state:focused 10/10 green; HA package 6+6 parses; full gate has 11 exact base-reproduced failures
- Commits:          local review commit recorded by the final handoff; nothing pushed
- Runtime state:    no integration loaded; no credential created; live CAOSCare/HA/call stack untouched
- Unresolved proven defects: baseline test failures listed above; live HA/Arya discovery and request acceptance untested
- Product invariants that matter here: backend identity/profile scope; published/read-safe data; receipts and truthful status; human-supervised non-emergency use
- Do NOT change:    resident scope from speech; live services overnight; firewall/tunnels; Linode; call-control retry/wake behavior
- Next safe action: Michael reviews START_HERE step 1 and selects the exact existing synthetic/test resident_id for activation
```

## 2026-10-20 01:15 CDT — existing six-tool channel reconciled; activation still gated

- Agent/tool: Codex, direct owner instruction to connect the Care app and leave the currently working regular-ChatGPT Voice path alone. Checkout `/home/caoscare-1/CAOSCARE-DOT-ARIA-CONNECT`, branch `feature/dot-aria-caoscare-connect`; original Michael-owned checkout and live integration checkout unchanged.
- Built on the recovered six-tool channel, not a replacement: added atomic Mongo operation-ID claims/replay/conflict handling; exact server-owned Room 214 validation on every endpoint; genuine repeat asks still use the canonical request lifecycle and content-aware same-issue matching; task ID, receipt, lifecycle and operation-specific notification evidence are preserved through the HA response adapter.
- Compatibility correction: retain string-valued `delivery` on the canonical request bus so existing `newRequestMessage()` clients continue working; add safe `delivery_evidence` rather than replacing that field. The channel does not expose staff notification addresses/routes or reuse the legacy frontend's unsupported repeat-notification wording.
- Tested with synthetic scratch data and stubbed channel notifications: canonical gate 5 **30 passed / 1,505 deselected**, one deprecation warning, 13.14 s (`/tmp/caoscare_backend_test_gate.NrfjLb.log`); expanded request/lifecycle gate 6 **34 passed / 1,501 deselected**, same warning, 11.42 s (`/tmp/caoscare_backend_test_gate.Pb4Jbb.log`). Separate runs with overlap, not 64 unique tests. Both exit 0 and verify their own backend identity before/after testing. No hardware/provider tests or full-suite green claim.
- Live read-only evidence: Care app `/api/health` HTTP 200; `/api/dot-aria/capabilities` HTTP 404. HA 2026.10.2 has MCP but no loaded `rest_command` component or `caoscare_*` script service. The existing ChatGPT→HA connector returned current light discovery successfully; neither light was changed. The channel's four auth/profile environment settings are absent.
- Existing voice evidence: helper records live at 01:06:08, post-end refresh sent 01:06:21, exact Start-enabled/End-absent idle and ready 01:06:44. That is one completed observed cycle, not a current-idle guarantee or reboot recovery proof. Listener/helper/tunnel remain active with unchanged PIDs 571938/616161/559440 and zero systemd restarts; no restart or browser action was performed.
- Activation remains unperformed. Asked Michael specifically whether the dedicated local Room-214-only service credential may be created/stored; no key was generated or existing credential changed. Exact approved owner/profile binding, config check, safe idle load window and six-script exposure are still required. Do not substitute an owner JWT or broaden the existing OpenAI/HA keys.
- Implementation sizes: `dot_aria_channel.py` 190 lines, new `dot_aria_operations.py` 73; canonical legacy `resident_requests.py` 477 (already oversized at the base; only bounded provenance/result additions, no new large implementation block); channel test file 289. `git diff --check` passes.
- Rollback boundary: nothing loaded; revert only this isolated lane's review commit if rejected. Live integration `59b6546`, Michael-owned original `a33bf22` and current voice helper `73815cd` remain intact. Once activation is authorized, preserve exact live config backups before any write.

## 2026-10-20 01:22 CDT — shared readiness/history requirements queued, not implemented

- Agent/tool: Codex, direct owner requirement capture; branch `feature/dot-aria-caoscare-connect`. Existing six-tool preparation is preserved at local commit `b50cf88`, not loaded or pushed.
- Added a dated local capture to the existing [queue document](PILOT1_READY_QUEUE.md#readiness-gauge-queue), explicitly separate from its historical Pilot 1 assignments. Shared task ID `arya-readiness-history`; status PARKED behind the current wake-reliability fix.
- Single authoritative specification: [Desktop Agent IDEA_BOOK §6](../../Desktop-Agent-arya-regular-chat/docs/IDEA_BOOK.md#readiness-gauge-spec). It covers host resources, voice/HA/Care readiness, fresh evidence versus UNKNOWN, correlated persistent operational history, bounded storage/overhead, access control/privacy, and synthetic-first/coordinated acceptance. CAOSCare will consume the same measurements, not create a duplicate collector, listener, browser client or recovery authority.
- Verified this is documentation only: cross-link destinations/anchor identifiers exist and whitespace checks pass. No gauge code, daemon, runtime settings, credentials, resident data or live services changed. No remote publication or gauge acceptance test is claimed.
- Current attention returns to wake reliability. The Care app remains tested but unactivated; exact scoped credential/profile and safe activation prerequisites from the prior entry still apply. Rollback for this capture is independent of both the six-tool preparation and live voice behavior.

## 2026-10-20 01:31 CDT — owner resumed Care connection; home-test binding corrected offline

- Agent/tool: Codex, direct owner instruction "so hook up caoscare" after Michael confirmed wake-to-Voice working. Branch `feature/dot-aria-caoscare-connect`; live voice, listener, browser and tunnel unchanged.
- Read-only preflight: Care health HTTP 200, channel capabilities HTTP 404; HA config/services HTTP 200, version 2026.10.2, MCP loaded, REST commands absent, no CAOSCare scripts. The existing connected HA tool reached the server and returned "No exposed entities found in domain(s): script" (semantic INVALID_ARGUMENT, not network failure). No device action, resident request or staff notification sent.
- Found a concrete activation defect: the prepared guard required profile room `214`, but the documented/current Michael home-test identity `res_2425767f4a51` has `214-HOME`, already pinned to physical Room 214 by kiosk `kio_dc8c06a19608`. Read only those known test identity/binding fields; no other resident records or conversation contents inspected.
- Corrected `_approved_profile()` to allow the established `214-HOME` label only with a matching existing server-owned Room 214 kiosk pin. Fresh checks deny reads/writes if the pin is removed, points elsewhere or the profile moves outside this scope. No record is moved or created. Existing profile ID, physical request-room `214`, provenance, operation replay protection and receipt handling preserved.
- Isolated gate: first run failed test collection because the new test imported a sibling without the repository's `tests.` package prefix. Corrected the test import; second canonical gate **40 passed / 1,501 deselected / one deprecation warning in 12.29 s**, exit 0. Run ID `063d1225-fe5e-47e1-97e6-a5f28e0bf3b0`, scratch database `caoscare_dot_aria_home_scope_gate2`, port 8074, backend log `/tmp/caoscare_backend_test_gate.fvWwoK.log`; no live/provider tests. Scratch backend stopped by the gate.
- New/modified implementation sizes: channel 201 lines; new home-scope tests 59 lines. Documentation updated in existing handoff/README/map. `git diff --check` passes.
- Exact remaining gate: owner answer authorizing creation/storage of the dedicated local CAOSCare credential (not an OpenAI or HA key). Asked one specific question; no credential generated, live config/exposure changed, merge/load or restart performed. Activation will briefly restart HA to load its REST command component and guarded-reload the development backend only after fresh idle verification. No real request acceptance until a new supervised test.
- Rollback: review-only correction can be reverted to `8701519`; live integration remains `59b6546`, with its older running backend unchanged. Nothing pushed. Next safe action is the credential decision, then exact scoped configuration and verified idle activation through the existing six-tool route.

## 2026-10-20 — approved credential provisioned; activation candidates verified

- Agent/tool: Codex, branch `feature/dot-aria-caoscare-connect`. Michael explicitly approved creation/storage of the dedicated CAOSCare credential and replied "its free" to the fresh EliteDesk-idle question. This authorizes the bounded HA/development-backend activation, not a test call or real staff notification.
- Added `scripts/dot_aria_credential.py` (52 lines) and `scripts/dot_aria_stage_config.py` (70), with `backend/tests/test_dot_aria_credential.py` (71). Provisioning is exclusive, private, never displays the secret and never rotates a prior credential implicitly. Staging preserves old config and refuses an existing/conflicting channel configuration. No daemon, listener or browser client added.
- Credential and private rollback/candidate files reside in `/home/caoscare-1/.config/caoscare/dot-aria-activation-20261020` (0700); token and candidates are 0600. The backend candidate contains only its SHA-256 digest. Scope: existing owner `user_630fb526bd7f`, existing test profile `res_2425767f4a51` with the verified Room 214 pin, HA source `192.168.122.137`. No OpenAI/HA credential altered or exposed.
- Final isolated canonical gate: **44 passed, 1,501 deselected, one deprecation warning, 12.29 s**, exit 0; run `77cfbfca-89ff-46a9-874e-1216ea8c03c4`, scratch DB `caoscare_dot_aria_activation_final_gate`, port 8074, log `/tmp/caoscare_backend_test_gate.FvDXIs.log`. Preceding provisioning-only revision passed 43 tests. No provider/hardware test or staff notification.
- Status at this checkpoint: candidates rendered, not yet installed/restarted/exposed. The existing six-script package will be loaded via a single named HA package; current `scripts.yaml` and all existing exposures retained. Official HA 2026.10.2 source confirms the supported `homeassistant/expose_entity` API for exactly the six scripts and response-preserving MCP dispatch. Source: `https://raw.githubusercontent.com/home-assistant/core/2026.10.2/homeassistant/components/homeassistant/exposed_entities.py`, `https://raw.githubusercontent.com/home-assistant/core/2026.10.2/homeassistant/components/mcp_server/server.py`.
- Fresh accessibility inspection could not expose regular-Voice controls, so it is not asserted as idle proof. Owner's current idle confirmation plus continued listening/no newer helper event is the operational load gate; fresh call-related activity must abort. No extra Playwright connection or reset signal was used.
- Next: preserve integration ref/config rollback, install checked candidates, run HA configuration validation, then bounded reload and read-only discovery. A later entry must record actual loaded versions/results rather than treating this checkpoint as completion.

## 2026-10-20 01:48 CDT — scoped Care channel loaded; ChatGPT metadata refresh remains

- Agent/tool: Codex; isolated branch `feature/dot-aria-caoscare-connect`. Michael explicitly authorized the scoped credential and confirmed "its free" for the idle load. No public push, Linode, resident-production action, test call, device toggle or real staff request.
- Loaded: integration checkout fast-forwarded `59b6546`→`6b96741` with rollback branch `rollback/dot-aria-before-20261020`; guarded backend restart proved runtime `6b96741`, PID 651391, port 8092. Previous running backend SHA was `d777641`, distinct from previous source SHA. Scoped config uses existing owner/profile/Room-214 kiosk pin and exact HA VM source; no resident record changed.
- HA: preserved original configuration/secrets, installed one named package, passed core config check, restarted once at 01:39 CDT. Runtime script validation nevertheless rejected four scripts because their empty text-selector maps were invalid after package processing. Corrected five fields to `text: {multiline: false}` and reloaded scripts only; all six services now present. No second HA restart.
- Focused regression: **45 passed / 1,501 deselected / one deprecation warning / 12.42 s**, exit 0. Run `02e6ccf8-2823-4098-9f3e-88b2e13e1b97`, scratch DB `caoscare_dot_aria_selector_gate`, port 8074, log `/tmp/caoscare_backend_test_gate.KdEZKo.log`. Scratch backend cleaned up. No claim of full-suite green.
- Exposure correction: live HA registry generated four entity IDs from aliases, not service names. Resolved the six `unique_id` mappings, revoked the four nonexistent assumed exposures, exposed only actual six, and asserted unrelated exposures unchanged. Complete map and tool schemas/receipt interpretation in `docs/ops/dot-aria/README.md`; no entity renamed/deleted.
- Live read-only verified: HA-origin capabilities/profile/departments/menu/schedule all HTTP 200 with correct approved identity; four HA script responses preserve actual backend data; local MCP lists all six parameterized tools and department/menu/schedule calls return successful response payloads. Ten departments; October 20 menu/schedule empty. Initial MCP verifier incorrectly looked outside JSON's `result` wrapper; corrected interpretation against the actual response, not a server failure.
- Remote connector: ChatGPT→HA light discovery succeeded after load; both lights remain on and untouched. `GetLiveContext(domain=script)` returns no entities by design in HA 2026.10.2, not proof of absent script tools. Current chat tool catalog still has no CAOSCare tools; the supported next step is Refresh on the **existing** ChatGPT Home Assistant connection, then owner read-only acceptance. No app/key recreation or broadened permissions. Plugin Management confirmed reuse of the available connection; OpenAI Docs identified the supported metadata-refresh workflow.
- Wake listener/helper/browser/tunnel PIDs `571938`/`616161`/`616165`/`559440` unchanged; services active, zero restarts. This proves process preservation, not a new live audio cycle or restart recovery. TV work and readiness-gauge queue intact.
- Code sizes: package 214 lines (configuration); selector tests 52. Prior provisioning scripts 52/70; channel 201; operation module 73. No new oversized implementation. Rollback private directories: EliteDesk `/home/caoscare-1/.config/caoscare/dot-aria-activation-20261020`, HA `/config/.caoscare-dot-aria-rollback-20261020`. No secrets in Git/output.
- Credential cleanup after verified authenticated reads: removed only `channel.token` and `ha-secrets.candidate.yaml` from the exact private activation directory. Active HA secret and backend hash remain installed; original configuration backups retained. Do not rerun provisioning or rotate the credential as part of metadata refresh.

```text
HANDOFF CAPSULE
- Objective:        finish owner-side discovery/acceptance of existing six-tool Care channel
- Branch:           feature/dot-aria-caoscare-connect; loaded backend 6b96741
- Lane / ownership: six-tool channel only; do not touch working Voice/TV/gauge lanes
- Last proven state:45 focused tests pass; six local MCP schemas; real read-only Care data
- Commits:          local only; no push; activation selector/docs receipt follows 6b96741
- Runtime state:   backend 8092; HA package/exposure loaded; original Voice/tunnel PIDs unchanged
- Unresolved proven defects: ChatGPT session catalog not yet refreshed; live writes untested
- Product invariants that matter here: one owner-bound test profile; atomic retry guard; real receipts; truthful notification evidence
- Do NOT change:    credentials again, other resident scope, Voice controls, TV, real staff records
- Next safe action: owner clicks Refresh on existing Home Assistant connection in laptop ChatGPT; then read departments only
```

## 2026-10-20 02:02 CDT — Manage spinner investigated; no current tunnel/HA failure reproduced

- Agent/tool: Codex, read-only diagnostics after Michael reported the existing connection's Manage screen stuck spinning with Reconnect visible. No refresh completion or ChatGPT Care-tool availability is claimed. No service restart, configuration/exposure change, credential change, browser action, staff request or device actuation.
- Tunnel under `caoscare-1`: existing PID 559440, active since October 19 20:09:30, zero systemd restarts, exactly one client. Protected key-file reference and intended `main` endpoint `http://192.168.122.137:8123/api/mcp` intact. Live/ready checks succeed; successful control-plane poll age 13.298 seconds at the first check. The unauthenticated startup probe's `auth-required` is expected for a protected endpoint, not evidence that the stored ChatGPT authorization has expired.
- Fresh arrival evidence: local tunnel event ring records `openai-mcp-discover` at **01:59:35.269 CDT**, then initialization/acknowledgment/another request through **01:59:37.764**, correlation `0879714f-ae6a-475d-9c1f-d24db593bf14`. This predates this diagnostic's own external tool read. It establishes discovery traffic arriving, but no owner click timestamp was provided and the response body is not logged; do not assert exact click correlation or successful ChatGPT metadata adoption. Response metrics show `server/discover`/initialize/control-plane responses with HTTP 200 and no newly logged error in this interval. Transport HTTP success alone is not semantic tool-discovery proof.
- End-to-end existing-connection check: at **02:00:11.098–02:00:11.640 CDT**, the available ChatGPT HA tool returned the overhead light's current ON state successfully, correlated to tunnel request `50afa21c-10c2-449a-b7b7-60e2bde025d6` at 02:00:11.609. Light untouched. The prior OAuth token-endpoint exchange at 01:47:25 returned HTTP 200; no new token-exchange failure was logged during this refresh. Do not recommend Reconnect merely because that button exists.
- Fresh local HA MCP verification: initialize HTTP 200 / 10.9 ms, initialized notification HTTP 202 / 2.5 ms, `tools/list` HTTP 200 / 31.6 ms, all six actual Care tools with required parameters present. Read-only department call HTTP 200 / 36.0 ms, `isError:false`, transport/backend success, 10 departments. Both OAuth discovery documents currently HTTP 200; issuer and authorization/token endpoints consistently use the intended HA VM.
- Redacted HA logs have no entries after 01:48 in the inspected current log. Old 01:39 empty-selector errors are historical and corrected, as fresh six-tool discovery confirms; do not treat them as a recurrence. No raw HTTP logging enabled and no secrets printed. Default logs do not provide a complete successful-request access trace.
- Remaining failing boundary: Michael's ChatGPT Manage/metadata-refresh flow has not visibly completed. Server availability and existing authenticated calls pass; the precise client/UI versus ChatGPT metadata-processing cause remains unknown. This chat's available tool catalog still lacks the six new Care tools.
- Working Voice preserved: listener/helper PIDs 571938/616161 unchanged, active, zero restarts. Care package/credential remains installed. No new live Voice or staff-request acceptance.
- Next single owner action: on the **laptop**, reload only the browser page showing the existing Home Assistant connection's **Manage** screen once (browser Reload), not Reconnect/Delete and not the EliteDesk Voice tab. This tests a stale settings view without replacing setup; then inspect the displayed metadata state before another action.

## 2026-10-20 02:10 CDT — reload cleared spinner, not verified metadata adoption

- Owner observation: laptop browser Reload cleared the spinner and left Manage idle; no automatic reconnect or reconnect prompt. Subsequent attempt still did not work. Arya successfully read both lights (desk 100%, overhead 50%, both ON), with no actuation. Do not recast this as an entire-tunnel outage, successful metadata refresh, or a request to repeat setup.
- Additional read-only evidence: the running tunnel's detailed health reports queue depth 0, active work 0, 53 dispatched completions, 0 dispatcher failures/timeouts, and 53 responses accepted/completed by the control plane with 0 retries/terminal delivery failures. Latest completion remains 02:00:11; no additional tunnel events after 02:02 at inspection. Existing protected key-file configuration, one client and HA target remain intact.
- Important evidence limit discovered in installed v0.0.16: `/health/mcp` explicitly reports `unsupported_transport` / `same_child_evidence_unavailable` for this HTTP-streamable connection. Its empty tool list is NOT proof of missing HA tools. Neither readiness nor response-upload acceptance proves that ChatGPT saved the returned catalog. No raw HTTP logging was enabled to obtain bodies.
- Fresh local authenticated MCP audit: `tools/list` succeeds in 31.3 ms; 27 total tools including all six Care tools, no duplicate names, supported name syntax, object input schemas on the six, no continuation cursor, 14,878 serialized bytes. Metadata SHA-256 `b9545e19502b86bc3ee610bfd885e764f06e21c2308507ba8f316197fa62af57`. Full JSON Schema validator was not installed in the inspected diagnostic environment; no dependency was installed and no full schema-validation claim is made.
- No server-side metadata or auth rejection is reproduced. The failed owner-visible step remains Manage/metadata refresh; exact browser request/error and ChatGPT-side processing outcome are unavailable from these logs. Current session still exposes no Care tools. Available plugin-inspection discovery does not resolve this custom connection's management details; unrelated plugin results were not substituted. Official OpenAI Docs and installed client troubleshooting help were used to interpret health and logging limits, not to justify new setup.
- No runtime/configuration/credentials/exposure/Voice changes, restarts, test calls or staff requests. Only this diagnostic receipt changed.
- Next single owner action: provide one screenshot of the current **laptop Home Assistant GPT Manage panel**, including its buttons and any visible error. This identifies the actual management surface before another action; do not ask for another reload/reconnect or secret/key page. The missing evidence is the failing UI step, not another light read.
