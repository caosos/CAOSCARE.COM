# CAOS Care

CAOS Care is the care-focused vertical of the CAOS ecosystem.

It is intended to support senior-care and assisted-living workflows through resident-centered memory, staff support, care-plan visibility, safety escalation, documentation, wearable/tablet/kiosk surfaces, predictive behavior-change awareness, and a practical CCE-lite trust layer.

## Start here for agents

Before making claims or changes, read:

1. `AGENTS.md`
2. `docs/PROJECT_STATE.md`
3. `docs/CAOS_CARE_AGENT_ONBOARDING_CONTRACT.md`
4. `docs/CCE_LITE_TRUST_LAYER_PROPOSAL.md`
5. `docs/REPO_MAP.md`
6. `docs/BUILD_STATUS.md`

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
- wearable/tablet/kiosk workflows
- escalation support under human oversight
- CCE-lite routing, verification, and receipt-backed trust workflows

## Required stance

- Human care remains primary.
- AI output is advisory unless explicitly approved by authorized humans.
- Safety-critical workflows require receipts, escalation paths, and confirmation gates.
- Private resident data must be protected.
- No feature is complete without acceptance criteria and regression notes.

## Current state

This repository has been initialized as the CAOS Care build surface and agent onboarding entrypoint.

Public website crawl was attempted from ChatGPT tooling, but no crawlable CAOS Care site content was available at the time this README was updated. Future agents must inspect the deployed website directly when accessible and update this repo map/onboarding contract with verified page content.
