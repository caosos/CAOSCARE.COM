# AGENTS.md — CAOS Care Agent Protocol

This file is the mandatory entry point for AI agents inspecting or modifying the CAOS Care repository.

## Operating mode

Default mode is inspect-first.

Do not code, redesign, deploy, or rewrite product claims until you understand:

1. the current branch/ref being inspected
2. which files exist in this repo
3. whether the task is documentation, frontend, backend, care workflow, hardware, privacy/safety, or deployment
4. whether the public website is available and crawlable
5. which care-domain safety boundaries apply

## Product identity

CAOS Care is the care-focused vertical of the CAOS ecosystem.

It is intended to support senior-care and assisted-living environments through:

- care-plan visibility
- resident reminders
- resident safety alerts
- staff support
- documentation and receipts
- family/staff communication assistance
- wearable/tablet/kiosk workflows
- behavior-change awareness
- escalation support under human oversight

CAOS Care must remain practical, clear, and operationally useful in real care environments.

## Mandatory preserve list

Do not remove or silently degrade:

- resident safety concepts
- care-plan tracking
- staff empowerment workflows
- predictive behavior-change awareness
- privacy/consent boundaries
- audit receipts
- escalation/handoff paths
- wearable/tablet/kiosk direction
- human-in-the-loop care decisions
- low-intimidation senior-care UX
- CAOS ecosystem alignment

## Care-domain safety rule

CAOS Care must not present itself as a doctor, nurse, emergency service, medical device, clinical authority, or autonomous medical decision-maker unless the required legal, clinical, regulatory, and certification framework exists.

Default stance:

```text
assistive, advisory, human-supervised, receipt-backed
```

High-risk outputs require clear boundaries and human confirmation.

## Required first read order

Before making changes, read:

1. `README.md`
2. `docs/PROJECT_STATE.md`
3. `docs/CAOS_CARE_AGENT_ONBOARDING_CONTRACT.md`
4. `docs/REPO_MAP.md`
5. `docs/BUILD_STATUS.md`

If the public website is reachable, also inspect the live site and record verified page findings in `docs/REPO_MAP.md` or a dedicated website audit doc.

## Public website verification rule

Do not invent website content.

If CAOSCARE.COM is not reachable or not crawlable from available tools, say so plainly and mark website content as pending source review.

Future agents must distinguish:

- verified repo content
- verified live website content
- Michael-provided product direction
- inferred architecture
- planned features

## Change discipline

Use small, bounded changes.

For documentation:

1. keep claims accurate
2. mark unverified website claims as pending source review
3. preserve care-domain safety boundaries
4. document onboarding and acceptance criteria
5. update repo maps when files are added

For code, when code exists:

1. inspect relevant files first
2. preserve accepted behavior
3. aim below 300 lines for handwritten production code files
4. hard cap handwritten production code files at 300 lines unless Michael explicitly approves an exception
5. split by clear domain or responsibility, never arbitrary line chopping
6. avoid God files
7. do not launch a broad refactor solely to shorten an untouched legacy file that is already over the cap
8. if modifying an existing code file already above 300 lines, do not make it larger — extract the responsibility being changed when practical
9. prefer focused modules and contracts
10. add receipts / logs / checks where appropriate
11. before finishing any coding task, report the line counts of every created or materially modified production-code file

Documentation, informational files, reports, generated files, static data, lockfiles, and necessary configuration files are exempt from the 300-line cap.

## Required care principles

CAOS Care must prioritize:

- resident dignity
- staff usefulness
- family clarity where appropriate
- privacy and consent
- accessibility
- low-friction UX
- reliable alerts/escalation
- evidence-backed claims
- transparent limitations
- human accountability

## Stop conditions

Stop and report before acting if:

- a change may imply clinical/medical authority
- private resident data may be exposed
- production deployment is requested without explicit approval
- destructive changes are requested
- legal/compliance claims are unclear
- website content is unavailable but needed for accuracy
- source evidence contradicts product claims
- a feature would remove human oversight from safety-critical care

## Non-negotiable

CAOS Care must be built as a governed assistive care platform with human oversight, privacy controls, receipts, safety boundaries, and operational usefulness.

No hallucinated clinical claims. No autonomous medical judgment. No silent privacy risk. No vague enterprise fluff.

## Project state update rule

`AGENTS.md` is the only file a human or AI agent should need to remember first.

Before beginning meaningful work, read:

1. `AGENTS.md`
2. `docs/PROJECT_STATE.md`
3. `docs/REPO_MAP.md`
4. `docs/BUILD_STATUS.md`
5. any task-specific docs (for example `docs/DEPLOYMENT_RUNBOOK.md`, contracts, or surface-specific maps)

If `docs/PROJECT_STATE.md` does not exist yet, read and update `docs/BUILD_STATUS.md` until `docs/PROJECT_STATE.md` is created.

Before finishing meaningful work, update `docs/PROJECT_STATE.md` with a dated entry.

Each entry must include:

- Date
- Agent/tool used
- Branch/ref
- What changed
- What was verified
- What is blocked
- Next safe step

Do not replace or erase prior project history. Append dated entries unless correcting a factual error, and label corrections clearly.

Update `docs/PROJECT_STATE.md` after any completed feature, bug fix, deployment attempt, hardware/device test, authentication change, dependency/environment change, major documentation update, every few commits during active work, or any stopping point where another agent may need to resume.
