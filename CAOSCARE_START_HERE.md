# CAOSCARE START HERE

This file is an additive universal onboarding front door for CAOSCARE / the Care app.

Human trigger phrase:

`CARE APP START HERE`

When Michael says that phrase, or clearly asks an AI to onboard to CAOSCARE, the AI should fetch this file fresh from `caosos/CAOSCARE.COM` and follow the existing repository topology before answering substantive CAOSCARE questions.

## Do not replace the existing topology

This file does **not** supersede, rewrite, or replace `AGENTS.md`, `CLAUDE.md`, lane onboarding files, project-state documents, branch-specific handoffs, or other established instructions.

Its job is only to tell a new or context-lost AI where to enter.

If another onboarding or agent file already governs the current lane, follow that file. Do not flatten multiple lanes into one generic workflow.

## Universal first step

Read `AGENTS.md` first.

`AGENTS.md` is the repository-wide agent protocol and mandatory entry point for agents inspecting or modifying CAOSCARE.

Then follow the read order and task-specific routing already defined there.

For any code or UI work, read the **Change discipline → file size / modularity**
rule in `AGENTS.md` before editing. Keep implementation files roughly within
300–400 lines when practical; around 400 is a signal to split by coherent
responsibility, not a hard cap. Do not keep enlarging an oversized file or
split it mechanically. Report line counts of every created or materially
modified production-code file at handoff. `AGENTS.md` is authoritative for
the complete rule and exceptions.

## Current execution priority

Immediately after repository-wide hydration, read in this order:

1. **`AGENTS.md`** (already part of hydration).
2. **`docs/CURRENT_PRIORITY.md`** — Michael's current execution target and priority order. Current-state guidance, not durable architecture; the Product Baseline and contracts still govern product truth.
3. **`docs/PILOT1_EXECUTION_CHECKLIST.md`** — the authoritative execution tracker for the 2026-10-10 Pilot 1 target.
4. **`docs/PILOT1_ACTIVE_WORK.md`** — the parallel-work ownership map. Identify your lane, branch/worktree, owned files and shared dependencies. Shared contracts change only through the Shared Core lane.
5. **`docs/PILOT1_READY_QUEUE.md`** — approved bounded future work. Know whether your job is ACTIVE, READY, WAITING, BLOCKED, DONE, or PARKED. Idle workers never invent busywork.
6. **`docs/PILOT1_RECOVERY_CHECKPOINT.md`** — the recovery snapshot: pipeline, lane tips, shared-core status, Michael's decisions, standard acceptance tests, runtime, next integration order.

The Pilot 1 files live on the **`integration/2026-09-27`** branch. If they are missing from the checkout or branch you fetched (for example `main`), read them from `origin/integration/2026-09-27`.

Before recommending or changing work, know: the current integration SHA, your lane, the current active task, your shared dependencies, whether your job is ACTIVE / READY / WAITING / BLOCKED, and the 2026-10-10 target.

If the recovery checkpoint conflicts with live source or runtime evidence, live evidence wins and the checkpoint must be updated.

All six Pilot 1 files are read before modifying CAOSCare.

Do not start lower-priority work when the checklist has an active unfinished task unless Michael explicitly redirects priority.

Do not let lower-priority feature expansion displace an active deadline in `docs/CURRENT_PRIORITY.md` unless Michael explicitly changes priority.

After every meaningful work block, update the checklist before declaring the task complete, following its **Update protocol**.

## Re-ground before advising

Before giving architecture, implementation, integration, status, or next-step advice:

1. Identify the repository, branch/ref, and work lane actually relevant to the request.
2. Read the current repository-wide onboarding required by `AGENTS.md`.
3. Read the current project-state / repo-map / build-status material required by that onboarding.
4. Read any lane-specific onboarding or contract for the system being discussed.
5. Inspect current branch tips, source, runtime evidence, or worktree state when the answer depends on what is currently built, committed, running, canonical, or uncommitted.
6. Treat current source/runtime evidence as stronger than stale conversational memory or old handoff text.
7. Preserve existing architecture and lane ownership. Do not invent a parallel system merely because the current AI lacks context.

## Cross-thread sync

If Michael says `CROSS-THREAD SYNC`, `CARE APP START HERE`, or otherwise indicates that the current conversation is missing project context:

- stop relying on the current chat slice alone;
- re-read this file and the existing onboarding topology;
- re-read `docs/CURRENT_PRIORITY.md` and `docs/PILOT1_EXECUTION_CHECKLIST.md`, and identify the current phase and active task;
- rehydrate from current repository/project evidence;
- then answer.

Do not make Michael manually restate architecture that is already available in the repository.

## Lane-aware routing

Examples only — follow the files actually present on the relevant branch/ref:

- Aria conversation / realtime / substrate work: locate and follow the current Aria lane onboarding and conversation-substrate contract.
- Resident Aria / Room 214 / Level 1 / RF / ResidentEvent work: locate and follow the current Level 1, Room 214, RF/event/session-fencing evidence and lane handoffs.
- Admin / Operations work: follow the current Admin/Operations lane state and operational contracts.
- Home Assistant / EliteDesk / device-control work: follow the current node-build, hardware, connectivity, and Home Assistant records before proposing architecture or changes.
- Cross-lane integration: inspect all active lane reports and current branch tips before recommending merge or integration order.

Do not assume `main` contains the newest unmerged lane implementation. Do not assume an old handoff is newer than current source.

## Truth discipline

Keep these distinct:

- verified current source/runtime state
- committed repository history
- local or uncommitted reported work
- documented intended architecture
- inference

Do not present one as another.

## No automatic mutation

Onboarding is read/inspect first.

Do not merge, rebase, cherry-pick, deploy, rewrite other lanes, or begin production changes merely because this file was invoked. Perform mutations only when Michael's current request authorizes them.

## One-line rule

**CARE APP START HERE means: fetch fresh CAOSCARE context, enter through the existing topology, identify the correct lane, verify current evidence, and only then answer.**
