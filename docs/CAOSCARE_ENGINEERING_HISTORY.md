# CAOSCare engineering history — how it became what it is

**The one canonical chronological story** (owner directive 2026-10-15). Written for a technically capable
reader who was not present. Each era states the problem, the decision, what was built, the evidence, the
outcome, what it replaced, and a status word: **CURRENT · SUPERSEDED · HISTORICAL · EXPERIMENTAL · PARKED**.
It links to the detailed reports, pull requests and issues instead of repeating them.

This file is history. For **today's truth** read the header of `docs/PROJECT_STATE.md`; for durable
architecture `docs/CAOSCARE_PRODUCT_BASELINE.md`; for where code lives `docs/REPO_MAP.md`. The dated
`docs/PROJECT_STATE.md` entries before 2026-10-12 were trimmed from the working copy on 2026-10-12; they
are intact in git history: `git show 4647c79^:docs/PROJECT_STATE.md` (entries 2026-06-14 → 2026-10-03).
The 2026-09-23 decision history (`docs/reports/2026-09-23-milestones-and-decision-history.md`) is the
detailed record through September; this document continues it and does not replace it.

Evidence used: `git log` (first commit 2026-04-17; 69/43/15/2/85/167/755 commits Apr→Oct), every merged
PR (#1–#171), open/closed PRs, issues #117, #129 (historical), #153, #162–#166, #168, PROJECT_STATE
history, `docs/reports/`, the TSBs, the owner directives recorded in the repo, and the runtime receipts of
2026-10-15. Where a rationale was never written down it says **rationale unrecorded**.

---

## 0. The evidence ladder (read this before trusting any claim)

A future engineer must not let one rung stand in for another. CAOSCare records each separately:

| Rung | What it proves | What it does not prove |
|---|---|---|
| **Git commit / PR** | the code exists at an exact SHA | that it runs, passes, or is loaded anywhere |
| **Test result (gate)** | the automated checks passed on that SHA (fresh DB, named port, run id echoed by `/api/health`) | runtime behaviour on a real host |
| **Runtime receipt** | a real process did a real thing (`db.receipts`, activation events, `CAOSCARE_RUNTIME_SHA` on the pid) | that a human saw it work |
| **Browser acceptance** | a real browser drove the real UI against a named backend (desktop + 390 px, zero failed API calls) | physical hardware or owner judgement |
| **Physical acceptance** | Michael observed it in Room 214 (wake, TV, voice) | that the owner accepts the section |
| **Owner acceptance** | Michael inspected and approved the bounded section | that it is deployed |
| **Production deployment** | an exact SHA is running on caoscare.com with a receipt and a rollback SHA | nothing further |

The rule that binds them, adopted 2026-10-02 (§5): **No action without a receipt. No receipt without
provenance.** An agent's "done" is never evidence.

---

## 1. Origin — April to July 2026: the product idea and the first stack

**Problem / objective.** A senior-living community needs a voice-first companion in the resident's room
that can also file real requests to real staff, with the staff and the administrator able to see what was
asked, what happened, and who did it. Michael's framing from the start: assistive, human-supervised,
receipt-backed; not a doctor, nurse, device or emergency service (`AGENTS.md`, `README.md`).

**What was built.**
- 2026-04-17 → 04-29: scaffold generated on the Emergent platform (FastAPI + Mongo backend, React frontend,
  Android companion/bridge/vision surfaces). ~65 `auto-commit` commits. **HISTORICAL** (rationale unrecorded).
- 2026-05-16/17, PRs #1–#13: the repo made self-owned — Emergent branding, visual-edit tooling and the
  Emergent dependency removed; direct OpenAI for chat/TTS/STT/memory/vision (#3) and the **first OpenAI Realtime
  relay** (#4); owner bootstrap script and staff-only public registration (#10); env templates and the first
  deployment runbook (#1, #12); copy changed to "staff" and human-review wording (#11). **CURRENT** foundations.
- 2026-06-10 → 06-14: direct Google Sign-In replaced the Emergent auth relay; first local prototype on a
  Lenovo laptop (PROJECT_STATE 2026-06-14 entries). **CURRENT**.
- 2026-07-28: the dedicated `caoscare-1` host stood up, owner bootstrapped, password login verified.

**Original assumptions later superseded:** a docked or wall-mounted resident tablet as the room interface
(§2, §8), turn-based STT→chat→TTS voice (§3), Emergent-hosted auth and tooling.

---

## 2. Early room architecture — August 2026: the room node, the eMeet, and "no tablet"

**Problem.** Voice in a real room needs a microphone, a speaker, echo control and a computer that the
resident never has to operate.

**Decisions and evidence.**
- 2026-08-02: EliteDesk node build (`docs/ELITEDESK_NODE_BUILD.md`): HP EliteDesk 705 G4 as the room/
  facility computer, Home Assistant OS in a libvirt VM beside CAOSCare, the Aria voice-first directive and the
  capability portfolio (`docs/ARIA_VOICE_FIRST.md`, `docs/ARIA_CAPABILITY_PORTFOLIO.md`).
- 2026-08-09: **Realtime over WebRTC becomes the only resident voice path**; the turn-based path was retired
  after two drifting prompt builders caused a live bug (`docs/ARIA_VOICE_FIRST.md`). Terminal 8 built the
  receipt foundation and the resident request bus on the existing `StaffTask` spine rather than a parallel
  object (`docs/TERMINAL_8_OPERATIONAL_LAYER.md`). **CURRENT**.
- 2026-08-21 → 08-23: Terminal 9 — transportation engine and calendar, Front Desk role, Resident Record with
  session-grouped conversations, voice forensics by room (`docs/reports/2026-08-2*`). A **failed experiment**
  is recorded honestly: `semantic_vad` + eagerness "low" produced a 38 s dead zone live and was reverted
  (`docs/reports/2026-08-23-1345-semantic-vad-failed-experiment.md`). **SUPERSEDED**.
- 2026-08-24 → 08-27: echo research across rooms 401/403/408 showed a split microphone + soundbar causes
  phantom turns; decision: **one eMeet speakerphone is the single capture + playback endpoint** so one AEC
  path owns Aria and (eventually) TV audio (`docs/ROOM_AUDIO_ARCHITECTURE.md`, 2026-08-27). A mock device
  layer for dev rooms and the Home Assistant adapter with read-back verification followed. **CURRENT** (the
  acoustic reasoning is what runs in Room 214 today).
- The resident room is **not tablet-based** (`docs/CAOSCARE_PRODUCT_BASELINE.md` §2). **CURRENT**.
- RF / IR / Zigbee / SIP / Twilio were recorded as room-node integration directions, not commitments. RF
  became real first (§2 below); IR became real on 2026-10-12 (§3); SIP/Twilio stayed partly built
  (`telephony/`, `routes/phone_aria*.py`; accounts/hardware never provisioned). **PARKED** except RF and IR.

**Safety path established.** 2026-08-29 → 09-06: real Nooelec SDR + `rtl_433` + paired Interlogix/Lifeline
pendants open a resident assistance event (`Alert`) through `record_resident_activation()`; the room lease
singleton stops two Aria sessions sharing one mic; TSB-001 (name attribution + unaudited profile write) and
TSB-002 (fabricated emergency + periodic RF frame + 60-minute zombie session) are the two founding incident
records (`docs/tsb/INDEX.md`). The Level 1 model (ResidentEvent = extended Alert; event lifetime decoupled
from session lifetime) came from the 2026-09-06 break-test (`docs/LEVEL1_BREAK_TEST_2026-09-06.md`). **CURRENT**.

---

## 3. Voice and wake evolution — August to October 2026

```
"Aria" three-syllable wake requirement           RATIFIED 2026-08-02
 → local keyword spotting (sherpa-onnx) proven     2026-09-23, Room 214, close range   PHYSICALLY VERIFIED
 → overnight false wakes; "air-ee-uh" == "area"    2026-09-24                          single word REJECTED
 → Wake Phrase Lab (phoneme collision analysis)    2026-09-24, tools/wakelab           EXPERIMENTAL
 → "Hey Nabu"/"Okay Nabu"/"Naboo" Voice PE tests   late Sept – early Oct               HISTORICAL, not identity
 → owner decision: name Aria, phrase "Hey Aria"    2026-10-03                          CURRENT
 → "Hey Aria" EliteDesk listener on the eMeet      2026-10-08 (RQ-036), tuned 0.05/1.5 CURRENT
 → Voice PE as the room endpoint (plan)            2026-10-03 → 2026-10-14             SUPERSEDED
 → Voice PE rejected; eMeet + listener restored    2026-10-14                          CURRENT
 → wake/TV mute/goodbye/restore chain accepted     2026-10-12/13, Room 214             PHYSICALLY VERIFIED
```

- **Why the single word failed:** five overnight wakes from background speech; CMUdict shows the intended
  pronunciation is identical to *area*; detector tuning cannot separate identical sounds, so the phrase had to
  change (`docs/WAKE_PHRASE_LAB.md`). A Whisper second-stage verifier was tried the same night and preserved as
  an experiment only (`docs/experiments/2026-09-24-whisper-wake-verifier.md`). **SUPERSEDED**.
- **Why "Hey Aria":** the name stays Aria (identity), the two-word phrase lowers collision; "Nabu"/"Naboo"
  phrases from the Voice PE firmware experiments were explicitly ruled out as product identity on 2026-10-03
  (`docs/ARIA_WAKE_WORD_ARCHITECTURE.md`). Physical evidence: `docs/reports/2026-10-08-hey-aria-physical-evidence.md`
  (6 logged wakes → 6 sessions at 0.05/1.5), outage diagnosis and recovery 2026-10-12 (runner cleanup killed
  the backend, PR #137), and the accepted chain 2026-10-12/13: "Aria" alone does not wake, "Hey Aria" wakes,
  TV mutes, conversation, "Okay, bye for now.", TV restores (PROJECT_STATE 2026-10-12 23:51/23:53).
- **Far-field:** close-range reliability is proven; far-field reliability and the false-wake rate remain
  open; a shadow detector logs at 0.01/3.5 without waking; wake tuning is **PARKED** by owner direction.
- **Voice PE:** bought as the intended per-apartment endpoint (2026-10-03 architecture correction), custom
  firmware branches `firmware/voice-pe-naboo` (proof only) and `firmware/voice-pe-aria`, HA bridge spike
  `spike/voice-bridge`; on 2026-10-14 Michael judged the quality unacceptable ("voicepe sucks"), the HA
  integration was removed and Room 214 went back to the eMeet path. A real outage found the same evening (the
  eMeet lost its PulseAudio profile; listener crash-looped) was fixed by restarting audio and the units.
  **SUPERSEDED**; future hardware is Home One (§8).
- **Voice model and voice:** `gpt-realtime` default → `gpt-realtime-2.1` + voice `marin` on Room 214
  (2026-10-12) → `gpt-realtime-2.1-mini` for all ordinary conversation (2026-10-15, §10).

---

## 4. Aria conversation and memory — the substrate

**Problem.** A companion for an older adult must not invent memories, must not confuse residents, must not
claim actions it did not take, and must carry a conversation across sessions and days.

- **2026-08-09 one identity, several contexts.** Resident Aria (`realtime_companion_prompt.py`), owner `/aria`
  (`realtime.py::_build_aria_instructions`, owner-only since PR #64), Admin Aria (`admin_assistant.py`, text
  tools), telephone Aria (`phone_aria*.py`). They share the name and the service layer, not a prompt;
  `docs/ARIA_CONTRACT.md` is still the owner-authored placeholder meant to unify them. **CURRENT** (debt noted).
- **2026-09-08 → 09-10 conversation substrate** (`docs/ARIA_CONVERSATION_SUBSTRATE.md`,
  `docs/ARIA_SUBSTRATE_IMPLEMENTATION_PLAN.md`): Layer E operational state (what is actually open right now,
  one read-only authority reused by humans and Aria), Layer B cross-session continuity, Layer C "did this call
  already file that", person-specific interpretation patterns ("dos savor" → "dos sabores"), turn-taking
  metrics derived from existing diagnostics. **CURRENT**.
- **Trusted vs untrusted input (2026-08-22 → 10-08).** A user turn that started while Aria was speaking is
  stored for diagnostics but never becomes durable memory; a questionable transcript cannot end a call or
  change a profile; `/memory/realtime-turn` only accepts a live room lease (RQ-028). **CURRENT**.
- **Truth guards (2026-08-30 → 10-09).** End-call grounding, device-ambiguity guard, light on/off must agree
  with the transcript, claim guards and the non-live research label, one-way IR reported as sent-not-verified
  (`docs/reports/2026-10-08-aria-untrue-claims-audit.md`, RQ-031/040/045/046/050). **CURRENT**.
- **2026-10-12 lifelong memory.** Each finished conversation summarized once and folded into one bounded life
  story per resident on the existing `db.memories` store; continuity window 18 h → 72 h; wake-word openers
  vary; goodbye answers open tool calls first (`routes/aria_life_memory.py`, `aria_opening.py`,
  `docs/reports/2026-10-12-platform-build-log.md`). Owner memory is a separate store. **CURRENT**.
- **2026-10-13 guidance profiles.** `supportive_guided` (default, 80-plus hand-holding) and `concise_natural`
  (Michael's room). Note: the Room 214 resident record was never given the concise profile; a bounded fix is
  proposed, not built (`docs/status/ROOM214_LAST_CONVERSATION_IDEAS_2026-10-15.md` §10). **CURRENT / open**.
- **2026-10-15 read-only self-code inspection (PR #169).** Only the verified Room 214 session (canonical
  kiosk + pinned resident + the lease the backend wrote + loopback origin) may read an allow-list of her own
  source; no write, shell, git or DB path exists; every attempt receipted. Live-accepted the same day: she
  read `realtime_memory_ingest.py`, `aria_life_memory.py`, `aria_memory.py`, explained memory correctly, and
  answered "Can you change your code?" with No (`docs/ROOM214_SELF_CODE_INSPECTION.md`). **CURRENT**,
  Room 214 only, not a platform-wide capability.

---

## 5. Governance — why the receipt law exists

- **2026-08 incidents** (TSB-001/002, fabricated appointment and emergency claims, unaudited profile writes)
  showed that a conversational system will narrate things that did not happen unless every action leaves a
  durable, attributable record. The audit trail requirement ("we need to be able to have all the data",
  2026-08-29) is the root.
- **2026-09-20 operational workflow audit** → 15 ratified service-layer decisions and the binding GATE
  (`docs/ENGINEERING_CONTRACT.md`): one canonical service layer for humans, Aria, simulator and adapters;
  Aria is an interface, not an authority; `ActorContext` at the service function; simulation provenance;
  event_log vs receipt boundary; `escalation.tick()` the sole escalation authority; no simulator writes until
  those are implemented.
- **2026-10-02 receipt law** adopted by Michael and recorded in `docs/CAOSCARE_OPERATIONS_SIMULATOR.md` §2:
  *No action without a receipt. No receipt without provenance.* SIM-0 (SC-13, 2026-10-03) implemented it for
  StaffTask: `ActorContext`, `task_lifecycle.transition()` as the one path, chained receipts with actor,
  authority, before/after; device records (2026-10-12), alerts acknowledge/close/ingress (2026-10-12), family
  updates and policy edits followed.
- **Actor identity rules** that came from live use: simulated actors are explicit and never real people
  (`Resident.synthetic`, `simulated` fields, "SIM" labels); an unverified room claim is recorded as such; a
  **test operator** performing clicks in Michael's signed-in session is named as the actor with his permission
  in the receipt (CO-008 v11 acceptance, 2026-10-16T00:30Z); owner acceptance is separate from engineering
  acceptance.
- **Tested SHA vs loaded SHA.** The backend carries `CAOSCARE_RUNTIME_SHA`; every restart receipt names the
  tested revision, the loaded revision and the pid; Room 214's page embeds its build SHA (2026-10-15). A loaded
  runtime that is behind the checkout is reported as stale, never assumed current.
- **Non-destructive history.** Simulator runs are stopped and preserved, never reset in place; receipts are
  append-only; PROJECT_STATE is append-only; production deploys take a Mongo backup and name the rollback SHA.
- **Release control.** The 2026-09-25 incident (an authorised one-line SEO change shipped nine unreviewed
  commits because the deploy script deploys a `main` SHA) produced the open requirement that a deploy must show
  the full production→target diff (`docs/reports/2026-09-25-release-control-requirement.md`). **Open**.

---

## 6. Simulator evolution — from a demo room to a living community

Why it exists: Michael can only test a building if the building is busy. The simulator must drive the same
canonical workflows as real staff with explicitly simulated actors on scratch data
(`docs/CAOSCARE_OPERATIONS_SIMULATOR.md`, `docs/reports/RUNNING_FACILITY_TESTBED.md`).

| Version / step | When | What changed and why | Evidence | Status |
|---|---|---|---|---|
| SIM-0 … SIM-4 | 2026-10-03 → 10-06 | receipt spine, minimal scheduler on the demo room, Live Operations first slice, mixed real + simulated staffing, Nursing and Maintenance scenarios, demo-data continuity | PRs #44, #49, #50, #51, #56, #57, #62, #66, #70 | SUPERSEDED by the living community (demo room still exists) |
| Living community checkpoint | 2026-10-13 | deterministic 80-apartment / 70-occupied / 75-resident community, 50 stable workers, 90-day staffing and care plans, 52,110-event timeline; **10-resident burn-in** as the safe cohort | PR #146 (draft) | the 10-resident cohort is SUPERSEDED (optional only) |
| SIM-003 | 2026-10-14 | passed on a real MongoDB replica set (truthiness, clock anchored on `updated_at`, lease revalidation) | PR #150 | CURRENT |
| SIM-005A/B | 2026-10-14 | realistic staffing (overnight 3 aides + RN on call, maintenance hours + on-call, closed departments say CLOSED); all 75 residents executable; tickets go to the least-loaded on-site worker | PRs #151, #152 | CURRENT |
| SIM-006 | 2026-10-14 | one active ticket per on-site worker, real waits, visible queues; overnight 60× run on a scratch DB | PR #154 | CURRENT |
| SIM-007A + workspace | 2026-10-14 | Live Operations dashboard; then the approved customizable `/operations` design with explainable metrics (#153 defect: "Done Today" was a wall-clock count) | PRs #156, #157, #158, #159 | CURRENT (draft PRs) |
| v7 run | 2026-10-14 | first long run `simrun:living:68d9abcc…` | #168 receipts | STOPPED, preserved |
| **one run per community → several runs, one active** | 2026-10-14 | the one-run limitation blocked a fresh plan while history had to be kept; Michael chose "several runs per community, one active" | PR #167 (`cfc1245`, `537ac80`) | CURRENT |
| v8 real-time 1× | 2026-10-14 22:27 CDT | requests come from people (≈100 resident calls/day in their own words, staff-raised rounds and problem reports), expired-lease fix, 1× speed | PR #167 | SUPERSEDED by v9 |
| v9 | 2026-10-15 02:04 CDT | worker workflow: claim/reassign/release/hand-off are distinct receipted outcomes with reasons; escalations count as overdue; full gate 1308/0; cut over by owner decision 1 | #168 comments 06:25Z–07:04Z | SUPERSEDED by v10 |
| v10 | 2026-10-15 02:41 CDT | service model corrected (cooks vs dining servers, one-hour seatings, 8-min apartment meal, activities escort rule) | `docs/reports/2026-10-15-co008-service-model.md` (on branch `co008/service-model`; the CO-008 reports are not on integration yet) | SUPERSEDED by v11 |
| **v11 Kitchen** | 2026-10-15 15:36 CDT cutover | 30 of 75 residents get room delivery (owner planning assumption), 45 in the dining room, a conservative 13-minute delivery trip, nine meal-delivery aides, 66 workers; run `simrun:living:ebe800685588c1283a63` at 1× on scratch DB `caoscare_sim_acceptance_live20261014b` from detached checkout `~/CAOSCARE-CO008-V11` (`eaa1c23`) | `docs/reports/2026-10-15-co008-room-delivery.md` (branch `co008/room-delivery`, not on integration yet); cutover receipt #168 20:36Z; **engineering live acceptance** #168 2026-10-16T00:30Z (75/75 dinner tickets served as predicted) | CURRENT running stack; owner acceptance pending |
| v12 staffing | 2026-10-15 | 55 workers: housekeeping 2 (weekly 30-minute full clean by territory, Housekeeper 01 Mon–Fri, 02 Wed–Sun), maintenance 1 (on call after hours), activities 1 coordinator, admin = business office manager / administrator / executive director; built and tested on `co008/workspace-staff-drilldown` | #153 22:19Z, #166 22:36Z | **built, tested, NOT LOADED**; cutover needs a separate owner authorization |

Current owner-approved assumptions in one place: `docs/CAOSCARE_OPERATIONS_SIMULATOR.md` §11. They are
planning assumptions, never facility measurements.

---

## 7. Operations UI evolution

- 2026-09-06/07 Admin worktree: operations overview, maintenance work orders, activity log, reporting,
  owner command centre (PROJECT_STATE 2026-09-07 entries). **SUPERSEDED in layout, CURRENT in data.**
- 2026-10-04 Live Operations (SIM-2) on the simulator state. **SUPERSEDED** by SIM-007A.
- 2026-10-11/12 department boards, routing exceptions, current-vs-older records, delivery truth
  (`routes/department_board.py`, `routing_exceptions.py`, `operations_currency.py`, `request_delivery.py`). **CURRENT**.
- 2026-10-14 #153: the owner saw "374 needs attention" and "Done Today" numbers that mixed test/mock rows and
  wall-clock completions with resident calls. Fix direction: every number is a truthful drill-down to exact
  records; live vs simulated separated; simulated day shown beside real time (#164). SIM-007A dashboard, then
  the approved customizable workspace with working card drag, the shared app shell for the whole owner/admin
  app, Settings › Documents (PRs #157–#159). **CURRENT (draft PRs on the CO-008 chain)**.
- 2026-10-15 #153 slice 1: Staff On Duty, worker detail, role truth (`co008/workspace-staff-drilldown`,
  built, not loaded). Owner punch list 21:11Z; **slice 2 authorized 2026-10-16T00:37Z**: truthful
  click-through for Nursing Done Today / Nursing Open / Kitchen Done Today with run scope, real-vs-simulated
  day and actor disclosed. **CURRENT work**.

---

## 8. Hardware direction changes

```
resident tablet / dock                                    SUPERSEDED (before Aug 2026)
 → EliteDesk room node behind the TV + eMeet + TV          RATIFIED Aug 2026; the Room 214 rig today
 → central EliteDesk server + Voice PE thin endpoint        2026-10-03 → 10-14  SUPERSEDED (Voice PE rejected)
 → managed Android phone + dock                            EXPERIMENTAL, nothing built
 → CAOSCare Home One universal appliance (#165)            FUTURE; feasibility only, no purchases
```
Why rejected or deferred: the tablet made the room a gadget and the resident an operator; Voice PE audio
quality failed the owner's judgement; the phone/dock was never built; Home One (far-field array, physical
mute, Pi 5-class replaceable compute, full radio set, battery backup, BYO or local models) is the stated
direction once software proves itself. The XIAO IR Mate (ESPHome) controlling a Sony TV by infrared is real
in Room 214 (2026-10-12); the touch-top is deliberately kept as local TV power (owner decision 2026-10-12).
RF pendant decode (Nooelec SDR) is real; Zigbee/Z-Wave/IR for other devices remain planned.

---

## 9. Cloud and deployment evolution

- **EliteDesk = development and the Room 214 runtime.** Backend `:8092` restarted only through the guarded
  `scripts/restart_dev_backend.sh` (refuses while a lease is live, proves the candidate on a spare port, names
  tested/loaded SHA and pid); Room page built and swapped by `room-node/aria_wake/ctl.sh`. A GitHub Actions
  self-hosted runner path for exact-SHA loads exists (PRs #135–#149) and taught one hard lesson: runner
  post-job cleanup killed the backend on 2026-10-12 until PR #137 stripped the runner marker.
- **GitHub = source of truth.** `integration/2026-09-27` is the authoritative branch; `main` is the release
  branch; worktrees per bounded task; draft PRs; the owner master queue #166 (2026-10-14) replaced the
  dispatch thread #129 (2026-10-11) which replaced #117 (2026-10-09); earlier Pilot 1 files (`docs/PILOT1_*`)
  are historical.
- **Linode = production (caoscare.com).** First deploy 2026-08-30 (`e6c4f47`), 2026-09-01 (`afbb1e0`),
  2026-09-19 (`7bad624`), 2026-09-25 (`348d164`, the release-control incident), 2026-10-11 (`ff87c22`),
  **2026-10-12 17:03 CDT `06e7e2b` (PR #132)** — the last proven production SHA. `scripts/deploy_caoscare.sh
  <full-sha>` on the server takes a Mongo backup and is also the rollback command. Any release after
  2026-10-12 is **NOT YET VERIFIED** at this writing: `origin/main` is still `06e7e2b` and no deployment
  receipt exists on #166.
- **Why the EliteDesk → GitHub → Linode discipline:** production must run an exact reviewed SHA with a backup
  and a named rollback; the 2026-09-25 incident showed what deploying "whatever is on main" does.

---

## 10. AI model and cost evolution

- Text/reasoning routes: `gpt-4o-mini` (`OPENAI_TEXT_MODEL`) for extraction, summaries, admin assistant;
  research via the Responses API web search on `gpt-4.1-mini` (RQ-047, proven live 2026-10-13 with
  citations and usage receipts). **CURRENT**, unchanged by the cost decision.
- Live voice: `gpt-realtime` (May) → `gpt-realtime-2.1` with voice `marin` on Room 214 (2026-10-12). The
  2026-10-09 A/B proposal already named the mini model as the candidate under the owner's "least expensive
  model that passes" rule (Baseline §5a).
- **2026-10-15 owner finding:** about 89 % of OpenAI spend was full Realtime. **Decision:** ordinary live
  conversation (resident rooms, owner `/aria`, phone bridge) runs on **`gpt-realtime-2.1-mini`**; the full
  model is not a fallback (an empty variable falls back to mini). Done the same evening: `.env` on the
  EliteDesk + guarded restart; provider-reported `session.model = gpt-realtime-2.1-mini` with voice marin; a
  real scripted conversation with a tool call and a clean goodbye on mini; PR #171 merged (`e69cb69`) making
  the code default match and logging the provider model per session. Desktop-Agent's `gpt-*-sol/astra`
  reasoning tiers are a different project and untouched. **CURRENT**.
- Cost philosophy: resident experience, accuracy and reliability come first (Baseline §5a); the cheapest
  model that demonstrably passes wins; paid tests need an owner cap; usage is recorded from provider
  `response.done` fields, never estimated when it can be measured.

---

## 11. Where CAOSCare stands now (2026-10-16 ~01:00 CDT)

- **Authoritative branch:** `integration/2026-09-27` at `e69cb69` (PR #171). Production: `06e7e2b` on
  caoscare.com (2026-10-12). Any newer release: not yet verified.
- **Room 214 (Michael's home test room, platform-wide code):** central EliteDesk, eMeet + "Hey Aria"
  listener, OpenAI Realtime on `gpt-realtime-2.1-mini`, lights with read-back, Sony TV by IR (one-way), call-
  start TV mute/restore, lifelong memory, live web lookup, read-only self-code inspection. Dev backend `:8092`
  at `1f60a58` with the mini model loaded by config; Room page `main.b13c2b0d.js`.
- **Simulator:** v11 Kitchen running at 1× on a scratch DB (engineering-accepted 2026-10-16T00:30Z, owner
  acceptance pending); v12 staffing built and not loaded; owner-approved assumptions in
  `docs/CAOSCARE_OPERATIONS_SIMULATOR.md` §11; real resident data is never mixed in.
- **Queue:** owner master queue #166; active CO-008; next authorized bounded slice #153 slice 2; then #162
  dashboard + Home One page, #163 unified Aria gateway, #164 simulation clocks/detail, #165 Home One hardware,
  #168 staff work-queue follow-up.
- **Known open items:** owner/admin acknowledgement-role policy for alerts; release-control diff requirement;
  `docs/CAOSCARE_BLUEPRINT.md`, `CAOS_THESIS.md`, `ARIA_CONTRACT.md` still owner-authored placeholders; Room 214
  concise profile not applied; Midea AC Matter instability; far-field wake reliability; Aria identity text in
  four prompt builders; the browser still calls unauthenticated room-device endpoints.

### The current architecture in one picture

```
Resident speaks ("Hey Aria") or presses (screen / RF pendant)
  → ROOM NODE / FACILITY SERVER (EliteDesk): local wake listener (eMeet) → Room page (:3002) → backend (:8092)
  → OPENAI Realtime session (gpt-realtime-2.1-mini, WebRTC audio browser↔OpenAI; backend mints the key,
    assembles instructions, memory and tools)
  → Aria decides: answer / tool call
  → GOVERNED CAOSCARE SERVICE (one canonical layer): resident request, device command, status, research,
    reminder, self-code read (Room 214 only)
  → canonical action/task (StaffTask / Alert / device command) with ActorContext
  → RECEIPT (actor, authority, before/after, provider refs) + event log
  → staff / admin visibility (department workspaces, Operations, Live Operations)
  → learning / memory (trusted turns → facts, events, life story; continuity next session)
HOME ASSISTANT = the local device layer (lights, IR blaster, climate) with read-back; never the brain.
GITHUB = source of truth and the coordination/receipt channel (#166, PRs). LINODE = production caoscare.com.
SIMULATOR = the same service layer driven by explicitly simulated actors on scratch databases.
REAL FACILITY DATA = the `caoscare` dev DB and production DB; simulated rows never enter them.
```
