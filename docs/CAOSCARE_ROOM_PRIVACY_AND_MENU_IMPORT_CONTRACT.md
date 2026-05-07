# CAOSCare Room Privacy and Menu Import Contract v1

## Status

Active product-scope contract.

This document defines how CAOSCare should handle building floor plans, room-based workflows, weekly menu import, room changes, and privacy-preserving operational views.

## Core principle

CAOSCare should use the least identifying information required for the workflow.

For many facility operations, staff do not need to see resident names. They need room, bed/slot, status, task, and completion state.

```text
Use room identity by default.
Use resident identity only when the workflow truly requires it.
```

## Room-based operating model

Operational workflows should support room and bed/slot identifiers independent of resident names.

Examples:

```text
101-A
101-B
214-A
214-B
316-A
316-B
T999-A
T999-B
```

For rooms with more than two occupants, support:

```text
room_number + occupant_slot
```

Examples:

```text
301-A
301-B
301-C
301-1
301-2
301-3
```

The exact display style should be configurable by facility.

## Privacy default

Privacy-sensitive dashboards should default to room/slot display.

Allowed default operational display:

```text
Room 214-A: breakfast selected
Room 214-B: refusal logged
Room 316-A: housekeeping complete
Room 101-A: maintenance follow-up needed
```

Avoid default display when not necessary:

```text
Resident full name + medical/care details + room + family contact
```

Resident names may be shown only when role, permission, and workflow require it.

## Role-based identity visibility

Identity visibility should be controlled by role and purpose.

Examples:

```text
Kitchen: room/slot, diet/allergy/texture flags only when authorized and required
Housekeeping: room/slot and service status; resident name usually hidden
Maintenance: room/area, issue, access notes; resident name hidden unless necessary
Clinical/nursing: resident identity visible as authorized
Admin: configurable full visibility
Family: only authorized resident/family-linked records
```

## Building schematic / floor plan import

CAOSCare should support uploading or configuring building layout/floor plans.

Required floor-plan concepts:

```text
facility
floor
wing
zone
room
bed/occupant slot
common area
restricted area
staff-only area
service area
kitchen area
maintenance area
housekeeping area
nurse station
emergency/fire drill route context
```

The system should support both visual floor plans and structured room/zone maps.

Initial implementation may use structured room/zone records before full schematic rendering.

## Room change workflow

Room changes must not break operational records.

Required behavior:

```text
resident-to-room assignment can change
room/slot operational history remains intact
resident care history follows the resident where permitted
room maintenance/housekeeping history stays with the room
meal workflow can operate by room/slot without exposing names
```

Room changes should create receipts:

```text
old_room_slot
new_room_slot
changed_by
changed_at
reason optional
notes optional
```

## Weekly menu import

CAOSCare should support weekly menu upload/import.

Acceptable import sources may include:

```text
PDF
image/photo
spreadsheet
CSV
manual entry
copied text
vendor/menu system export
```

The import workflow should produce structured menus:

```text
week_start_date
meal_period
menu_date
option_name
option_description
diet flags if authorized
texture flags if authorized
allergy warnings if authorized
availability
notes
```

## Menu workflow after import

Once a weekly menu is imported, CAOSCare should support room-by-room or resident-facing selection.

Required statuses:

```text
not_collected
selected
refused
switchover
changed
served
not_served
exception
```

Required receipt fields:

```text
room_slot
menu_date
meal_period
selected_option
status
entered_by
entered_at
changed_by
changed_at
served_by
served_at
notes
```

## Refusals and switchovers

Refusals and switchovers must be first-class records, not loose notes or radio chatter.

Definitions:

```text
refusal: resident declines meal/service/participation
switchover: resident changes from original meal/location/service path to another
```

Refusal/switchover records should capture:

```text
room_slot
workflow type
reason if known
staff entry
timestamp
follow-up required
resolved status
```

## Privacy-preserving meal board

Kitchen-facing meal boards should show only what kitchen needs.

Default kitchen view:

```text
room_slot
meal_period
selection
refusal/switchover status
diet/texture/allergy flags only when authorized and necessary
served status
notes limited to kitchen-relevant content
```

Kitchen should not see unrelated resident memory, family contacts, clinical notes, or private details.

## Privacy-preserving drill / room-check board

Fire drill and room-check boards should show room/slot status by default.

Default drill view:

```text
room_slot
status
checked_by
checked_at
follow-up required
```

Resident name should only be shown when necessary for safety and permitted by role.

## Operational memory boundary

Room-based operational records are not automatically personal memories.

Examples:

```text
Room 214-A refused lunch today = operational record
Repeated Room 214-A lunch refusal pattern = possible staff-review signal
Resident stated preference for soup = possible low-risk preference memory
```

Memory extraction must follow the CAOSCare Memory Automation Contract.

## Non-negotiable

CAOSCare must reduce unnecessary exposure of resident identity and private information.

If a workflow can be completed safely and accurately with room/slot identifiers, it should not require resident names by default.

The goal is operational clarity with privacy preservation.
