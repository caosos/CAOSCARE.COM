# CCE-lite Trust Layer Proposal for CAOS Care

Status: proposal / product-architecture direction  
Scope: CAOS Care resident/staff/family/admin workflows  
Parent engine: CCE — CAOS Council Engine

## Executive decision

CAOS Care needs a trusted product now. It does not need the full CAOS Council Engine on every turn.

The right first care implementation is:

```text
CCE-lite = intent classifier + risk gate + verifier + receipt + human escalation
```

Full CCE can remain available for admin, incident review, policy, research, and architecture work. Resident-facing and staff-facing senior-care workflows should stay simple, fast, calm, and human-supervised.

## Product truth

Senior care does not need an AI toy. It needs a trust layer.

In practical terms, the product must help answer:

```text
Did the resident get heard?
Did the request route to the right staff member?
Was the action documented?
Was a human required?
Was the family/staff update clear?
Was private data protected?
Did the system avoid pretending to be a doctor, nurse, emergency service, or legal authority?
Can leadership review what happened later?
```

That is the trust product.

## Why CCE-lite first

Full multi-model council mode is useful, but it is too heavy for ordinary resident/staff interactions.

A resident saying "I am cold" or "call my daughter" does not need five models debating policy. It needs fast routing, safe boundaries, and a record.

A staff member asking for a family update draft or incident handoff may need verification, but usually not a full council.

A serious incident, disputed family message, policy update, or compliance-adjacent analysis may need full Council Mode.

## Mode ladder for CAOS Care

### Fast Care Mode

Use for low-risk operational tasks.

Examples:

- resident comfort request;
- reminder;
- simple staff task creation;
- non-sensitive kiosk interaction;
- basic facility info.

Shape:

```text
intent classifier -> action/router -> receipt
```

### Verified Care Mode

Use when content matters and should be checked before output/action.

Examples:

- family message draft;
- shift handoff summary;
- incident note cleanup;
- resident concern summary;
- maintenance issue with safety relevance;
- behavior-change advisory note.

Shape:

```text
intent classifier -> primary draft/plan -> verifier -> final output/action -> receipt
```

### Council Care Mode

Use only for complex/high-impact admin workflows.

Examples:

- serious incident review;
- family dispute summary;
- policy/procedure drafting;
- care workflow redesign;
- regulatory/compliance-adjacent research;
- vendor/product comparison;
- architecture and deployment decisions.

Shape:

```text
router -> worker panel -> opposition/safety/source checks -> synthesizer -> verifier -> receipt
```

### Lockdown / Human Escalation Mode

Use when the system should not answer or act autonomously.

Examples:

- emergency medical situation;
- diagnosis/treatment request;
- medication authority;
- autonomous emergency dispatch;
- legal/compliance guarantee;
- privacy boundary problem;
- unclear consent/permission;
- destructive action without authorization.

Shape:

```text
risk gate -> human escalation / block -> receipt
```

## Required CCE-lite components

### 1. Intent classifier

Classifies the user request into a care-safe lane.

Initial lanes:

```text
resident_comfort
resident_safety
staff_task
family_update
maintenance
incident_or_handoff
reminder
facility_info
privacy_or_consent
medical_or_emergency_boundary
unknown
```

### 2. Risk gate

Determines how much autonomy the system has.

Risk levels:

```text
low       -> answer/route normally
medium    -> verified mode
high      -> human confirmation required
blocked   -> no AI answer/action; escalate
```

### 3. Verifier

Checks sensitive output before it reaches users or creates records.

Verifier checks:

- no diagnosis;
- no medication authority;
- no autonomous clinical/legal decision;
- no unsupported certainty;
- no unnecessary private data exposure;
- family/staff tone is clear and professional;
- action and escalation are consistent with care-domain safety posture.

### 4. Receipt builder

Creates an audit-safe record.

Minimum fields:

```text
request_id
surface
actor_role
intent_lane
risk_level
mode_used
resident_id_or_scope_reference
staff_or_team_notified
action_taken
human_confirmation_required
privacy_flags
safety_flags
verifier_result
final_status
timestamp
```

Receipts should not leak unnecessary private resident/staff/family details.

### 5. Escalation router

Routes human-required items to the right path.

Initial escalation targets:

```text
care staff
nurse / clinical lead where facility-defined
maintenance
executive director / administrator
family contact where permissioned
emergency protocol instruction to staff, not autonomous dispatch
```

## User/admin controls

Resident and staff surfaces should stay simple.

Admin/builder surfaces may expose toggles:

```text
Fast / Verified / Council / Lockdown mode policy
Always verify family messages
Always verify incident summaries
Require human confirmation for resident-safety alerts
Primary-source-only research for admin/policy tasks
Show disagreement summary for council tasks
Show receipt detail level
Limit model spend per facility/day
```

## Care-domain safety boundary

CAOS Care remains:

```text
assistive
advisory
human-supervised
receipt-backed
privacy-aware
operationally useful
```

CAOS Care must not claim to be:

```text
doctor
nurse
emergency service
medical device
clinical authority
autonomous medical decision-maker
legal/compliance guarantor
```

High-risk flows require human review and receipts.

## What CAOS Care should sell

Do not sell "multi-model AI council" to senior-care operators as the first message.

Sell this:

```text
Residents are heard faster.
Staff are routed clearer.
Families get cleaner communication.
Leadership gets receipts.
The system stays inside human-supervised care boundaries.
```

The engine can be advanced. The product must be simple.

## First implementation slice

A useful v1 can be built without full council mode.

Build these first:

1. Intent lane classifier for resident/staff requests.
2. Risk gate for care-domain boundaries.
3. Verified mode for family updates, incident summaries, and staff handoffs.
4. Receipt fields on routed actions.
5. Human escalation status visible in staff/admin surfaces.
6. Admin setting to force verified mode for specific lanes.

## Acceptance criteria

CCE-lite is working when CAOS Care can show:

```text
A resident/staff/family request was classified.
The risk level was assigned.
The correct mode was selected.
A verifier checked sensitive output.
The action was routed or blocked.
A receipt was stored.
A human escalation happened when required.
The system stayed inside care-domain safety boundaries.
```

## Non-goals for v1

Do not start with:

- full multi-model debate on every turn;
- autonomous medical advice;
- autonomous emergency dispatch;
- complex resident-facing AI controls;
- provider-specific claims;
- unverified compliance guarantees;
- hidden resident-data sharing;
- heavy admin dashboards that slow staff down.

## Relationship to full CCE

Full CCE is the reusable CAOS engine.

CCE-lite is the care-safe operational profile.

```text
CAOS core owns the engine contract.
CAOS Care owns the care-domain policy, UX, safety boundaries, and workflow receipts.
```

The first CAOS Care product should not wait for the full engine to be perfect. It should ship the minimum trustworthy version: classify, gate, verify, document, and escalate.
