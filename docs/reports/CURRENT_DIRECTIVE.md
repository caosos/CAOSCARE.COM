# CAOSCARE Current Development Directive

_Last updated: 2026-08-23_

This is the current shared working directive for Michael, ChatGPT-Aria, and Claude Code. Read it from `origin/main` before substantial work.

## 1. Shared-state architecture

- **EliteDesk** is the only active CAOSCARE development machine.
- **GitHub `caosos/CAOSCARE.COM`** is the canonical source of truth, durable history, and shared state layer between Claude Code and ChatGPT-Aria.
- The laptop is only an SSH/browser/control device; do not maintain a separate CAOSCARE clone for it.
- Linode/public `CAOSCare.com` is out of current engineering scope unless Michael explicitly brings it back.

Normal loop:

`plan -> build -> test -> milestone -> document -> commit -> push -> continue`

## 2. Product blueprint governs Admin work

Before changing Admin/community information architecture, read:

`docs/reports/ADMIN_PRODUCT_BLUEPRINT.md`

That blueprint is the shared product map. Do not independently invent navigation, facility hierarchy, department behavior, staff access, Front Desk workflow, calendar behavior, or transportation workflow without reconciling the change against it.

Core hierarchy:

`Company / Organization -> Community / Facility -> Departments + Staff + Front Desk -> Residents + Rooms + Devices -> Requests + Tasks + Scheduling + Transportation + Activities + Menus + Reports`

The normal Admin experience is a **single-community operating workspace**. If a prerequisite object does not exist, show onboarding/setup rather than pretending the downstream operating system is configured.

## 3. Current engineering priority: Voice reliability

Voice remains the immediate priority before broad Admin/scheduling expansion.

Latest live failure reproduced in a resident room while UI showed `LIVE · IDLE` / "Speak any time — I'm listening":
- visible USER transcript and Aria's response did not semantically match
- after that, Michael continued speaking but no further speech was registered/responded to
- the listening-but-deaf defect therefore remains active

Known Voice problem areas:
- listening-but-deaf periods
- insufficient mic/audio-path instrumentation to prove where speech disappears
- `mark_resting` false activation; needs a code-level gate, not only prompt wording
- phantom/echo short turns
- visible `gpt-4o-transcribe` transcript vs native Realtime model audio understanding can diverge
- natural-pause / premature turn boundaries
- preserve genuine barge-in
- operational provenance: no fabricated facts may become durable side effects
- complete conversation persistence must continue to hold

Engineering method:

`one controlled change -> real-room test -> forensic report -> keep or revert`

Do not tune several audio variables at once. Michael performs the authoritative human acceptance test.

**Voice fundamentals rule:** the simple early resident-voice implementation appeared materially more reliable than the current complex stack. Do not respond by adding more tuning blindly. Identify the historical reliable baseline, compare it to current, build a regression matrix, and if useful A/B an isolated minimal baseline against current. Preferences, memory, tools, and personalization are secondary to a dependable microphone -> Realtime -> turn detection -> understanding -> response loop.

## 4. Standing multi-agent execution model

From now on, substantial CAOSCARE work should use multiple agents in parallel **on different lanes**, not multiple agents racing on the same subsystem.

Read and follow:

`docs/reports/MULTI_AGENT_EXECUTION_PLAN.md`

Standing rules:
- use isolated worktrees/branches or equivalent safe isolation for implementation lanes
- primary `~/CAOSCARE.COM` is the integration/acceptance tree
- one lead/integration agent coordinates file/domain ownership
- no two agents edit the same central production file concurrently
- background agents do not silently merge/reset/rebase/deploy/delete data
- each lane reads current GitHub state before working
- integration agent reviews and tests completed lane work before main is checkpointed

Current lanes are:
- **A: Voice fundamentals/regression hunt — highest priority**
- **B: Community/Admin operating model + screenshot/visual acceptance**
- **C: Scheduling/calendars/transportation**
- **D: QA/architecture/integration review — preferably read-mostly while A/B/C implement**

Do not run the broad `backend/models.py` split concurrently with these lanes unless the lead explicitly schedules a dedicated integration window; it is too cross-cutting and conflict-prone.

## 5. What comes after Voice

Once Voice reaches a meaningful reliability threshold:

1. Scheduling / calendars / appointments / transportation coordination.
2. Admin/community operating-system gaps according to `ADMIN_PRODUCT_BLUEPRINT.md`.
3. Other partially built systems.

Parallel Lane B/C may continue on clearly isolated, non-conflicting work while Voice Lane A is active; Voice remains the top acceptance priority.

Do not rebuild existing systems blindly. First inventory each area as:
- WORKING
- PARTIAL
- BROKEN
- MISSING
- DUPLICATED / WRONG LOCATION

Then finish coherent workflows end-to-end.

## 6. Browser-visible acceptance is required

Database/API success is not sufficient.

For every meaningful feature reported complete, provide:
- exact UI path
- what Michael should see
- what is clickable
- what action should succeed
- what persisted result should be visible afterward

If Mongo contains data but Michael cannot see/use it from the intended screen, it is not accepted.

Michael's screenshots are authoritative visual acceptance evidence and should be reconciled against the product blueprint.

## 7. Approximately 30-minute checkpoint cadence

Use approximately **30-minute development checkpoints**, or a meaningful milestone sooner.

At each checkpoint:
1. assess current work
2. run focused tests
3. if coherent and working, update relevant reports/state
4. commit
5. push `origin/main`
6. verify local HEAD == origin/main

Preferred report:

```text
CHECKPOINT
What changed:
What was verified:
Commit:
EliteDesk:
GitHub:
Status: IN SYNC
```

Thirty minutes is a checkpoint target, not permission to push broken code. Finish the smallest coherent unit first.

Michael grants standing approval for normal milestone commits/pushes of completed, tested, non-destructive work under this cadence. This does not authorize destructive Git operations, deployment, database mutation, or knowingly broken commits.

## 8. Safe EliteDesk / GitHub synchronization

At session start:
1. `git fetch origin`
2. inspect `git status`
3. compare local HEAD to `origin/main`

If clean + behind: fast-forward safely (`git pull --ff-only`).
If clean + current: proceed.
If dirty: preserve work; do not pull over it blindly.
If diverged/unexpectedly ahead: stop and report.

Never automatically reset, rebase, clean, force-pull, force-push, discard uncommitted work, or delete files merely to synchronize.

Desired state between completed blocks:

```text
ELITEDESK HEAD == GITHUB origin/main
working tree clean
```

## 9. Standing ~300-line architecture rule

Handwritten production code should normally remain at or below approximately **300 lines per file**.

This is a design ceiling to prevent God files, not an arbitrary line-count game.

A small overage is acceptable only when the file has one cohesive responsibility, splitting would reduce clarity, the overage is genuinely necessary, and the reason is explicitly noted.

Split by coherent responsibility into modules/services/helpers/domain logic/functions. Do not arbitrarily chop files merely to satisfy the number.

Normal exemptions include documentation, reports, informational/reference files, generated code/data, static datasets, and configuration/schema material where splitting reduces clarity.

At every checkpoint inspect materially changed handwritten production files and report any overage.

`backend/models.py` remains temporary technical debt, not precedent. Its prior exception is not a standing grandfather.

**There should be no God files in CAOSCARE.**

## 10. Local development stack status

The prior local data/auth outage is **resolved** and documented. It was not data loss.

Two hostname-resolution mismatches were fixed:
- frontend -> backend now uses explicit `127.0.0.1:8000`
- frontend dev service now has persistent supervised process management / dual-stack reachability

Do not reopen that incident unless current evidence shows a regression.

## 11. State/evidence safety

- inspect before mutating
- preserve uncommitted work
- do not delete bad operational records used as evidence without Michael approval
- do not expose secrets
- do not deploy merely to test local development
- do not reset/reseed databases without explicit evidence and approval

## 12. Working principle

The repo is the shared state layer.

Claude Code and ChatGPT-Aria should reconstruct the same project state from GitHub without Michael acting as a copy/paste relay.

GitHub gets updated at accomplishments, not at keystrokes.
