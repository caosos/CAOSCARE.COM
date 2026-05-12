# CAOSCare Privacy, Safety, Security, and Peace-of-Mind North Star v1

## Status

Active product north-star contract.

This document defines the highest-level purpose of CAOSCare across resident assistance, staff workflows, facility operations, family communication, devices, sensors, memory, and AI response behavior.

## Core statement

CAOSCare exists to improve privacy, safety, security, and peace of mind for residents, staff, operators, and loved ones.

```text
Privacy + Safety + Security + Peace of Mind
```

These are not marketing words. They are product requirements.

## Primary beneficiaries

CAOSCare must serve all of these groups without losing the resident-centered mission:

```text
residents
families / loved ones
care staff
kitchen staff
housekeeping staff
maintenance staff
nursing / clinical staff
administrators / operators
```

## Resident promise

Residents should experience CAOSCare as:

```text
safe
familiar
respectful
non-embarrassing
helpful
calm
private by default
present when needed
not intrusive when not needed
```

The system must preserve dignity. A resident is not a data object, a camera target, or a task ticket.

## Family / loved-one promise

Loved ones should gain peace of mind because CAOSCare can help answer:

```text
Was help requested?
Was staff notified?
Did someone acknowledge?
Is someone on the way?
Was the need resolved?
Are there recurring patterns worth reviewing?
Is my loved one being treated with dignity and attention?
```

Family communication must be permission-scoped and privacy-aware.

Peace of mind must not require exposing unnecessary private details.

## Staff promise

Staff should experience CAOSCare as support, not surveillance or punishment.

The system should reduce chaos by making work visible, assigned, logged, and easier to hand off.

Staff-support goals:

```text
less radio confusion
less lost paper
clearer assignments
faster response awareness
better handoff
fewer missed details
less duplicated work
more proof of completed work
```

## Privacy rule

CAOSCare must use the least identifying information required for the workflow.

Examples:

```text
Use room/slot for kitchen, housekeeping, maintenance, and drill workflows when names are not required.
Show resident identity only when role and workflow require it.
Do not expose clinical details to non-clinical roles unless explicitly permitted.
Do not retain raw audio/video unless required and authorized.
```

## Safety rule

CAOSCare must support rapid recognition, escalation, and follow-through for safety-relevant events.

Safety means:

```text
resident help requests are captured
staff are notified
acknowledgment is tracked
response progress is visible
unanswered calls escalate
critical events are handled as events first, not ordinary memory
```

## Security rule

CAOSCare must protect device, staff, resident, and family workflows from unauthorized access or spoofing.

Security means:

```text
role-based access
device authentication
signed field-device requests where required
revoked-device handling
audit logs
least-privilege visibility
protected resident data
clear production hardening path
```

## Peace-of-mind rule

Peace of mind comes from trustworthy visibility, not vague reassurance.

The system should not merely say help is coming. It should know and show the actual state:

```text
page created
staff notified
staff acknowledged
staff accepted
en route
arrived
resolved
escalated if unanswered
```

Resident-facing and family-facing language must be based on real backend status.

## AI behavior rule

AI in CAOSCare must behave as a calm, memory-aware, capability-aware assistant.

It may express operational care through action:

```text
remembering preferences
keeping the resident oriented
paging staff
tracking response state
summarizing handoff
flagging patterns for review
```

It must not claim unsupported certainty, clinical authority, human emotional experience, or autonomous care authority.

## Sensor rule

Tablet cameras and microphones are safety tools, not surveillance toys.

Allowed posture:

```text
event-triggered
permission-scoped
visible when active
receipt-backed
minimal retention
human-supervised
```

Disallowed posture:

```text
hidden monitoring
unrestricted camera browsing
unlogged access
punitive surveillance
unsupported visual diagnosis
```

## Memory rule

CAOSCare memory must support lifelong continuity without uncontrolled context leakage.

Required posture:

```text
automatic for residents
auditable for administrators
source-backed for care-sensitive use
reviewable by authorized humans
correctable
permission-scoped
```

The system should preserve context, retrieve carefully, distinguish fact from inference, and never present weak or unsupported memory as certainty.

## Facility operations rule

CAOSCare must help the whole building operate better.

Operational workflows should become:

```text
visible
assigned
timestamped
checkable
receipt-backed
handoff-ready
privacy-preserving
```

This includes maintenance, kitchen, housekeeping, drills, tasking, shift handoff, and clinical/nursing support where permitted.

## Design test

Every major feature should pass this question:

```text
Does this improve privacy, safety, security, or peace of mind without creating unnecessary intrusion, exposure, or false certainty?
```

If the answer is no, the feature must be redesigned, deferred, or rejected.

## Non-negotiable

CAOSCare must never trade resident dignity for convenience.

CAOSCare must never trade privacy for operational visibility unless the workflow truly requires it and the access is authorized.

CAOSCare must never use AI confidence as a substitute for human accountability.

The product center is:

```text
privacy, safety, security, and peace of mind for loved ones.
```
