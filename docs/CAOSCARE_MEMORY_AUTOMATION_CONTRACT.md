# CAOSCare Memory Automation Contract v1

## Status

Active baseline contract for CAOSCare memory behavior.

This contract defines how CAOSCare should remember users, residents, staff, family contacts, facility context, and care-relevant events without requiring residents to manage memory manually.

## Core position

CAOSCare memory is not a manual chatbot preference panel.

CAOSCare memory is an automatic, governed, source-backed continuity layer designed for long-running senior-care relationships.

The resident should not be expected to inspect, confirm, classify, or maintain memory atoms. The system must perform memory work automatically under strict review, evidence, privacy, and escalation rules.

## Non-negotiable distinction

```text
Cross-session leakage is forbidden.
Governed cross-session retrieval is required.
```

Leakage means accidental context contamination, such as treating an old event as if it is happening now.

Governed retrieval means intentional, scoped, source-backed use of durable memory when relevant, permitted, and safe.

## Primary goal

CAOSCare should be capable of accompanying a user for years while preserving continuity, dignity, context, and safety.

The system may preserve broad interaction history and care-context events, but only distilled, source-backed, permission-scoped memory should be injected into AI responses.

## Accuracy standard

The standard is not that the model magically cannot make an error.

The standard is that CAOSCare must never present uncertain, inferred, stale, weak, or unsupported memory as established fact.

Memory must be labeled, weighted, sourced, scoped, and auditable.

## Operating principle

```text
Store broadly.
Distill carefully.
Retrieve narrowly.
Inject only when relevant.
Escalate when safety requires it.
Never overstate certainty.
```

## Human audit phase

During early CAOSCare deployment, Michael or another authorized reviewer may act as the audit layer.

The system should surface memory candidates, high-risk derived patterns, and automation decisions for review until the memory policy proves stable enough for higher automation.

The intended maturity path is:

```text
Phase 1: Human-audited memory candidates
Phase 2: Auto-save low-risk memories, review medium/high-risk memories
Phase 3: Auto-review confidence thresholds with staff/admin exception queue
Phase 4: Fully governed automation with audit sampling and escalation receipts
```

No phase may remove auditability.

## Memory handling tiers

### Tier 1: Low-risk memory

Examples:

```text
preferred name
favorite music
favorite foods or drinks
hobbies
conversation style
comfort topics
simple routines
accessibility preferences
```

Default handling:

```text
auto-save if source-backed
auto-retrieve when relevant
resident-facing use allowed
receipt retained
```

### Tier 2: Medium-risk memory

Examples:

```text
family relationships
care routines
mild anxiety triggers
sleep preferences
meal routines
mobility preferences
staff interaction preferences
```

Default handling:

```text
auto-save with evidence
visible to staff/admin
retrieve with permission scope
allow correction/counterevidence
```

### Tier 3: High-risk care-sensitive memory

Examples:

```text
health-adjacent claims
pain patterns
confusion patterns
fall risk observations
medication-adjacent statements
behavior-change observations
family conflict or abuse-adjacent statements
```

Default handling:

```text
save as candidate or flagged observation
require staff/admin review before strong factual use
never diagnose
never present as certain if inferred
surface source and confidence
```

### Tier 4: Critical safety event

Examples:

```text
fall
chest pain
trouble breathing
missing resident
severe confusion
abuse allegation
suicidal or self-harm statement
urgent medication issue
emergency call request
```

Default handling:

```text
create alert or escalation immediately
record event and receipt
do not treat first as ordinary memory
human response path required
```

## Source modes

Every memory must carry a source mode.

```text
USER_STATED
RESIDENT_STATED
STAFF_STATED
FAMILY_STATED
ADMIN_STATED
DEVICE_OBSERVED
SYSTEM_OBSERVED
DERIVED_PATTERN
UNVERIFIED_CANDIDATE
COUNTEREVIDENCE
```

The source mode controls how the memory may be used.

A derived pattern must never be spoken as if it were a directly stated fact.

## Required memory object fields

Minimum memory atom shape:

```text
memory_id
subject_type
subject_id
content
bin_name
source_mode
source_ref
quote_or_anchor
confidence
priority
sensitivity
mutation_policy
visibility_scope
consent_scope
status
created_at
updated_at
last_referenced_at
expires_at
requires_review
```

## Subject model

CAOSCare must not hard-code resident as the universal memory identity.

Required subject shape:

```text
subject_type + subject_id
```

Allowed CAOSCare subject types include:

```text
user
resident
staff
family
caregiver
facility_admin
facility
device
```

Resident memory is a role overlay, not the root architecture.

## Retrieval policy

Before injecting memory into a response, the system must determine:

```text
Who is the subject?
Who is asking?
What is the active session or event?
What is relevant now?
What is permitted for this audience?
What is source-backed?
What is stale or needs review?
What could create safety risk if overstated?
```

Memory retrieval must be scoped by:

```text
subject_type
subject_id
session_id or event_id
role/permission
sensitivity
relevance
recency
confidence
review state
```

## Resident experience

Residents should experience memory naturally.

Allowed resident-facing pattern:

```text
Good evening, Miss Betty. Would you like gospel music again tonight?
```

Not resident-facing unless needed:

```text
I retrieved OPERATING_PREFERENCE with 92 percent confidence.
```

Audit metadata belongs in staff/admin views and receipts.

## Staff/admin experience

Staff and administrators must be able to inspect:

```text
what was remembered
why it was remembered
where it came from
when it was last used
who can see it
whether it was inferred or stated
whether it needs review
what counterevidence exists
```

## Hallucination resistance rule

CAOSCare must never invent memory.

CAOSCare must never turn a weak signal into a firm claim.

CAOSCare must never erase uncertainty labels when communicating with staff or administrators.

If a memory is derived or low-confidence, the system must say so or suppress it.

## Example: correct handling

Weak pattern:

```text
Three shower-time distress notes in two weeks.
```

Allowed staff-facing language:

```text
Possible pattern: three shower-related distress notes were recorded in the last two weeks. Staff review recommended.
```

Disallowed language:

```text
Mary always gets anxious before showers.
```

## Required future implementation components

```text
MemoryEventLog
MemoryAtom
MemoryEvidence
MemoryCandidate
MemoryRetrievalReceipt
MemoryPolicy
MemoryReviewQueue
CounterevidenceLink
SubjectMemoryContextBuilder
```

## Non-negotiable

CAOSCare memory must be automatic for residents, governed for staff, auditable for administrators, and source-backed for every care-sensitive use.

The system may grow with the user for years, but it must never confuse continuity with uncontrolled context leakage or unsupported certainty.
