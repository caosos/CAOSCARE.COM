# CAOSCare Facility Operations Contract v1

## Status

Active product-scope contract.

This document expands CAOSCare beyond resident-facing assistance into a full senior-care facility operations platform.

## Core product correction

CAOSCare is not only a resident companion, safety alert system, or AI chat surface.

CAOSCare must become a whole-building operating layer that helps staff help residents by turning daily facility work into visible, logged, assigned, checkable workflows.

The system must reduce paper loss, radio confusion, missed handoffs, duplicated work, unclear ownership, and unlogged resident status changes.

## Product principle

```text
CAOSCare helps the entire facility operate in order.
```

The resident remains central, but the system must also support kitchen, housekeeping, maintenance, caregiving, nursing/clinical scheduling, administration, fire drills, meal service, family communication, tasking, and shift handoff.

## Rollout principle

CAOSCare should not attempt to absorb the whole building at once.

Initial rollout should begin with the most operationally visible, least clinically regulated workflows:

```text
Phase 1: Maintenance + kitchen operations
Phase 2: Housekeeping + meal workflows
Phase 3: Fire drill / room-check workflows
Phase 4: Staff tasking + shift handoff
Phase 5: Clinical/nursing schedule support and care-team workflows
```

Clinical and nursing workflows are already more represented in the existing product direction, but non-clinical departments such as maintenance, kitchen, and housekeeping must be added as first-class operating surfaces.

## Problem statement

Many senior-care workflows are still paper-based, memory-based, radio-based, or verbally passed between staff.

This creates predictable failure modes:

```text
menus get lost
switchovers are missed or duplicated
resident refusals are not logged
radio chatter overlaps during drills or incidents
staff cannot see current building state
kitchen prep depends on habit instead of checklist
housekeeping work lacks clean status visibility
maintenance rounds depend on memory or scattered notes
nurse schedules and coverage are not visible enough to adjacent departments
meal service can be delayed by unclear order of operations
handoffs happen verbally and disappear
residents wait too long for meals or responses
leads cannot easily assign and verify work
```

CAOSCare must convert those workflows into structured operational records.

## Facility-wide scope

CAOSCare must support at least these operational surfaces:

```text
resident care and reminders
meal choice collection
meal service tracking
resident refusal tracking
resident switchover tracking
kitchen opening / prep / service / closing checklists
housekeeping room/task tracking
maintenance checklists and work orders
preventive maintenance rounds
nurse schedules and coverage visibility
clinical/care-team task visibility where permitted
fire drill participation and refusal logs
staff task assignment
shift handoff
maintenance requests
incident/escalation receipts
family/staff communication support
admin visibility and reporting
```

## Meal workflow requirements

Current paper meal workflows must be replaced or supplemented by tablet/computer workflows.

Required capabilities:

```text
upload or create daily/weekly menus
assign menu collection by resident/room
staff tablet view for room-by-room menu selection
resident choice entry
refusal entry
switchover entry
late change tracking
kitchen-visible meal counts
resident-specific notes and restrictions
service status tracking
time-to-serve visibility
meal delivery completion receipts
```

Meal records should answer:

```text
Who selected what?
Who entered it?
When was it entered?
Was it changed?
Was the resident a refusal?
Was it a switchover?
Was the meal served?
How long did it take?
Who completed the delivery?
```

## Fire drill / emergency drill workflow

Radio-only fire drill tracking is not sufficient.

Required capabilities:

```text
active drill mode
room-by-room resident status checklist
staff tablet/mobile entry
refusal status
resident location/status note
who checked the room
timestamped completion
unresolved resident list
admin/live command view
post-drill report
```

Example statuses:

```text
present and participating
refused / staying in room
not feeling well
out of room / location known
not found / needs follow-up
assisted by staff
requires escalation
```

The purpose is not to eliminate radio use, but to reduce chaotic radio chatter and preserve a real-time source of truth.

## Kitchen operations workflow

Kitchen work must become checklist-driven and repeatable.

Required capabilities:

```text
opening checklist
pre-meal prep checklist
service checklist
post-meal cleanup checklist
closing checklist
assigned duties by person/role
estimated time windows
completion checkoffs
time stamps
lead verification
missed/late task visibility
cleaning logs
```

Example kitchen opening/prep items:

```text
turn on lights
equipment startup
fryer/grill/oven readiness
temperature checks where applicable
prep assigned food items
verify menu and counts
prepare dining-area service first
prepare room/delivery meals after dining-area service if facility policy requires
clean surfaces during transitions
```

Example closing/cleanup items:

```text
wipe surfaces
wash/sanitize required areas
mop floors
trash removal
equipment shutdown
restock where needed
log exceptions
lead signoff
```

## Housekeeping workflow

Housekeeping must have the same operational visibility as care and kitchen work.

Required capabilities:

```text
room-by-room task assignment
daily/weekly/deep-clean task templates
status by room
refusal / unable-to-complete reason
notes and photo attachments where appropriate
completion receipts
lead/admin dashboard
handoff to maintenance when issue found
```

## Maintenance workflow

Maintenance must be a first-class CAOSCare operating surface, not an afterthought.

Required capabilities:

```text
work order intake
room/building-area assignment
priority and safety classification
preventive maintenance checklists
daily/weekly/monthly recurring inspections
life-safety equipment checks where appropriate
unit/room readiness checklists
move-in / move-out task lists
paint / repair / furniture / fixture tracking
photo notes and completion receipts
parts/materials needed
vendor/mover/outside-service tracking
handoff from housekeeping or care staff
completion timestamps
blocked/waiting status
```

Maintenance records should answer:

```text
What is broken or needed?
Where is it?
Who reported it?
Who owns it?
What priority is it?
Is it resident-impacting?
Is it safety-impacting?
What materials or outside services are needed?
Was it completed?
When was it completed?
Who verified it?
```

## Nursing / clinical schedule support

Clinical authority remains human and regulated. CAOSCare may support visibility, scheduling, task awareness, and handoff, but must not make autonomous clinical decisions.

Required support capabilities may include:

```text
nurse schedule visibility
coverage gaps / role coverage view
shift assignment visibility
care-team handoff notes
resident check task visibility
follow-up task visibility
incident/escalation linkage
clinical task reminders where authorized
read-only care context for non-clinical departments where permitted
```

Clinical/nursing workflows must preserve privacy, role-based access, and human authority.

The system must not expose clinical details to staff who do not need them for their role.

## Staff task assignment

Leads must be able to assign duties clearly.

Required capabilities:

```text
assign tasks by staff member
assign tasks by room/zone/department
set due times or shift windows
mark started/completed/skipped
require notes for skipped/refused work
show overdue items
show current workload by person
produce shift handoff summary
```

## Operational receipts

Every meaningful facility action should create a receipt.

Receipts should record:

```text
action type
resident/room/facility area if applicable
assigned staff
acting staff
status
timestamp
notes
reason for refusal/skipped status
source device or surface
follow-up required
```

## Human factors requirement

CAOSCare must be easy enough for working staff to use during real facility pressure.

Design requirements:

```text
large touch targets
fast room-by-room entry
minimal typing
clear status colors/icons
offline/poor-network tolerance where possible
simple undo/correction path
role-specific screens
no clutter during drills/incidents
```

## AI role in facility operations

AI should help organize, summarize, detect missed work, prepare handoffs, and surface possible patterns.

AI must not become an autonomous manager or clinical authority.

Allowed AI uses:

```text
summarize shift status
identify unresolved refusals
flag repeated late meal delivery
prepare kitchen/housekeeping/maintenance handoff
summarize drill completion gaps
summarize open work orders
surface overdue recurring checklist items
suggest follow-up questions
surface likely workflow bottlenecks
```

Restricted AI uses:

```text
autonomous disciplinary conclusions
autonomous clinical conclusions
autonomous emergency decisions without human workflow
unsupported claims about staff intent
unsupported claims about resident behavior
```

## Reporting requirements

The platform should eventually report:

```text
meal selection completion rate
meal delivery time
refusals by resident/day/meal
switchovers by resident/day/meal
fire drill participation status
room-check completion rate
housekeeping completion rate
kitchen checklist completion rate
maintenance work order completion rate
preventive maintenance completion rate
open/blocked maintenance tasks
nurse schedule coverage visibility where permitted
missed/late tasks
department workload patterns
recurring bottlenecks
```

Reports must distinguish fact from inference.

## Integration with memory

Operational records are not the same as personal memory, but they may produce memory candidates.

Examples:

```text
repeated meal preference may become a low-risk preference memory
repeated refusal may become a staff-review pattern
repeated pain/not-feeling-well note may become care-sensitive candidate
repeated maintenance issue may become a facility-context pattern
repeated housekeeping refusal may become an operational follow-up item
critical safety status must become alert/escalation first
```

All memory extraction from operations must follow the CAOSCare Memory Automation Contract.

## Immediate build modules

Initial modules should include:

```text
FacilityOperationsDashboard
MealWorkflow
MealMenuUpload
ResidentMealChoice
MealRefusalAndSwitchoverLog
FireDrillMode
RoomCheckStatus
KitchenChecklist
HousekeepingChecklist
MaintenanceChecklist
MaintenanceWorkOrders
PreventiveMaintenanceRounds
NurseScheduleView
StaffTaskAssignment
ShiftHandoffSummary
OperationalReceipt
```

## Non-negotiable

CAOSCare must help the whole building operate.

If a workflow currently depends on paper, radio chatter, memory, or informal verbal handoff, CAOSCare should evaluate whether it can become a structured, logged, staff-friendly workflow.

The goal is not more bureaucracy.

The goal is less chaos, faster service, clearer accountability, better resident experience, and staff support.
