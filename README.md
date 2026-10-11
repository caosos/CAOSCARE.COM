# CAOS Care

CAOS Care is the care-focused vertical of the CAOS ecosystem.

It is intended to support senior-care and assisted-living workflows through resident-centered memory, staff support, care-plan visibility, safety escalation, documentation, a resident **room node** (local CAOSCare computer behind the TV) with voice/audio and room hardware, staff **clients** (tablet / phone / computer) running the appropriate workspace, predictive behavior-change awareness, and a practical CCE-lite trust layer. Resident rooms are **not** tablet-based — see `docs/CAOSCARE_PRODUCT_BASELINE.md`.

## Start here for agents

Before making claims or changes, read in order:

1. `AGENTS.md`
2. `docs/CAOSCARE_PRODUCT_BASELINE.md` — canonical durable product truth
3. `docs/PROJECT_STATE.md`
4. `docs/REPO_MAP.md`
5. `docs/BUILD_STATUS.md` / `docs/CURRENT_NODE_STATUS.md`
6. `docs/CAOS_CARE_AGENT_ONBOARDING_CONTRACT.md` (hardware section is `HISTORICAL / SUPERSEDED`), `docs/CCE_LITE_TRUST_LAYER_PROPOSAL.md`, and task-specific contracts

The full boot sequence is in `AGENTS.md` and `docs/CAOSCARE_PRODUCT_BASELINE.md` §9.

## Project operating protocol — non-negotiable

This repository uses one authoritative living checklist, one receipt/liaison lane, one existing coordinator, and one bounded eligible item at a time. Preserve completed history and explicitly correct stale entries. Every item must identify its owner, priority, acceptance test, current stage, blocker, and next eligible action.

The coordinator lifecycle is:

```text
DELIVERED → ACK → WORKING → DONE
                         ↘ NEED / BLOCKED
```

A delivery is not an ACK. A worker claim is not a verified result. Do not create a duplicate coordinator, worker, queue, watchdog, monitor, or truth file.

### ETA-driven checks and exception alerts

Every `ACK / WORKING` receipt must include:

- project and bounded task ID;
- responsible coordinator or worker;
- current stage;
- evidence reviewed;
- realistic ETA;
- exact `next_check_at` timestamp in `America/Chicago`;
- expected acceptance test or completion evidence;
- current blocker, or `NONE`.

The ETA must be derived from the actual work scope, tests, browser verification, deployment steps, and known host conditions. Never invent an ETA or use a meaningless generic estimate.

The existing **LOCAL watchdog** owns the exact `next_check_at` timer. At that time it must inspect current process state, receipts, repository state, and loaded service state when applicable, then publish exactly one of:

- `WORKING` — current evidence, progress, revised ETA, and new `next_check_at`;
- `DONE` — exact commit, tests and results, review/browser evidence, loaded revision, host observation when applicable, user-visible result, cost if known, timestamp, and next queue item;
- `NEED / BLOCKED` — exact blocker, exact requested action or copyable command, impact, compatible authorized work continuing, and next check time.

Finishing early requires an immediate `DONE` receipt and dispatch of the next eligible bounded item. Do not wait for the scheduled check.

A missed ACK, ETA, or `next_check_at` is an exception and must be recorded with provenance. Do not claim that a worker stopped unless current host evidence proves it. Otherwise use:

```text
APPEARS STALE — HOST STATE UNVERIFIED
```

Notify Michael promptly only for:

- `DONE` requiring owner acceptance;
- `NEED / BLOCKED`;
- missed ACK, ETA, or check time;
- failed test, delivery, deployment, or recovery;
- a genuine owner decision;
- a material cost or authority boundary.

Do not notify Michael for routine healthy progress, unchanged state, or routine build/release authority already granted.

The **CLOUD supervisor** is the hourly fallback. Every hourly checkpoint must state:

- current bounded task and queue stage;
- latest exact receipt and commit;
- tested state versus loaded state;
- last timestamped host observation, or `UNKNOWN`;
- ETA and `next_check_at`;
- blocker;
- one next action.

GitHub activity or a dated comment is not proof that a host process is alive now. Slack, GitHub, or other supported events may wake supervision earlier, but they do not replace current host receipts.

Keep project ownership and code isolated. Do not edit, dispatch, supervise, or recover another project's work. Quarantine misdelivered work until the intended recipient is verified.

The governing rule is:

> **No action without a receipt. No receipt without provenance.**

## CCE-lite trust layer

CAOS Care should use the CAOS Council Engine direction as a practical care-safe profile, not as a heavy multi-model council on every resident/staff interaction.

The first useful version is:

```text
CCE-lite = intent classifier + risk gate + verifier + receipt + human escalation
```

This means CAOS Care should prioritize:

- residents being heard faster;
- staff being routed clearer;
- family/staff communication being verified before it matters;
- sensitive outputs staying inside human-supervised boundaries;
- leadership having receipts for what happened.

Full council mode belongs later in admin, incident review, policy, research, architecture, and complex decision-support workflows.

See [`docs/CCE_LITE_TRUST_LAYER_PROPOSAL.md`](docs/CCE_LITE_TRUST_LAYER_PROPOSAL.md).

## Core doctrine

CAOS Care is not a replacement for clinicians, caregivers, licensed medical professionals, emergency services, or regulated clinical judgment.

CAOS Care is a governed assistive platform for:

- care-plan visibility
- resident reminders
- staff empowerment
- resident safety alerts
- family/staff communication support
- documentation and receipts
- behavior-change detection as advisory signal
- the resident room node + staff-client model (`docs/CAOSCARE_PRODUCT_BASELINE.md` §2/§3); wearable ingest
- escalation support under human oversight
- CCE-lite routing, verification, and receipt-backed trust workflows

## Required stance

- Human care remains primary.
- AI output is advisory unless explicitly approved by authorized humans.
- Safety-critical workflows require receipts, escalation paths, and confirmation gates.
- Private resident data must be protected.
- No feature is complete without acceptance criteria and regression notes.

## Current state

> This section is a snapshot from early onboarding and understates where the
> project is. For real current state read **`docs/PROJECT_STATE.md`** (recent
> dated entries) and **`docs/CURRENT_NODE_STATUS.md`**. The repository is an
> active multi-surface CAOSCare codebase with a deployed backend/frontend and
> a live resident-room bring-up host — not a blank build surface.

Public website crawl was attempted from ChatGPT tooling, but no crawlable CAOS Care site content was available at the time this README was updated. Future agents must inspect the deployed website directly when accessible and update the repo map/onboarding contract with verified page content.
