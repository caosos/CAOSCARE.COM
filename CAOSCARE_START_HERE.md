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

Immediately after repository-wide hydration:

1. Read **`docs/CURRENT_PRIORITY.md`** when it exists. It holds Michael's current execution target and priority order. Treat it as current-state guidance, not durable product architecture; the Product Baseline and contracts still govern product truth.
2. Read **`docs/PILOT1_EXECUTION_CHECKLIST.md`**, the authoritative execution tracker for the 2026-10-10 Pilot 1 target.
3. Identify the checklist's **Current phase** and **Current active task** before recommending new CAOSCare work.

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
