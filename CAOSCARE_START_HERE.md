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
