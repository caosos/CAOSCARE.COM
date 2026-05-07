# CAOSCare Operations Gap Map v1

## Status

Active planning map.

This document records the visible gap between the current CAOSCare application surfaces and the facility-wide operations platform direction.

## Current visible product strength

Current CAOSCare surfaces already strongly support resident/device/clinical-adjacent workflows.

Visible existing surfaces include:

```text
public landing page
kiosk demo
resident admin list
clinician dashboard
pendant registry
RF pendant support
wearable registry
smart-room devices
staff task list/templates
medication reminders
map / live zones
staff accounts
wall kiosks
geo zones
family contacts
notification log
device tokens / HMAC field-device authentication
pattern insights
compliance audit export
hardware receipts
escalation rules
phase-build roadmap
staff live alert dashboard
```

## Existing foundation to reuse

The existing `Tasks` surface is the best seed for facility operations.

It already models:

```text
daily workflow
templates
spawn today's tasks
status
shift
assigned staff
started timestamp
completed timestamp
duration
notes / receipts direction
```

This should be generalized rather than replaced.

Recommended evolution:

```text
StaffTask -> OperationalTask
StaffTaskTemplate -> OperationalTaskTemplate
Task category -> Department + WorkflowType
Task completion -> OperationalReceipt
```

## Main gap

The application currently has strong resident/device/clinical surfaces but lacks first-class operational department surfaces.

Missing or underdeveloped surfaces:

```text
maintenance command center
maintenance work orders
preventive maintenance rounds
maintenance checklist templates
move-in / move-out readiness workflow
vendor / mover / outside-service tracking
kitchen operations dashboard
kitchen opening / prep / service / closing checklists
meal menu upload / daily menu management
room-by-room meal choice collection
meal refusal / switchover tracking
meal service board
housekeeping room workflow
housekeeping status by room
fire drill / room-check live mode
department shift handoff
cross-department follow-up routing
```

## Build priority

Initial build should prioritize operational workflows that are high-pain, low-regulatory compared to clinical workflows.

Recommended order:

```text
1. Maintenance work orders + checklists
2. Kitchen checklist workflow
3. Meal selection / refusal / switchover workflow
4. Housekeeping room workflow
5. Fire drill / room-check workflow
6. Department handoff dashboard
7. Nursing/clinical schedule visibility where permitted
```

## Maintenance module requirements

Maintenance is a first pilot department.

Required entities:

```text
MaintenanceWorkOrder
MaintenanceChecklistTemplate
MaintenanceChecklistRun
MaintenanceChecklistItem
MaintenanceVendorEvent
MaintenanceMaterialNeed
RoomReadinessChecklist
MoveInMoveOutWorkflow
```

Required statuses:

```text
new
triaged
assigned
in_progress
blocked
waiting_parts
waiting_vendor
completed
verified
cancelled
```

Required fields:

```text
work_order_id
facility_id
room_or_area
resident_id optional
reported_by
assigned_to
priority
safety_impact
resident_impact
category
summary
description
photos optional
materials_needed
vendor_needed
status
due_at
started_at
completed_at
verified_by
notes
created_at
updated_at
```

## Kitchen module requirements

Kitchen is a first pilot department.

Required entities:

```text
KitchenChecklistTemplate
KitchenChecklistRun
KitchenChecklistItem
MealMenu
MealChoice
MealRefusal
MealSwitchover
MealServiceReceipt
```

Required workflow surfaces:

```text
opening checklist
pre-breakfast prep
breakfast service
post-breakfast cleanup
lunch prep
lunch service
post-lunch cleanup
dinner prep
dinner service
closing checklist
```

Meal records must track:

```text
resident
room
meal period
selected meal
selection source
entered_by
changed_by
refusal status
switchover status
served status
served_by
served_at
notes
```

## Housekeeping module requirements

Required entities:

```text
HousekeepingRoomTask
HousekeepingChecklistTemplate
HousekeepingChecklistRun
HousekeepingIssueHandoff
```

Required statuses:

```text
pending
in_progress
completed
refused
unable_to_complete
maintenance_needed
verified
```

Housekeeping must be able to hand off issues to maintenance with room, note, photo, and priority.

## Fire drill / room-check module requirements

Required entities:

```text
DrillEvent
RoomCheck
ResidentDrillStatus
DrillReceipt
```

Required live statuses:

```text
unchecked
checked_present
participating
refused_staying_in_room
not_feeling_well
out_of_room_location_known
not_found
assisted_by_staff
requires_escalation
```

The goal is to reduce radio chaos while preserving a live command view and post-drill report.

## Department handoff requirements

Required entities:

```text
DepartmentShift
ShiftHandoff
HandoffItem
FollowUpRoute
```

Handoff should summarize:

```text
open tasks
blocked tasks
resident-impacting issues
meal refusals/switchovers
maintenance blockers
housekeeping refusals
fire drill exceptions
notifications sent
items requiring supervisor attention
```

## Integration with existing surfaces

The new operations layer should reuse current CAOSCare surfaces where possible:

```text
Staff accounts -> assignment and accountability
Tasks -> operational task/checklist engine
Residents -> resident-linked work
Rooms/zones/map -> location context
Audit -> CSV and compliance exports
Notifications -> staff/family/vendor communication when appropriate
Escalation -> urgent unresolved operational events
Roadmap -> build tracking
```

## What not to do

Do not build each department as a disconnected one-off page.

Do not bury operations inside clinical workflows.

Do not use AI summaries as a substitute for timestamped operational receipts.

Do not expose clinical details to non-clinical roles unless explicitly permitted.

Do not make staff type long notes for every routine action.

## Acceptance standard

A workflow is considered operationally useful only when it can answer:

```text
What needed to happen?
Who owned it?
Who did it?
When did it happen?
Was it skipped, refused, blocked, or completed?
What follow-up is required?
Can a lead/admin verify it without chasing radio chatter or paper?
```

## Immediate next build target

The first implementation target should be:

```text
MaintenanceWorkOrders + MaintenanceChecklistTemplates
```

The second implementation target should be:

```text
KitchenChecklistTemplates + MealWorkflow foundation
```

These targets prove CAOSCare can operate outside resident-device/clinical surfaces and become a whole-building operating system.
