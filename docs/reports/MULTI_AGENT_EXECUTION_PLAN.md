# CAOSCARE Multi-Agent Execution Plan

_Last updated: 2026-08-23_

This is the standing parallel-work model for CAOSCARE. The goal is faster convergence without agents colliding, duplicating work, or changing the same subsystem from different directions.

## Core rule

Run multiple agents simultaneously **only on separate, clearly owned lanes**.

No two agents should modify the same production files or solve the same problem at the same time unless one is explicitly acting as reviewer/integrator.

Each implementation lane should use an isolated worktree/branch or other equally safe isolation. The primary `~/CAOSCARE.COM` worktree remains the integration/acceptance tree.

GitHub is the canonical shared state. Every lane reads the current directive, blueprint, reports, and relevant recent commits before working.

## Integration model

One lead/integration agent owns the primary worktree and is responsible for:

- assigning non-overlapping file/domain ownership
- preventing duplicate work
- reviewing each lane's diff
- resolving integration conflicts deliberately
- running cross-system verification after integration
- preserving the ~300-line/no-God-file rule
- checkpointing coherent integrated work to GitHub

Background agents do not silently merge, reset, rebase, deploy, delete data, or overwrite the primary worktree.

## Current parallel lanes

### Lane A — Voice fundamentals / regression hunt — HIGHEST PRIORITY

This lane exclusively owns the Realtime resident-voice stack while active.

The immediate goal is **not more tuning**. The goal is to determine why the simple early voice implementation worked better than the current system.

Work from fundamentals:

1. Identify the earliest/last known-good resident voice implementation and the best historical sessions where conversation was materially more reliable.
2. Compare that baseline against current Voice across:
   - Realtime session configuration
   - mic capture / WebRTC lifecycle
   - VAD
   - noise reduction / browser audio constraints
   - transcription model
   - greeting/playback handling
   - barge-in logic
   - prompt/preferences/personalization
   - memory/context injection
   - tools/tool gating
   - persistence/diagnostics
3. Build a regression matrix showing what was added/changed between the reliable baseline and current behavior.
4. Do not assume preferences are the cause merely because reliability declined after the system became more complex; prove the relevant change.
5. If practical, create an **isolated minimal-baseline comparison** on a separate branch/worktree/port that reproduces the early fundamentals without disturbing current main:
   - microphone input
   - one Realtime session
   - basic greeting/conversation
   - minimal prompt
   - no unnecessary preferences/tools/memory during the comparison
   - diagnostic logging sufficient to compare with current
6. A/B the minimal baseline against current with Michael as the human acceptance test.
7. Find the regression boundary before layering complexity back in.

The Voice lane must also forensically inspect the newest failed resident-room session where:
- UI stayed `LIVE · IDLE` / "Speak any time — I'm listening"
- visible transcript did not match Aria's apparent interpretation
- subsequent real speech stopped being registered

Do not randomly change several audio variables together.

Engineering loop:

`evidence -> one controlled change -> real-room test -> forensic report -> keep/revert`

If mic/audio-path instrumentation is still insufficient to prove where speech disappears, instrument that boundary before claiming a root cause.

### Lane B — Community / Admin operating model

Own the building-operating-system structure from `ADMIN_PRODUCT_BLUEPRINT.md` and the visual acceptance screenshots.

First task:
- organize Michael's uploaded screenshots into the dated visual-evidence folder
- produce the consolidated WORKING / PARTIAL / BROKEN / MISSING / WRONG-LOCATION gap report

Then implement coherent Admin foundations in blueprint order, avoiding Voice-owned files.

Primary fundamentals:
- organization/company prerequisite
- community/facility prerequisite
- one-community operating workspace
- Departments as clickable operational workspaces, not registry rows only
- Staff invite/access/role/department lifecycle
- first-class Front Desk module
- correct top-level navigation hierarchy

Do not claim success from Mongo/API counts when the operator cannot find/use the feature in the browser.

### Lane C — Scheduling / calendars / transportation

Own scheduling/calendar/transportation workflow files only; coordinate file ownership with the integration agent before edits.

Start by inventorying current implementation rather than rebuilding it.

Required product direction:
- actual dated calendar views
- click a day/date to see that day's items
- resident schedule and community/activity schedule share coherent source-of-truth rules
- transportation has an understandable visible lifecycle from request to slot/run/resource assignment to confirmation/completion
- requested time is not the same as booked/confirmed time
- driver and vehicle are distinct resources
- Front Desk can understand and act on pending/unslotted transportation

Use the existing partially built transportation/schedule systems where sound.

### Lane D — QA / architecture / integration review

Prefer this as a read-mostly review lane while A/B/C implement.

Responsibilities:
- watch for cross-lane contradictions
- enforce browser-visible acceptance criteria
- inspect materially changed production files for ~300-line compliance
- flag God-file growth
- verify no secrets or destructive operations
- maintain a dependency/conflict map
- review whether each lane still matches the shared blueprint/directive

Do not refactor broad shared foundations such as `backend/models.py` concurrently with A/B/C unless the lead explicitly schedules a dedicated integration window; that refactor touches too many imports and is conflict-prone.

## File ownership and collision rule

Before parallel agents edit code, the lead must state each lane's intended file/domain ownership.

If two lanes need the same file:
- one lane owns the edit
- the other supplies requirements or a patch suggestion only
- integration happens through the owner/lead

Do not let two agents race on `Admin.jsx`, shared models, shared auth, shared Realtime hooks, or other central files.

## Checkpoint cadence

Each lane can work in parallel, but GitHub checkpoints remain coherent.

Approximately every 30 minutes or at a meaningful milestone:
- lane reports what changed and what was verified
- integration agent reviews/integrates safe completed work
- focused + cross-system tests run as appropriate
- reports/state updated
- commit/push
- confirm primary EliteDesk integration tree and `origin/main` match

Do not push knowingly broken main merely to satisfy the clock.

## Fundamental product principle

CAOSCARE is not a collection of tabs. It is the operating system for a community/building.

The hierarchy and workflows must make sense from first setup through daily operation.

For Voice specifically: **simple reliable conversation is the foundation.** Preferences, memory, tools, and personalization are valuable only after the microphone -> Realtime -> turn detection -> understanding -> response loop is dependable.
