# CAOS Care Agent Onboarding Contract

> **SUPERSEDED IN PART.** The canonical durable product truth is now
> `docs/CAOSCARE_PRODUCT_BASELINE.md` (read it right after `AGENTS.md`).
> Where this contract conflicts with the Product Baseline on architecture or
> product direction, the Baseline wins. Specifically:
> - the **Hardware / device direction** section below is `HISTORICAL /
>   SUPERSEDED` — resident rooms are **not** tablet/dock-based; the current
>   resident-room architecture is a room node (EliteDesk-class PC behind the
>   TV) + eMeet audio + TV as a visual surface (Baseline §2), and staff use
>   tablet/phone/computer clients of the role/department workspaces
>   (Baseline §3);
> - the code-size rule here ("200 lines / 400-line hard cap") is
>   `SUPERSEDED` by "aim below 300, 300-line hard cap" (Baseline §8,
>   `AGENTS.md`).
>
> Everything else in this contract (care doctrine, safety boundaries,
> privacy, UX doctrine, memory principles, acceptance criteria) remains
> valid.

## Purpose

This contract orients future AI agents, builders, reviewers, and maintainers entering the CAOS Care repository.

CAOS Care is the care-focused vertical of the CAOS ecosystem. It exists to support senior-care, assisted-living, family-care, and staff workflows through governed AI assistance, memory, reminders, safety escalation, documentation, and simple device/app surfaces.

## Source status

At the time this contract was created:

- GitHub repo `caosos/CAOSCARE.COM` was accessible.
- The existing `README.md` contained only a placeholder line and was replaced with a real entrypoint.
- Public website crawl/search from ChatGPT tooling did not surface crawlable CAOSCARE.COM product content.

Therefore, website-specific copy and page inventory must be marked pending source review until the deployed website is accessible and inspected directly.

## CAOS ecosystem role

CAOS Care is one vertical in the broader CAOS ecosystem.

Relationship:

```text
CAOS Core = memory, agents, receipts, provider routing, governance, user identity
CAOS Care = senior-care / assisted-living / resident-safety vertical
CAOS Connect = manufacturing liaison / vendor-builder vertical
CAOS Trading = research/watchlist/finance-support vertical if retained
```

CAOS Care must inherit core CAOS doctrines:

- truth discipline
- user governance
- receipts everywhere
- no silent memory mutation
- no God files
- modular architecture
- human-in-the-loop high-risk actions
- privacy protection
- context sanity checks
- progressive memory trust only where appropriate

## Product mission

CAOS Care should help residents, staff, families, and operators coordinate care without creating unsafe autonomy or intimidating enterprise software.

The platform should help answer:

- What care was planned?
- What care happened?
- Who did it?
- When did it happen?
- What needs attention now?
- What changed in the resident's pattern?
- What reminders or escalations are needed?
- What evidence supports the alert or recommendation?
- Who needs to be notified?
- What was acknowledged, deferred, or completed?

## Required capability bundle

CAOS Care must include or preserve the following build scope unless Michael explicitly removes or replaces it.

**Current active priority (Product Baseline §6):** make the **resident
module** reliable first — resident context, room, assistance, communication,
information retrieval, staff routing, appropriate reminders, resident-facing
Aria behaviour, and the linked operational truth. Department workflows are
partially built; cross-department coordination, building/environmental
awareness, and higher-level automation are **direction, not built** — do not
present later layers as implemented.

### 1. Care Plan Optimization

Track what care was provided, by whom, and when.

Required concepts:

- care tasks
- resident plans
- staff assignments
- completion status
- missed/deferred care
- timestamps
- notes
- receipts
- handoff summaries

### 2. Resident Safety

Support safety signals and escalation.

Required concepts:

- wearable-based alerts
- two-way voice path where supported
- fall detection path where supported
- geo-fencing / location awareness where supported
- check-in reminders
- escalation trees
- human acknowledgement
- false-positive handling
- incident receipts

### 3. Staff Empowerment

Technology should support staff and reduce friction, not create useless overhead.

Required concepts:

- fast task views
- shift handoff support
- simple notes
- escalation clarity
- fewer duplicate entries
- staff-facing reminders
- plain-language AI assistance
- low-friction staff-client UX (the same role/department workspace on tablet, phone, or computer)

### 4. Predictive Health Analytics

AI-driven behavior-change detection should help flag earlier intervention opportunities.

Required concepts:

- behavior baseline
- pattern changes
- hydration/meal/activity/sleep/response signals where available
- advisory alerts
- confidence and evidence
- human review
- no autonomous diagnosis

## Hardware / device direction

> `HISTORICAL / SUPERSEDED` — the block below described an obsolete
> specialized-resident-tablet / dock / charging-base concept. It is kept
> for history, not as current architecture. **Current architecture:
> `docs/CAOSCARE_PRODUCT_BASELINE.md` §2 (resident room node) and §3 (staff
> clients).**

**Current (per the Product Baseline):**

- **Resident room:** a local CAOSCare room node — proven baseline an HP
  EliteDesk-class small PC — sitting hidden behind/near the TV; an eMeet-class
  speakerphone near the resident as the single room audio endpoint for Aria;
  the TV as the resident's normal television and an optional CAOSCare visual
  surface; a handset as the guaranteed-duplex fallback. The room node may
  integrate RF receiver/transmitter, IR, Zigbee, Z-Wave, networking, and
  communications integrations such as Twilio as the product develops.
  Proven vs planned must be distinguished.
- **Staff:** tablet / phone / computer clients running the appropriate
  role- and department-authorized workspace. No tablet-specific business
  logic.
- **Wearable ingest** direction is preserved (`POST /api/wearables/event`).

**Historical / superseded concept (do not treat as current):**

- specialized resident tablet
- dock/charging base
- one power cord feeding the base
- tablet charges when docked
- base may include receiver/connectivity hardware
- kiosk-capable form factor / care-environment console

Hardware and manufacturing specifics should coordinate with CAOS Connect where appropriate.

## Privacy and consent

CAOS Care will handle sensitive personal and operational information. Privacy must be built in from the start.

Required boundaries:

- resident data is private
- staff data is private
- family access must be permissioned
- facility access must be role-based
- raw sensitive data must not enter public/global bins
- analytics must be product/reliability focused, not ad-surveillance
- no selling user/resident data
- no third-party behavioral profiling
- receipts should not expose unnecessary private content

## Human oversight and safety

CAOS Care must not make autonomous clinical, legal, or emergency decisions.

Allowed:

- reminders
- summaries
- pattern alerts
- escalation prompts
- documentation support
- care-plan visibility
- advisory risk flags with evidence

Not allowed by default:

- diagnosis
- medication authority
- clinical orders
- autonomous emergency dispatch
- medical-device claims
- legal/clinical/compliance guarantees

High-risk actions require explicit human confirmation and receipts.

## UX doctrine

CAOS Care UX must be calm, simple, and fast.

Preferred qualities:

- low intimidation
- large clear controls where needed
- senior-friendly language
- staff-efficient task flow
- minimal clutter
- clear priority indicators
- obvious escalation state
- accessible contrast/text sizing
- voice-friendly interaction
- quick acknowledgement paths

Avoid:

- enterprise dashboard clutter
- hidden critical alerts
- unclear status
- over-automation
- scary or judgmental wording
- complex workflows for frontline staff

## Memory and recall requirements

CAOS Care must use CAOS memory principles carefully.

Important memory behavior:

- remember resident preferences only with proper scope/permission
- remember recurring care routines
- support vague recall: "that fall form", "the water reminder", "the room check thing"
- preserve source/evidence and timestamps
- allow correction and forgetting where appropriate
- distinguish durable facts from temporary observations
- prevent memory poisoning from untrusted external input

## Agent model

Future CAOS Care may use specialized agents, such as:

- Care Plan Agent
- Resident Reminder Agent
- Safety Alert Agent
- Staff Handoff Agent
- Family Update Agent
- Incident Summary Agent
- Behavior Change Agent
- Device/Hardware Agent
- Privacy/Safety Review Agent
- QA/Regression Agent

Each agent must have:

- lane
- tools
- permission scope
- memory scope
- budget
- stop conditions
- receipts
- human escalation rules

## Documentation requirements

Future agents must maintain documentation as product structure changes.

Required docs should eventually include:

- product contract
- hardware/device contract
- privacy/safety contract
- data model contract
- UX behavior contract
- agent/workflow contract
- public discoverability/SEO contract
- analytics contract
- build status
- troubleshooting vault
- feature parity matrix

## Repository discipline

All build work must follow CAOS discipline:

- inspect before write
- no unrelated refactors
- no main production deploy without approval
- no secrets committed
- no runtime data committed
- handwritten production-code files: aim below 300 lines, **hard cap 300 lines** unless Michael explicitly approves an exception (this replaces the older "200 soft / 400 hard" wording — see `AGENTS.md` and Product Baseline §8)
- docs may be long-form when needed
- receipts/commit SHAs in handoff; leave a handoff capsule (`AGENTS.md`)

## Website/page requirements

When CAOSCARE.COM is deployed and accessible, public pages should clearly explain:

- what CAOS Care is
- who it helps
- what it does
- what it does not do
- privacy/safety boundaries
- hardware direction (resident room node + staff clients — Product Baseline §2/§3)
- care-plan optimization
- resident safety
- staff empowerment
- predictive behavior analytics
- contact/access path

Public pages should be crawlable and should not expose private resident/facility data.

## Acceptance criteria for future agents

Before claiming a feature is built, verify:

- source file/module exists
- visible behavior exists or is documented as planned
- data/privacy boundary exists
- human oversight boundary exists for high-risk actions
- receipts/logging exist where meaningful
- test/smoke/manual acceptance path exists
- docs are updated

## Non-negotiable

CAOS Care must be useful in real care environments while remaining honest about its limits.

It is assistive, governed, human-supervised, privacy-aware, and receipt-backed.

No autonomous medical judgment. No fake clinical claims. No hidden privacy leakage. No intimidating enterprise clutter. No undocumented architecture.
