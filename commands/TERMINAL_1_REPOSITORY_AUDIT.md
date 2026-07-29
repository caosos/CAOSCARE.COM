# TERMINAL 1 — CAOS Care Repository Audit

## Instruction to Claude Code

Perform this investigation now from the root of the `caosos/CAOSCARE.COM` repository.

This is an **audit-only** session. Do not edit, create, delete, commit, push, install, deploy, start, or stop anything. Do not print secrets or `.env` values.

First read `AGENTS.md` and obey it. Then read, in order:

1. `README.md`
2. `docs/PROJECT_STATE.md`
3. `docs/CAOS_CARE_AGENT_ONBOARDING_CONTRACT.md`
4. `docs/CCE_LITE_TRUST_LAYER_PROPOSAL.md`
5. `docs/REPO_MAP.md`
6. `docs/BUILD_STATUS.md`
7. `docs/DEPLOYMENT_RUNBOOK.md`

Then inspect the complete repository, current branch, recent commits, application architecture, frontend, backend, authentication, deployment files, tests, unfinished code, `TODO` and `FIXME` markers, duplicate or obsolete code, and documentation.

Pay special attention to contradictions between `docs/BUILD_STATUS.md`, `docs/DEPLOYMENT_RUNBOOK.md`, `docs/PROJECT_STATE.md`, the current source code, and Git history.

Determine:

- What actually exists and works in the current `main` branch.
- What is only documented or proposed.
- What documentation is stale or factually wrong.
- Whether `yarn.lock` and direct Google OAuth are present now.
- Current frontend and backend entrypoints.
- Current authentication routes and authorization boundaries.
- Current test coverage and obvious untested critical paths.
- Launch blockers.
- Security or privacy problems visible in source.
- Dead Emergent dependencies or branding still present.
- Files that are too large or violate `AGENTS.md`.
- The smallest logical repair sequence.

Return one evidence-backed Markdown report in the terminal with these sections:

1. Executive finding
2. Verified current architecture
3. Contradictions and stale documentation
4. Broken or unfinished implementation
5. Security and authentication findings
6. Tests and verification gaps
7. Prioritized repair backlog
   - Critical now
   - Required before public preview
   - Required before production
   - Later CAOS Care development
8. Exact files involved
9. Recommended first coding task

Include file paths and line references wherever practical. Make no changes.