# CAOSCARE Current Development Directive

_Last updated: 2026-08-23_

This file is the current shared working directive for Michael, ChatGPT-Aria, and Claude Code.
When Michael says to execute the current directive, read this file from `origin/main` and follow it.

## 1. Current architecture

- **EliteDesk** is the only active CAOSCARE development machine.
- **GitHub `caosos/CAOSCARE.COM`** is the canonical source of truth, durable project history, and shared state layer between Claude Code and ChatGPT-Aria.
- The laptop is not part of repository synchronization. It is only an optional SSH/browser/control device.
- Linode/public `CAOSCare.com` hosting is not an active engineering priority right now. Do not spend development time on deployment/public hosting unless Michael explicitly brings it back into scope.

The normal source-control flow is:

`EliteDesk -> test -> milestone -> document -> commit -> push GitHub`

GitHub is authoritative for completed verified work. The EliteDesk may temporarily be ahead only while active work is genuinely in progress.

## 2. Current product priority

Work in this order:

1. **Get resident voice reliable.**
2. **Scheduling / calendars / appointments / transportation coordination.**
3. **Finish and integrate the other partially built CAOSCARE systems.**

Do not jump into unrelated new feature areas while Voice still has fundamental known failures.

Before Voice work can continue effectively, first finish diagnosing/restoring the current local outage affecting:

- Google sign-in
- residents/rooms appearing empty
- kiosks appearing empty
- requests load failures
- pendants load failures

Do not recreate or reseed data merely because the UI is empty. Prove where the existing data is and restore the correct runtime/data path.

## 3. Voice engineering method

Known active Voice problem areas include:

- `mark_resting` false activation
- listening-but-deaf periods
- insufficient mic/audio-path instrumentation
- phantom/echo speech
- visible transcription vs Realtime model audio understanding
- natural pauses / premature turn completion
- preservation of genuine barge-in
- operational provenance / no fabricated facts
- complete conversation persistence

Use controlled experiments:

`one controlled change -> real-room test -> forensic report -> keep or revert`

Do not randomly tune several audio variables simultaneously.

Michael performs the authoritative human acceptance test.

When Voice passes a meaningful reliability threshold, move to scheduling/calendars. Do **not** rebuild those systems from scratch. First inspect the existing implementation and classify each piece as:

- WORKING
- PARTIAL
- BROKEN
- MISSING
- DUPLICATED

Then finish the existing architecture coherently.

## 4. Approximately 30-minute checkpoint cadence

Use approximately **30-minute development checkpoints**.

At roughly every 30 minutes **or** whenever a meaningful milestone is completed, whichever comes first:

1. assess the current work
2. run the appropriate focused tests
3. if the state is coherent and working:
   - update `docs/reports/INDEX.md`, `docs/PROJECT_STATE.md`, and/or a relevant report when materially useful
   - commit the completed work
   - push to `origin/main`
   - verify local HEAD equals `origin/main`
4. report the checkpoint briefly

Preferred report format:

```text
CHECKPOINT
What changed:
What was verified:
Commit:
EliteDesk:
GitHub:
Status: IN SYNC
```

The 30-minute interval is a **checkpoint target**, not permission to push broken code.

If a change is incomplete at the checkpoint:

- do not push a knowingly broken `main`
- finish the smallest coherent unit
- test it
- then commit/push
- state why the checkpoint ran long if relevant

Do not leave hours of completed verified work only on the EliteDesk.

Michael grants standing approval for normal milestone commits and pushes of completed, tested, non-destructive work under this cadence. This does not authorize destructive Git operations, deployment, database mutation, or knowingly broken commits.

## 5. Safe EliteDesk / GitHub synchronization

At the start of a development session:

1. `git fetch origin`
2. inspect `git status`
3. compare local HEAD to `origin/main`

If **clean + behind**:
- fast-forward safely (`git pull --ff-only` is acceptable)

If **clean + current**:
- proceed

If **dirty**:
- preserve the work
- do not pull over it blindly
- report the state

If **diverged or unexpectedly ahead**:
- stop and report the exact state

Never automatically:

- reset
- rebase
- clean
- force-pull
- force-push
- discard uncommitted work
- delete files merely to synchronize

Desired state between completed development blocks:

```text
ELITEDESK HEAD == GITHUB origin/main
working tree clean
```

Make synchronization easy for Michael. A safe helper/status command is desirable, but it must never destroy work merely to make SHAs match.

## 6. Standing ~300-line architecture rule

Handwritten production code should normally remain at or below approximately **300 lines per file**.

This is an architectural rule intended to prevent God files, not an arbitrary line-count game.

A small overage above 300 is acceptable only when:

- the file still has one clear cohesive responsibility
- splitting it would make the architecture less understandable
- the overage is genuinely necessary
- the reason is explicitly noted during review

There is generally no reason for a handwritten production-code God file when coherent responsibilities can be extracted into modules, services, helpers, domain logic, or functions that call one another.

Do **not** keep growing a file simply because it is already oversized.

If a production file accumulates multiple responsibilities, split by coherent responsibility. Prefer small focused modules with explicit interfaces over one file containing routing, persistence, validation, business logic, formatting, and orchestration together.

Do **not** arbitrarily chop files into meaningless pieces merely to satisfy the line number.

Normal line-count exemptions include material where size does not represent production-code complexity, such as:

- documentation
- reports
- informational/reference files
- generated code/data
- static datasets
- configuration/schema material where splitting would reduce clarity

At every milestone/checkpoint:

- inspect materially changed handwritten production files
- report files over approximately 300 lines
- explain any legitimate overage
- refactor before checkpoint unless there is a documented exception

`backend/models.py` remains temporary technical debt, not precedent. Its prior one-checkpoint exception does not become a standing grandfather.

**There should be no God files in CAOSCARE.**

## 7. Current data/auth outage remains first

Before continuing normal Voice tuning, determine the exact cause of the current shared failure pattern:

- Google sign-in failed
- Requests failed to load
- Pendants failed to load
- residents/rooms/kiosks appeared empty

Treat these as potentially one shared backend/environment/API/database problem until evidence proves otherwise.

Do not reseed or recreate records first.

Verify:

- frontend API origin actually in use
- backend process/port/CWD
- runtime environment loaded
- Google client configuration presence/match without printing secrets
- auth response/status
- Mongo configuration/database actually in use
- whether the known resident/kiosk/request/conversation records still exist
- exact backend/API errors behind the frontend messages

If records exist in the expected database, restore the application/runtime connection to them rather than creating replacement data.

After repair verify live:

- Google owner sign-in works
- residents repopulate
- Chauncey / Room 304 exists
- kiosks repopulate
- Requests loads
- Pendants loads
- conversations/diagnostics remain available

Then document the root cause and checkpoint it.

## 8. Public hosting / Linode

Do not spend current engineering time on Linode or public deployment.

The existing website is not operationally important right now. Development quality and GitHub durability take priority.

Any previously created deployment scripts/reports remain part of project history but are out of current scope unless Michael explicitly says otherwise.

## 9. Standing safety around state

Do not silently destroy evidence or working state.

For investigation and repair:

- inspect before mutating
- preserve uncommitted work
- do not delete false/bad operational records used as evidence unless Michael approves
- do not expose secrets
- do not run deployment merely to test local development
- do not reset databases or seed replacement data without explicit evidence and approval

## 10. Working principle

The repo is the shared state layer.

Claude Code and ChatGPT-Aria should be able to reconstruct the same project state from GitHub without Michael acting as a copy/paste relay.

The operating loop is:

`plan -> build -> test -> milestone -> document -> commit -> push -> continue`

GitHub gets updated at accomplishments, not at keystrokes.
