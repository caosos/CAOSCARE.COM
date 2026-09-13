# Four-Claude Preservation Audit — aria/conversation-substrate

Generated in response to the "CAOSCARE — FOUR-CLAUDE PRESERVATION AUDIT"
coordination directive, 2026-09-09. Read-only inventory; no merges, rebases,
resets, stashes, or integration performed. This file is the only artifact
created by this audit pass.

CLAUDE SESSION:
Not one of the four known lanes (`claude/admin-operations`,
`claude/level1-integration`, `claude/level1-breaktest`,
`claude/resident-baselines`). This worktree's branch is
`aria/conversation-substrate` — a fifth lane not named in the coordination
record. Using a task-based identity per instruction: **aria-conversation-substrate**.

Additionally — important finding, see "CROSS-LANE DEPENDENCIES" below — this
branch shows commits from **two distinct Claude-Session IDs**, not one:
`session_0117e2CCkVHgEoPPNWbzv3R8` (this session) and
`session_01UFCUPkt8RJScGtYJ3pUtGs` (a different session, four commits, all
after this session's most recent prior commit, all before this audit began).

CURRENT OBJECTIVE:
Aria conversation substrate — Layers B (cross-session continuity), C
(runtime conversation-vs-intent state), E (operational-state authority) —
plus their integration into `_build_companion_instructions` and the resident
session-mint path. Most recently: Layer C implementation, an incident fix
(test suite touched real Room 214 hardware), then (by the other session on
this branch) reviewer-driven corrections to Layers B/C and a Layer-E speak-through
for `check_request_status`/`request_staff_help`.

WORKTREE PATH:
/home/caoscare-1/CAOSCARE.COM

REPOSITORY ROOT:
/home/caoscare-1/CAOSCARE.COM

Other worktrees observed on this machine (`git worktree list --porcelain`):
- /home/caoscare-1/CAOSCARE-ADMIN → claude/admin-operations @ f144b21
- /home/caoscare-1/CAOSCARE-CLAUDE → claude/resident-baselines @ e787cc3
- /home/caoscare-1/CAOSCARE-LEVEL1 → claude/level1-breaktest @ 9aa0e0d
- /home/caoscare-1/CAOSCARE-LEVEL1-INTEGRATION → claude/level1-integration @ 7fae156

BRANCH:
aria/conversation-substrate

REMOTE TRACKING:
origin/aria/conversation-substrate

HEAD BEFORE PRESERVATION:
b0aacb0da4d6884f6f65ca2cd603f5a195c46ce5 ("Record Step 3 (_mint wiring) blocked
on Level 1 extraction")

AHEAD / BEHIND TRACKING:
ahead 9, behind 0 (`git status --short --branch`:
`aria/conversation-substrate...origin/aria/conversation-substrate [ahead 9]`)

DIRTY FILES BEFORE:
19 modified (unstaged) + 18 untracked = 37 dirty paths. Full lists below.

STAGED FILES:
None. `git diff --cached --stat` is empty.

UNSTAGED FILES (modified, tracked):
```
backend/device_adapters.py
backend/models.py
backend/routes/alert_lifecycle_events.py
backend/routes/kiosks.py
backend/routes/realtime.py
backend/routes/realtime_companion_prompt.py
backend/routes/realtime_device_tools.py
backend/routes/realtime_room_lease.py
backend/routes/resident_activation.py
backend/routes/rf.py
backend/tests/test_resident_events.py
frontend/src/components/kiosk/RoomDevicePanel.jsx
frontend/src/lib/__tests__/restingEndCallGuard.test.js
frontend/src/lib/realtimeDeviceTools.js
frontend/src/lib/realtimeMessageHandler.js
frontend/src/lib/useRealtimeVoice.js
frontend/src/pages/Kiosk.jsx
frontend/src/pages/RealtimeChatScreen.jsx
frontend/src/pages/StaffDashboard.jsx
```

UNTRACKED FILES:
```
backend/routes/realtime_resident_session.py
backend/routes/resident_session_binding.py
backend/routes/rf_activation_intake.py
backend/tests/test_level1_concurrency_isolation.py
backend/tests/test_level1_session_fencing.py
docs/LEVEL1_BREAK_TEST_2026-09-06.md
frontend/src/lib/__tests__/activationClient.test.js
frontend/src/lib/__tests__/callForHelpWording.test.js
frontend/src/lib/__tests__/realtimeConnectionRecovery.test.js
frontend/src/lib/__tests__/realtimeInactivityTimer.test.js
frontend/src/lib/__tests__/realtimeStopReason.test.js
frontend/src/lib/__tests__/residentRecovery.test.js
frontend/src/lib/activationClient.js
frontend/src/lib/realtimeClimateControl.js
frontend/src/lib/realtimeConnection.js
frontend/src/lib/realtimeInactivityTimer.js
frontend/src/lib/realtimeLeaseWatchdog.js
frontend/src/lib/residentActivationPoll.js
```

COMPLETED WORK FOUND:
On this branch's committed history (not dirty — already in HEAD, listed for
completeness since the audit asks what's here):
- Layer E (operational-state authority): `aria_operational_state.py`,
  `realtime_operational_context.py` — commit `7050710`.
- Layer B (cross-session continuity): `aria_continuity.py`, `aria_time.py` —
  commit `6f0f876`, corrected in `0c95352` (index moved out of hot path;
  unfinished-flagging no longer defaults an unknown reason to "unfinished").
- Layer C (runtime conversation-vs-intent state): `aria_conversation_state.py`
  — commit `a03d5b5`, refined in `2f25487` (positive tool-call evidence
  required for `awaiting_required_detail`; defers to Layer E via `ref`).
- Incident fix (real-hardware test isolation): `backend/pytest.ini`
  `real_hardware` marker, excluded by default — commit `adf95ba`.
- Layer-E speak-through for resident-request tools: `aria_request_status.py`
  — commit `b864bfa`.
- All of the above verified importing cleanly and passing their own test
  files as of each commit's own message; re-verified together just now
  (see TEST RESULTS below) — 20 passed, 1 pre-existing skip.

INCOMPLETE WORK FOUND:
- **`_mint` / resident session-mint path** — see `_MINT STATUS` below. B/C/E
  wiring is written and correct inside the untracked `_mint`, but
  deliberately uncommitted by both sessions that have touched this branch,
  because the file it lives in belongs to the in-flight Level 1 `_mint`
  extraction.
- Substrate Layers D (subject-triggered memory retrieval) and F (capability
  truth in context) — designed in `docs/ARIA_SUBSTRATE_IMPLEMENTATION_PLAN.md`,
  not started, per explicit directive already on record to defer them.
- `docs/PROJECT_STATE.md` notes one remaining frontend hook for Layer E:
  `realtimeOperationsTools.js` needs to forward `data.spoken` for
  `check_request_status`/the dedupe branch — explicitly held for the
  `useRealtimeVoice.js` refactor to land first.

GENERATED / TEMP FILES FOUND:
None identified. No `__pycache__`, `.pyc`, build output, or coverage
artifacts appear in `git status` (already gitignored) or in the untracked
list above — everything untracked is deliberate, named source or test code.

UNKNOWN-OWNERSHIP FILES:
None outright unknown. Every dirty path was traced to a named lane by
reading its diff/docstring, not guessed from filename:
- Untracked backend files (`realtime_resident_session.py`,
  `resident_session_binding.py`, `rf_activation_intake.py`,
  `test_level1_*.py`, `LEVEL1_BREAK_TEST_2026-09-06.md`) — Level 1 lane
  (`claude/level1-integration` / `claude/level1-breaktest`), by content:
  activation fencing, RF burst classification, session binding.
- Modified backend files (`device_adapters.py`, `models.py`,
  `alert_lifecycle_events.py`, `kiosks.py`, `realtime.py`,
  `realtime_device_tools.py`, `realtime_room_lease.py`,
  `resident_activation.py`, `rf.py`, `test_resident_events.py`) — Level 1
  lane. Read directly: `alert_lifecycle_events.py` adds session/activation
  fencing (`409` on stale session events) exactly matching the untracked
  `test_level1_session_fencing.py`; `kiosks.py` fixes zone/room routing so a
  room-scoped kiosk can never surface another room's alert; `models.py` adds
  an `hvac_mode` device capability (real Midea AC work).
- Untracked/modified frontend files — frontend voice-refactor lane. Read
  file-header docstrings directly: `activationClient.js` (Level 1
  observability breadcrumbs), `realtimeClimateControl.js` (AC/thermostat
  split, same pattern as the existing light-control split),
  `realtimeConnection.js` / `realtimeInactivityTimer.js` /
  `realtimeLeaseWatchdog.js` / `residentActivationPoll.js` (named connection/
  timer/watchdog/poll modules being extracted out of `useRealtimeVoice.js`,
  which is the 319-line diff in the modified list — consistent with the
  extraction target).
- `realtime_companion_prompt.py`'s working-tree diff (the only substrate
  file still dirty) is a single unrelated hunk — a `get_room_status`
  climate-context sentence — that neither this session nor
  `session_01UFCUPkt8RJScGtYJ3pUtGs` has ever staged into a substrate commit
  (confirmed via `git add -p` hunk selection in this session's own history).
  It belongs to whichever lane is doing the real-AC/climate work
  (`test_climate_control.py`'s lane) and should be committed by that lane.

None of the above required guessing from filename alone; each was confirmed
by reading its diff or header comment.

COMMITS CREATED:
NONE in this audit pass (read-only inventory only; see "AFTER REPORTING —
STOP" below). Prior to this audit, in this same session (not created just
now): `a03d5b5`, `adf95ba` (this session); `2f25487`, `b864bfa`, `0c95352`,
`b0aacb0` (the other session on this branch, `session_01UFCUPkt8RJScGtYJ3pUtGs`
— already on HEAD before this audit started, not created by this report).
This audit itself will produce exactly one commit: this report file, per the
delivery instruction, staged and committed separately from all of the above.

PUSH RESULT:
Pending — performed immediately after this file is written and committed,
per the delivery instruction. See chat for the resulting SHA.

REMOTE SHA AFTER PUSH:
See chat message following this report (delivery instruction requires
reporting this separately, not inside the file).

REMAINING UNCOMMITTED FILES:
All 37 dirty paths listed above under UNSTAGED/UNTRACKED remain exactly as
found — untouched by this audit.

WHY THEY REMAIN:
- They belong to the in-flight Level 1 lane (`claude/level1-integration` /
  `claude/level1-breaktest`) and the frontend voice-refactor lane, not to
  this branch's substrate objective.
- The audit directive's absolute stop rules prohibit `git add .`/`git add -A`,
  claiming another lane's work, or committing to make status clean.
- The one substrate-adjacent dirty file (`realtime_companion_prompt.py`'s
  climate hunk) is a single unrelated hunk inside an otherwise-clean file;
  two prior commits on this branch already demonstrated the discipline of
  excluding it via `git add -p` rather than sweeping it in.

FILES / SYSTEMS THIS LANE OWNS:
- `backend/routes/aria_operational_state.py` (Layer E)
- `backend/routes/realtime_operational_context.py` (Layer E render)
- `backend/routes/aria_continuity.py`, `backend/routes/aria_time.py` (Layer B)
- `backend/routes/aria_conversation_state.py` (Layer C)
- `backend/routes/aria_request_status.py` (Layer-E speak-through)
- `backend/pytest.ini` (real_hardware test marker/gate)
- Corresponding test files: `test_aria_operational_state.py`,
  `test_aria_continuity.py`, `test_aria_conversation_state.py`,
  `test_companion_prompt_substrate.py`, `test_substrate_layers_integration.py`,
  `test_request_tools_speak_from_layer_e.py`, `test_light_control.py` /
  `test_climate_control.py` (marker-only edits, not full ownership — those
  two files' base content belongs to the real-hardware/climate lane).
- Shared additions inside `backend/server.py` (router registration for the
  three new `aria_*` routers + `ensure_indexes()` call in `lifespan`) and
  `backend/routes/resident_requests.py` (Layer-E fields added to
  `_resident_safe_view`, additive only).
- Documentation: `docs/ARIA_SUBSTRATE_IMPLEMENTATION_PLAN.md`,
  `docs/ARIA_LANE_ONBOARDING.md`, `docs/ROOM_214_CONVERSATION_EVIDENCE_2026-09-08.md`.

FILES / SYSTEMS THAT MAY COLLIDE WITH ANOTHER LANE:
- `backend/routes/realtime_companion_prompt.py` — this lane owns the block-
  order wiring (`_build_companion_instructions` signature and B→C→E
  assembly); a different, not-yet-identified lane owns an unrelated hunk
  already sitting in this same file's working tree (the `get_room_status`
  climate sentence). Same file, two independent owners of different hunks —
  a real collision risk if either lane runs a broad `git add`.
- `backend/routes/realtime.py` and `backend/routes/realtime_resident_session.py`
  — the canonical session-mint path is being extracted by Level 1
  (`realtime.py`'s `create_session` reduced to a passthrough;
  `realtime_resident_session.py` holds the new `_mint`), and this lane's
  Layer B/C/E wiring already lives inside that same untracked `_mint`
  function (added across two Claude sessions on this branch, never
  committed, always attributed to Level 1's extraction — see `_MINT STATUS`).
  Whoever commits `_mint` first effectively also commits this lane's
  session-mint integration; that commit must not be attributed solely to
  Level 1 or solely to substrate.
- `backend/models.py`'s `hvac_mode` capability addition and
  `test_climate_control.py`/`test_light_control.py`'s base content — real
  Room 214 AC/light hardware work, same physical devices this lane's
  incident fix (`adf95ba`) also touched (as a bystander, not a feature).

CROSS-LANE DEPENDENCIES:
- **Hard dependency**: substrate Layer B/C/E context assembly cannot reach
  the live resident session until Level 1's `_mint` extraction is committed
  (see `_MINT STATUS`).
- **Confirmed, not hypothetical, multi-session finding**: this branch's git
  log shows two distinct `Claude-Session:` trailers —
  `session_0117e2CCkVHgEoPPNWbzv3R8` (this session; commits `a03d5b5`,
  `adf95ba`) and `session_01UFCUPkt8RJScGtYJ3pUtGs` (commits `2f25487`,
  `b864bfa`, `0c95352`, `b0aacb0`, all dated 2026-09-09 00:08–00:15, i.e.
  after this session's prior commits and before this audit). They did not
  conflict — each commit applied cleanly on top of the last, and the other
  session's `PROJECT_STATE.md` entries show it independently reached the
  same conclusion this session reached (do not commit `_mint`, report the
  dependency instead) — but this means **the coordination directive's
  four-worktree model is incomplete**: at least one branch
  (`aria/conversation-substrate`) has been operated on by two separate
  Claude Code sessions sharing one worktree, sequentially, not just four
  parallel worktree-isolated lanes. Flagging this explicitly for the
  coordinating thread rather than resolving or guessing which session is
  "authoritative."

_MINT STATUS:
- Path: `backend/routes/realtime_resident_session.py` (untracked, new file)
  holds `_mint` and `create_resident_session`. `backend/routes/resident_session_binding.py`
  (untracked) holds `validate_activation`/`bind_activation`, imported by it.
  `backend/routes/realtime.py` (modified, uncommitted) has its own
  `create_session` reduced to `return await create_resident_session(payload)`.
- Ownership: Level 1 lane (`claude/level1-integration` and/or
  `claude/level1-breaktest`), by content — activation fencing, room-lease
  claim/reuse, RF burst grouping all live alongside `_mint` in these files,
  matching the untracked `test_level1_session_fencing.py` /
  `test_level1_concurrency_isolation.py` also present in this worktree.
- Dependency: this lane's Layer B/C/E wiring (`resolve_operational_state`,
  `resolve_continuity`, `resolve_conversation_state` calls, threaded into
  `_build_companion_instructions(...)` and `_caos.context`) is already
  written inside this untracked `_mint` — added across both Claude sessions
  on this branch, verified present by direct source read, never committed
  by either.
- Completeness: the wiring itself is complete and self-consistent (verified
  by `import server` succeeding and by the substrate test suite passing
  against the current tree). What's incomplete is Level 1's own extraction
  around it — not something this audit should judge or finish.
- Action taken: NONE. Not committed, not rewritten, not deleted, not
  assumed. Left exactly as found, per the directive's explicit instruction
  on this exact dependency.

REALTIME_COMPANION_PROMPT STATUS:
Touched — by this lane, across three commits (`a03d5b5`, `2f25487`, and the
original Layer E commit `7050710` before this session started), for the
`_build_companion_instructions` signature and B→C→E block-order assembly.
Also carries one unrelated, never-committed hunk (the `get_room_status`
climate-context sentence) belonging to a different lane — see "FILES /
SYSTEMS THAT MAY COLLIDE" above. The stale-persona wording the coordination
directive flagged ("calm, warm, deeply present," "soft, unhurried," "lives
in the wall") is present in this file and was NOT touched by this lane —
personality/character-engine work is paused per the directive and this
lane's own scope was context assembly, not persona rewrite.

TESTS ALREADY RUN:
This session, just now (post-audit-inventory, pre-report, read-only w.r.t.
git — writes only to the test database with cleanup, no real hardware):
`pytest tests/test_aria_conversation_state.py tests/test_aria_operational_state.py
tests/test_aria_continuity.py tests/test_companion_prompt_substrate.py
tests/test_substrate_layers_integration.py tests/test_request_tools_speak_from_layer_e.py
tests/test_level1_session_fencing.py tests/test_level1_concurrency_isolation.py`
plus `python -c "import server"`.

Earlier (per each commit's own message, not re-verified line-by-line here):
`a03d5b5` — 11/1 skip; `adf95ba` — level1 fencing 2/2, full-suite spot-check
of unrelated pre-existing HTTP-integration failures; `2f25487` — 17/1 skip;
`b864bfa` — 19/1 skip; `0c95352` — 20/1 skip.

TEST RESULTS:
`import server` — OK. Combined substrate + Layer-E-speak-through + Level 1
fencing suite — **20 passed, 1 skipped** (the skip is the pre-existing
`/api/aria/operational-state` HTTP endpoint test, pending a dev-backend
reload not yet coordinated — documented since the Layer E commit, not new).
No failures, no regressions detected against the current combined HEAD.

KNOWN RUNTIME DEPENDENCIES:
- MongoDB at `mongodb://localhost:27017`, db `caoscare` (`backend/.env`).
- `backend/.venv` — this session's Python environment; `python`/`pip` are
  not on PATH directly, only `python3`/the venv.
- Shared dev backend on :8000 has no reload flag — the three new `aria_*`
  inspection endpoints (`operational-state`, `continuity`,
  `conversation-state`) are wired and unit-tested but not live until it's
  restarted, coordinated across lanes (not done unprompted).
- Real Home Assistant integration for Room 214 (`HA_BASE_URL`/`HA_TOKEN`) —
  real Matter bulbs + Midea AC, now gated behind the `real_hardware` pytest
  marker (excluded by default) after last night's incident.

KNOWN UNRESOLVED DEFECTS:
- Real Room 214 AC (`dev_fa83aeda0cd4`) power state is physically
  unconfirmed — Home Assistant reported the entity `unavailable` when this
  session attempted to verify/turn it off during the incident remediation;
  not re-attempted repeatedly against real hardware without a human check.
  Full detail in `docs/PROJECT_STATE.md`, "2026-09-09 — Incident."
- `db.smart_devices.state` does not get overwritten on a failed/unverified
  Home Assistant command — it silently keeps the last-known value, which
  can read as stale/wrong (see same PROJECT_STATE incident entry). Not
  fixed; flagged as needing a real decision, not a late-night patch.
- `RESUMED_AFTER_TURNS` (Layer C) is a coarse fixed-turn-count heuristic for
  "the conversation moved on" — no semantic topic-change detection.
- Pre-existing, not this lane's: `tests/test_resident_events.py::test_resident_event_model`
  fails at current HEAD too (RF-intake classifier lane, tracked in
  `docs/LEVEL1_BREAK_TEST_2026-09-06.md`), and a large block of
  `backend_test.py`/`iter5_test.py`/`iter8_test.py`/`test_room_device_isolation.py`
  HTTP-integration tests fail/error against an unreachable or stale shared
  dev server — both conditions pre-date this audit and this lane.

DO-NOT-CHANGE INVARIANTS:
Everything listed under "KNOWN LEVEL-1 INVARIANTS," "REAL HARDWARE TEST
INVARIANT," "ADMIN / OPERATIONS INVARIANTS," and "PERSONALITY / CHARACTER
ENGINE" in the coordination directive is treated as binding by this lane.
Specifically observed as already respected in this branch's own code:
- RF semantics (`switch5` closed = help press; all-open short burst =
  supervisory) — enforced in the untracked `rf_activation_intake.py`
  (Level 1, not this lane; read, not modified).
- Five-minute mutual-silence rule (not a fixed conversation timer) —
  implemented in the untracked `frontend/src/lib/realtimeInactivityTimer.js`
  (frontend refactor lane; read, not modified) per its own header comment
  citing the Room 214 forensics.
- Real-hardware test isolation — this lane's own incident fix (`adf95ba`),
  re-verified still in effect (`pytest.ini` present, markers intact).
- Personality/character-engine work — untouched by this lane; the stale
  `realtime_companion_prompt.py` persona wording flagged in the directive
  was read, not edited.

NEXT SAFE ACTION:
Wait for the coordinating thread's comparison of all reports. This lane's
own next planned step (not started, listed here only for visibility, not
authorized by this audit): once Level 1 commits its `_mint` extraction,
add a mint-path integration test asserting `create_resident_session`/`_mint`
assembles Layer B+C+E into `instructions` and `_caos.context` together.
Separately and independently of lane sequencing: a human should physically
check the real Room 214 AC's actual power state.

FINAL GIT STATUS:
Identical to "DIRTY FILES BEFORE" — this audit made no working-tree changes
prior to writing this report file itself. After this report is written,
staged, and committed (per the delivery instruction), the only change to
`git status` will be this new file moving from untracked to committed; all
37 pre-existing dirty paths remain exactly as found.

FINAL HEAD:
Will be the commit created for this report file (SHA reported in chat per
the delivery instruction, not duplicated here since the file is written
before that commit exists).

SESSION AUDIT COMPLETE
