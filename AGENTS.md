# AGENTS.md — CAOS Care Agent Protocol

This file is the mandatory entry point for AI agents inspecting or modifying the CAOS Care repository.

## Canonical product baseline — read second

Immediately after this file, read **`docs/CAOSCARE_PRODUCT_BASELINE.md`**.
It is the canonical durable product truth: current architecture and product
invariants. When an older document conflicts with it on architecture or
product direction, the baseline wins and the older statement is stale.

Keep the layers separate:

- **`docs/CAOSCARE_PRODUCT_BASELINE.md`** = durable truth · architecture · invariants
- **`docs/PROJECT_STATE.md`** = changing build state (append-only dated entries)
- **`docs/REPO_MAP.md`** = where the implementation lives
- **`docs/BUILD_STATUS.md` / `docs/CURRENT_NODE_STATUS.md`** = runtime snapshots (point-in-time, may be stale)

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
- a resident room node (local CAOSCare computer behind the TV) with voice/audio (eMeet), the TV as a visual surface, and RF/IR/other room hardware — see the Product Baseline §2. Resident rooms are NOT tablet-based.
- staff clients (tablet / phone / computer) running the role- and department-scoped workspace — see the Product Baseline §3
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
- the resident-room-node architecture and the staff-client model as defined in `docs/CAOSCARE_PRODUCT_BASELINE.md` (§2, §3); wearable-ingest direction
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

## Required boot sequence

Before meaningful CAOSCare work, in order:

1. `AGENTS.md` (this file)
2. `docs/CAOSCARE_PRODUCT_BASELINE.md` — canonical durable product truth
3. `docs/PROJECT_STATE.md` — recent dated entries (changing state)
4. `docs/REPO_MAP.md` — where implementation lives
5. `docs/BUILD_STATUS.md` / `docs/CURRENT_NODE_STATUS.md` — runtime snapshot, where runtime matters
6. `README.md` and `docs/CAOS_CARE_AGENT_ONBOARDING_CONTRACT.md` — product/onboarding context (note: the onboarding contract's hardware section is `HISTORICAL / SUPERSEDED` by the Product Baseline)
7. task-specific contracts / TSBs
8. identify the exact **branch/ref** and the **assigned lane** (what you own, what you must not touch)
9. inspect the **actual relevant source** before claiming what exists
10. inspect **actual runtime / telemetry** when runtime behaviour matters
11. **inventory the tools / connectors / capabilities in this environment** before telling Michael "I can't access / look up / do that" — check whether an available tool or connector can do it
12. keep distinct at all times: repository truth · runtime truth · physical test evidence · Michael-provided product direction · inference · planned future capability
13. preserve raw evidence before any destructive cleanup; update `docs/PROJECT_STATE.md` and leave a handoff capsule (below) at handoff points

The full boot sequence and the layer split live in `docs/CAOSCARE_PRODUCT_BASELINE.md` §9.

If the public website is reachable, also inspect the live site and record verified page findings in `docs/REPO_MAP.md` or a dedicated website audit doc.

## Handoff capsule

At an agent/session handoff, leave a short capsule in `docs/PROJECT_STATE.md`
(this replaces the manual "transfer token" text). Record **only** what the
next agent needs to continue correctly, not the whole history:

```text
HANDOFF CAPSULE
- Objective:        <what is being built right now>
- Branch:           <exact branch/ref>
- Lane / ownership: <what you own; what you must NOT change>
- Last proven state:<what is actually verified working, and how>
- Commits:          <SHAs pushed this session>
- Runtime state:    <servers/services/ports live and relevant>
- Unresolved proven defects: <bug + evidence, or "none">
- Product invariants that matter here: <the 2-4 that constrain this work>
- Do NOT change:    <files/behaviours off-limits, especially another lane>
- Next safe action: <the single concrete next step>
```

Durable product truth → the Product Baseline / contracts. Current temporary
state → `PROJECT_STATE.md` + this capsule. Keep them separate.

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

Before beginning meaningful work, read (see the full boot sequence above):

1. `AGENTS.md`
2. `docs/CAOSCARE_PRODUCT_BASELINE.md`
3. `docs/PROJECT_STATE.md`
4. `docs/REPO_MAP.md`
5. `docs/BUILD_STATUS.md` / `docs/CURRENT_NODE_STATUS.md`
6. any task-specific docs (for example `docs/DEPLOYMENT_RUNBOOK.md`, contracts, or surface-specific maps)

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
