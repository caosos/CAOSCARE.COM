# Four-Claude Preservation Audit — CLAUDE 2 (Level 1 / Resident Aria / Pendant / ResidentEvent)

Date: 2026-09-09
Order stage: PRESERVE / INVENTORY (read-only)
Result: nothing modified; working tree already clean and pushed.

---

CLAUDE SESSION:
CLAUDE 2 — Lane: LEVEL 1 / RESIDENT ARIA / PENDANT / RESIDENTEVENT

CURRENT OBJECTIVE:
Level-1 resident-assistance path: RF transmission-semantics gate, activation
observability, ResidentEvent one-open-event + press-count integrity, real
auditable nurse paging/dispatch, inactivity-timer (mutual-silence) contract,
stale-request-resurrection fix + lifecycle timestamps, Aria self-knowledge
alignment. Currently in a live Room 214 acceptance-test cycle (backend on
:8000, parallel Level-1 acceptance frontend on :3001).

WORKTREE PATH:
/home/caoscare-1/CAOSCARE-LEVEL1-INTEGRATION
(Secondary/idle: /home/caoscare-1/CAOSCARE-LEVEL1 — my earlier branch
`claude/level1-breaktest`, clean.)

REPOSITORY ROOT:
/home/caoscare-1/CAOSCARE-LEVEL1-INTEGRATION (worktree of caosos/CAOSCARE.COM;
shared .git)

BRANCH:
claude/level1-integration

REMOTE TRACKING:
origin/claude/level1-integration

HEAD BEFORE PRESERVATION:
7fae156f73408e34377a89460b142d1222bde26b — "docs: PROJECT_STATE — Level-1
integration live on :8000 + parallel acceptance frontend on :3001"

AHEAD / BEHIND TRACKING:
0 ahead / 0 behind origin/claude/level1-integration (fully pushed, in sync).
Vs local `main` ref (d994331, = the known shared merge-base): 10 ahead / 0 behind.
Vs real remote main 9db5fd28 (from coordination record): local refs are stale
(origin/main still points at d994331; I have NOT fetched, to stay read-only).
Per the coordination record this branch is 10 ahead / 1 behind real main (the
"Repo hygiene: add backend smoke CI" commit is the 1 behind).

DIRTY FILES BEFORE:
NONE. `git status --short --branch` = `## claude/level1-integration...origin/claude/level1-integration`
only. `git diff`, `git diff --cached`, `git ls-files --others --exclude-standard`
all empty.

STAGED FILES:
NONE

UNSTAGED FILES:
NONE

UNTRACKED FILES:
NONE (before this audit report file was written)

COMPLETED WORK FOUND:
All already committed and pushed (7fae156). The 10 commits ahead of d994331:
- 38cc865 — Snapshot of the uncommitted ~/CAOSCARE.COM Level-1
  session-fencing/concurrency work, reproduced byte-for-byte (NOT authored by
  me — preservation of another lane's dirty tree as the base of this branch).
- d466367 — RF transmission-semantics gate (`rf_semantics.py`,
  `rf_matched_intake.py`) + activation observability (`activation_log.py`,
  `activation_timeline.py`) layered on 38cc865.
- 234d8ff — real auditable nurse paging/dispatch (`staff_dispatch.py`,
  `ai_escalation.py`); AI actions do not inflate physical press_count.
- d8b4dbd -> ab3243b — inactivity timer corrected to the two-flag
  mutual-silence state machine (`realtimeInactivityTimer.js` + handlers).
- 3951ef6 — stale-request-resurrection fix: CURRENT (open) vs HISTORY split +
  real lifecycle timestamps + facility-local time (`resident_requests.py`,
  `facility_local_time.py`, `realtime_tools_operations.py`,
  `realtimeOperationsTools.js`).
- 6608db0 — check_request_status wording: acknowledged/in_progress never
  authorise an arrival claim.
- a2db2bc, 7fae156 — PROJECT_STATE doc entries.
- 081ae13 — Aria self-knowledge: resident room = local node + speakerphone,
  not a wall-mounted tablet (`realtime_self_knowledge.py`, `ai.py`).

INCOMPLETE WORK FOUND:
NONE in this worktree. (There IS an open live Room 214 ResidentEvent
`alert_4da5fa59629a` from the last physical test — that is runtime data, not
code; see UNRESOLVED DEFECTS.)

GENERATED / TEMP FILES FOUND:
None tracked or untracked in the worktree. Session-local runtime artefacts
live only under the scratchpad (`/tmp/claude-1000/.../scratchpad/`):
`backend8000.log`, `level1-frontend-3001.log`, `bundle3001.js`,
`realtimeOperationsTools.js.served.bak`, `staging8002.log`. Not in the repo.

UNKNOWN-OWNERSHIP FILES:
NONE in this worktree.

COMMITS CREATED:
Prior to this audit: NONE. This audit adds exactly one commit — message
"audit: record four-Claude session state" — containing only this report file.
No cleanup commit of code was made; no existing dirty/incomplete code exists to
stage.

PUSH RESULT:
`git push origin claude/level1-integration` — this branch, fast-forward by one
commit (the audit-report commit). Exact SHAs are reported to Michael in the
delivery message and are visible in `git log` / GitHub.

REMOTE SHA AFTER PUSH:
Verified via `git ls-remote origin claude/level1-integration` immediately after
push; value reported to Michael in the delivery message.

REMAINING UNCOMMITTED FILES:
NONE.

WHY THEY REMAIN:
N/A — nothing uncommitted.

FILES / SYSTEMS THIS LANE OWNS (authored in d466367 -> 7fae156):
- backend/routes/rf_semantics.py, rf_matched_intake.py, rf_activation_intake.py
  (RF classification + matched-frame intake; the last was inherited-then-extended)
- backend/routes/activation_log.py, activation_timeline.py,
  activation_client_events.py (activation observability, db.activation_events)
- backend/routes/staff_dispatch.py, ai_escalation.py (real paging/dispatch,
  db.staff_dispatches)
- backend/routes/facility_local_time.py (facility-local timestamp labels)
- backend/routes/resident_requests.py — CURRENT vs HISTORY split +
  `_resident_safe_view` lifecycle fields
- backend/routes/realtime_tools_operations.py, realtime_aria_tools.py,
  realtime_tools.py — check_request_status/history tool schemas + wording
- backend/routes/realtime_self_knowledge.py — resident-room self-description
- backend/routes/resident_activation.py — semantic_class gate,
  activation_id_hint, alog hooks
- frontend/src/lib/realtimeInactivityTimer.js (+ realtimeConnection.js,
  realtimeMessageHandler.js, useRealtimeVoice.js integration) — mutual-silence
  timer
- frontend/src/lib/realtimeOperationsTools.js — check_request_status/history
  rendering
- backend/tests/test_rf_semantics.py, test_activation_observability.py,
  test_ai_escalation.py, test_request_status_lifecycle.py,
  test_level1_session_fencing.py, test_level1_concurrency_isolation.py;
  frontend __tests__/{realtimeInactivityTimer,requestStatusHistory,
  callForHelpWording,activationClient,...}.test.js
- docs/LEVEL1_BREAKTEST.md, LEVEL1_BREAK_TEST_2026-09-06.md, PROJECT_STATE.md
  (Level-1 entries), REPO_MAP.md (Level-1 additions)

FILES / SYSTEMS THAT MAY COLLIDE WITH ANOTHER LANE:
Large overlap with the conversation-substrate lane (`~/CAOSCARE.COM` @
`aria/conversation-substrate`, currently very dirty). This branch was *founded*
on a byte-identical snapshot of that lane's uncommitted tree (38cc865), so
nearly my whole diff-from-main coincides with their still-uncommitted work.
Files present in BOTH my committed set AND their dirty tree:
- Modified in both: backend/device_adapters.py, models.py,
  routes/{alert_lifecycle_events.py, kiosks.py, realtime.py,
  realtime_companion_prompt.py, realtime_device_tools.py,
  realtime_room_lease.py, resident_activation.py, rf.py},
  tests/test_resident_events.py,
  frontend/src/components/kiosk/RoomDevicePanel.jsx,
  frontend/src/lib/{realtimeDeviceTools.js, realtimeMessageHandler.js,
  useRealtimeVoice.js},
  frontend/src/lib/__tests__/restingEndCallGuard.test.js,
  frontend/src/pages/{Kiosk.jsx, RealtimeChatScreen.jsx, StaffDashboard.jsx}
- Committed in mine / UNTRACKED in theirs: backend/routes/{realtime_resident_session.py,
  resident_session_binding.py, rf_activation_intake.py},
  backend/tests/{test_level1_concurrency_isolation.py,
  test_level1_session_fencing.py},
  frontend/src/lib/{realtimeConnection.js, realtimeInactivityTimer.js,
  realtimeLeaseWatchdog.js, residentActivationPoll.js, activationClient.js,
  realtimeClimateControl.js}, several frontend __tests__ files,
  docs/LEVEL1_BREAK_TEST_2026-09-06.md
No collision with `claude/admin-operations` (clean, f144b21) or
`claude/resident-baselines` (clean, e787cc31).

CROSS-LANE DEPENDENCIES:
1. `claude/level1-integration` <= `aria/conversation-substrate` dirty tree: my
   base commit 38cc865 is that lane's uncommitted session-fencing/concurrency
   work. If that lane commits a *different* final form of the same files, mine
   and theirs will need semantic reconciliation (not a blind merge).
2. Runtime: RF bridge (`caos_rf_bridge.py`, pid 522046) posts to
   `http://127.0.0.1:8000` = MY Level-1 backend. Admin stack runs a second
   backend on `:8001` from `~/CAOSCARE-ADMIN/backend`. Both backends share the
   same Mongo `caoscare` DB — cross-stack alert mutation is possible (observed:
   the last Room 214 event was mutated by both).
3. `:3000` Admin frontend is pinned to `~/CAOSCARE-ADMIN/frontend` by a systemd
   `--user` drop-in (`caoscare-frontend-dev.service.d/worktree.conf`) authored
   by the Admin lane — I did not and must not touch it; I stood up the Level-1
   acceptance frontend on `:3001` instead.

_MINT STATUS:
PRESENT and COMMITTED in my worktree.
- Path: backend/routes/realtime_resident_session.py (`_mint(payload, lease)` at
  line 64; wrapper `create_resident_session(payload)` at line 22).
- git status here: clean/tracked. Introduced by 38cc865 (reproduced verbatim
  from the ~/CAOSCARE.COM dirty tree), unchanged since; no commit of mine edits
  `_mint` itself.
- Ownership: originates in the conversation-substrate lane — in `~/CAOSCARE.COM`
  this exact file is currently UNTRACKED (`??`), i.e. the "mid-extraction,
  uncommitted `_mint`" the directive names. My copy is a preserved earlier
  state of it.
- Completeness: the version in my tree is functionally complete — verified live
  this session (`POST /api/realtime/session` mints an `ek_...` ephemeral key;
  room-bound path claims a lease, binds activation, returns `_caos` config incl.
  `aria_companion_timeout_sec`).
- Depends on it: conversation-substrate Layer B/C/E assembly (per directive);
  my Level-1 realtime session path; the :3001 acceptance frontend.
- I did NOT commit `_mint` from this lane as canonical, did NOT re-extract, did
  NOT modify or delete it. The conversation-substrate lane's copy may have
  diverged from mine and is theirs to finalize.

REALTIME_COMPANION_PROMPT STATUS:
Touched by this branch's HISTORY but not by my authored work. Only change on
`main..HEAD` is in 38cc865 (inherited snapshot): a 6-line addition to the
climate-tool guidance ("`get_room_status` reports the AC/thermostat's TARGET
setting and the room's OWN current temperature as two separate things..."). The
flagged stale style is UNTOUCHED by me — still at:
- line 44: `"Your name is Aria - a calm, warm, deeply present companion. You live in "`
  (the "lives in the wall" phrasing)
- line 52: `"Speak like a real person - soft, unhurried, ..."`
The conversation-substrate lane currently has `realtime_companion_prompt.py`
modified (dirty) — that lane is actively editing this file. Per directive I did
NOT fix any of it.

TESTS ALREADY RUN (this session, before the audit):
- backend (each in its own pytest process, staging backend on :8002,
  CAOSCARE_TEST_HOOKS=1): test_request_status_lifecycle.py,
  test_resident_events.py, test_ai_escalation.py
- frontend: src/lib/__tests__/requestStatusHistory.test.js (via the :3001
  worktree with node_modules symlinked from ~/CAOSCARE.COM/frontend)
- import/build smokes: `_build_tools()`, `_build_aria_tools()`,
  `_system_self_knowledge()`, `_build_companion_instructions(None)`
- No pytest run touched real Room 214 hardware.

TEST RESULTS:
- test_request_status_lifecycle.py — 1 passed
- test_resident_events.py — 1 passed
- test_ai_escalation.py — 1 passed
- requestStatusHistory.test.js — 5 passed
- All import/build smokes passed (stale self-knowledge string absent, new
  wording present; companion instructions build at 16,523 chars).
- Not re-run in this audit (read-only). Known pre-existing unrelated failures:
  tests iter5-8 fail at `_login` (`admin@caoscare.com`/`admin1234` -> 401) —
  missing demo credentials, unrelated to Level-1.

KNOWN RUNTIME DEPENDENCIES:
- Level-1 backend: :8000, pid 607118, cwd ~/CAOSCARE-LEVEL1-INTEGRATION/backend,
  `{"ok":true,"db":"up"}`, loads backend/.env (Mongo
  `mongodb://localhost:27017/caoscare`, `CAOSCARE_ENABLE_DEMO_SEED=false`).
- Level-1 acceptance frontend: :3001, pid 610968, cwd
  ~/CAOSCARE-LEVEL1-INTEGRATION/frontend, craco dev server, env
  `REACT_APP_BACKEND_URL=http://127.0.0.1:8000` (baked in bundle), `node_modules`
  = symlink -> ~/CAOSCARE.COM/frontend/node_modules. Kiosk URL for Michael:
  `http://192.168.1.151:3001/kiosk/kio_dc8c06a19608`.
- RF bridge: `caos_rf_bridge.py` pid 522046, `CAOS_API_URL=http://127.0.0.1:8000`,
  `CAOS_KIOSK_ID=kio_9d5247d7ff59` (transport identity; resident resolved by RF
  fingerprint), rtl_433 child on 319.5 MHz, polling (last poll ~03:02Z).
- MongoDB `caoscare` @ localhost:27017 — shared with the Admin `:8001` backend.
- OpenAI Realtime (`gpt-realtime`) via OPENAI_API_KEY in backend/.env — verified
  minting.

KNOWN UNRESOLVED DEFECTS:
1. Room 214 event `alert_4da5fa59629a` (Helen, res_81b72be1e8b5) is OPEN —
   `status=active`, `press_count=6`, `aria_state=dormant`, `event_log=[]`. It
   must be resolved by Michael via the Admin panel before a clean acceptance
   run. I have NOT mutated it.
2. Aria wake for that event never occurred because the physical test browser was
   on `:3000`->`:8001` (Admin stack), not `:3001`->`:8000` (Level-1). Not a
   Level-1 behavior failure.
3. Room 214 later incident: waking laptop + clicking an already-open
   `localhost:3000/kiosk/...` tab while Aria was active produced "Conversation
   already has an active response in progress..."; exact causality UNRESOLVED —
   no telemetry-backed diagnosis; do not label it.
4. Two backends (:8000 Level-1, :8001 Admin) on one shared `caoscare` DB —
   cross-stack alert contamination hazard.
5. Room 214 AC actual state unresolved (Home Assistant entity was unavailable)
   — do not fabricate. Desk lamp + overhead light verified OFF by HA read-back.

DO-NOT-CHANGE INVARIANTS (in force in this lane):
- RF semantics: switch5 CLOSED = help_press (only class that may activate
  Resident Aria); all-switches-OPEN + short burst = supervisory -> telemetry
  only; tamper/battery/unknown -> telemetry only.
- ResidentEvent: one resident = one open event; real repeated physical presses
  coalesce into it; press_count = actual physical activations; AI/escalation/
  call_for_help must not inflate press_count.
- Five-minute rule: NOT a fixed conversation cap. Resident or Aria speaking ->
  no timer; either starts speaking -> cancel silence timer; both silent ->
  fresh 5-min countdown; 5 continuous minutes of mutual silence -> end.
- Runtime separation: :3000 Admin FE / :3001 Level-1 acceptance FE / :8000
  Level-1 BE / :8001 Admin BE — do not cross the stacks.
- Ordinary pytest must not actuate real Room 214 hardware; only explicit
  `real_hardware` tests may.
- Personality/character engine: PAUSED — no work on it; do not fix stale style
  in realtime_companion_prompt.py yet.
- `_mint` / conversation-substrate extraction: do not commit from this lane as
  canonical, re-create, delete, or overwrite.

NEXT SAFE ACTION:
Hold. Nothing to preserve or commit in this lane (clean, pushed at 7fae156
before this audit-report commit). Await the coordinating ChatGPT thread's
four-report comparison and integration order. Separately (runtime, not code):
when Michael confirms `alert_4da5fa59629a` is resolved via the Admin panel,
re-verify Helen has zero open ResidentEvents / Room 214 active-emergency null /
no Aria lease, then hand him `http://192.168.1.151:3001/kiosk/kio_dc8c06a19608`
for a clean one-press acceptance test.

FINAL GIT STATUS:
`## claude/level1-integration...origin/claude/level1-integration` — working tree
clean apart from this audit report file, which is committed on its own.

FINAL HEAD:
See PUSH RESULT below (audit-report commit SHA).

SESSION AUDIT COMPLETE

---

## Other worktrees observed (read-only, for the coordinator)

| Worktree | Branch | HEAD | State |
|---|---|---|---|
| /home/caoscare-1/CAOSCARE.COM | aria/conversation-substrate | b0aacb0 | DIRTY, [ahead 9]. ~20 modified + ~16 untracked files (the Level-1 session-fencing/concurrency body + `_mint` extraction, still uncommitted). |
| /home/caoscare-1/CAOSCARE-ADMIN | claude/admin-operations | f144b21 | clean, pushed |
| /home/caoscare-1/CAOSCARE-CLAUDE | claude/resident-baselines | e787cc31 | clean, pushed |
| /home/caoscare-1/CAOSCARE-LEVEL1 | claude/level1-breaktest | 9aa0e0d | clean, pushed (my earlier branch, superseded by level1-integration) |
| /home/caoscare-1/CAOSCARE-LEVEL1-INTEGRATION | claude/level1-integration | 7fae156 | clean, pushed (this lane) |

Only `aria/conversation-substrate` (~/CAOSCARE.COM) is dirty.
