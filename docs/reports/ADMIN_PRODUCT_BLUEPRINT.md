# CAOSCARE Admin / Community Operating Blueprint

_Last updated: 2026-08-23_

This document is the shared product map for Michael, ChatGPT-Aria, and Claude Code. Its purpose is to stop piecemeal tab-building and make CAOSCARE operate like the system a senior-living building actually runs on.

## 1. Product model: the hierarchy must exist before dependent objects can exist

CAOSCARE needs an explicit hierarchy:

**Company / Organization**
→ **Community / Facility**
→ **Departments + Staff + Front Desk**
→ **Residents + Rooms + Devices**
→ **Requests + Tasks + Scheduling + Transportation + Activities + Menus + Reports**

The application must not behave as though a community exists when none has been created.

### Required onboarding order

1. Create company / organization.
2. Create at least one community / facility under that company.
3. Configure the community's basic identity and operational settings.
4. Create/activate departments.
5. Add/invite staff and assign roles/departments.
6. Configure Front Desk / primary contact workflow.
7. Add residents and assign rooms.
8. Provision kiosks/devices/pendants and associate them with the correct community/resident/room.
9. Enable operational workflows: requests, calendars, transportation, activities, menus, reporting.

If a prerequisite is missing, CAOSCARE should show a clear setup action rather than silently displaying empty operational screens.

Examples:
- No company → show "Create organization" onboarding.
- Company exists but no community → show "Create community".
- Community exists but no departments → show "Set up departments".
- No staff → show "Invite staff".
- No Front Desk coverage/configuration → show "Set up Front Desk".

Dependent records should not be creatable against a nonexistent company/community context.

## 2. Scope: normal Admin is for one community

The normal CAOSCARE Admin experience is a **single-community operating workspace**.

An owner/admin working inside a community should see and operate that community. The main dashboard should not look like a corporate surveillance console for every community.

Future multi-community ownership is valid, but belongs in a separate owner/corporate context:

**Owner / Company view**
- company settings
- list of communities
- community health/summary as needed
- select/enter a community

**Community Admin view**
- operate the selected building
- departments/staff/front desk
- residents/rooms
- requests/tasks
- schedules/calendars
- transportation
- devices
- reports

Do not mix these contexts unnecessarily.

## 3. Visual acceptance is authoritative

A Mongo count or successful endpoint does not equal product completion.

Michael's browser is the authoritative acceptance surface.

For every feature Claude reports complete, the report must include:
- exact UI path
- what Michael should see
- what is clickable
- what action should work
- what persisted change/result should be visible afterward

If the database contains 16 residents but the intended Residents screen exposes only 7, the feature is not accepted until the UI discrepancy is understood and fixed.

## 4. Target top-level Community Admin navigation

The present information architecture is not the target.

Target direction:

1. **Departments & Staff**
2. **Residents & Care**
3. **Communication & Requests**
4. **Schedules & Transportation**
5. **Devices & Hardware**

Reports should not consume a scarce top-level slot merely because reports exist. Operational reporting should live where it is used, for example inside Communication & Requests and/or community operations.

The exact labels may evolve, but the ordering principle is:

**people/organization first → residents → communication/work → scheduling/resources → hardware**.

## 5. Departments are operational workspaces, not registry rows

Current implementation is only a registry: create, toggle active/inactive, delete. That is not sufficient.

Each department must be clickable and open a real department workspace.

A department workspace should support, as appropriate:
- department name / description
- active/inactive status
- contact information
- department lead
- staff assigned to the department
- staff coverage / availability
- open requests/tasks routed to the department
- pending / acknowledged / in-progress / completed work
- aging/overdue work
- current-day workload
- department-relevant schedule/calendar
- escalation/contact rules
- recent activity/history
- configurable routing behavior

Deleting a department must never silently destroy historical request/task records.

Inactive means unavailable for new routing, while historical records remain readable.

## 6. Staff and access must be real

A building cannot run on CAOSCARE if there is no coherent way for staff to exist and log in.

Required staff lifecycle:
- owner/admin invites/adds staff
- staff identity is associated with company and community
- role is assigned
- department(s) are assigned where applicable
- staff receives an authentication path
- staff can sign in and lands on an appropriate role dashboard
- staff can be deactivated without deleting historical actions

Roles should be operational, not decorative. Examples may include:
- owner
- community administrator / executive director
- front desk
- department manager
- general staff
- clinical role where appropriate
- driver / transportation

Exact role names remain configurable/architecture-driven; do not hard-code Michael's present test staffing as the permanent model.

## 7. Front Desk is a first-class module / role

Front Desk is not just another generic task category.

The Front Desk needs a focused daily workspace because it coordinates the building.

Expected Front Desk surface:
- residents + room directory
- today / upcoming appointments and transportation
- pending transportation requests
- rides needing confirmation/scheduling
- callback / front-desk requests
- unresolved resident requests relevant to front desk
- visitors / contact workflow when added later
- alerts requiring front-desk coordination
- today's community activities/schedule
- staff/department contact directory
- quick resident lookup
- clear links into the resident record and request history

Front Desk should not be forced to operate from a giant Owner/Admin console.

## 8. Residents & Care

Residents remain centered on a unified resident record.

Each resident should have:
- profile / identity
- room assignment
- kiosk/device association
- accessibility/communication preferences
- Aria memory
- family personalization
- complete conversation history
- requests/tasks
- transportation
- schedules/appointments where applicable
- activities/interests
- device history/status
- receipts/activity ledger

Admin must retain the direct **Enter Room** / real kiosk test path.

## 9. Communication & Requests

This area answers:

**Who asked for what, when, where is it routed, and what is happening with it now?**

At-a-glance fields should include:
- resident / room
- request text / normalized issue
- requested at
- requested by / source
- department
- priority
- status
- assignment
- age

Detail should expose the status timeline and related actions.

Reports/insights/audit/escalation can be accessible from this operating area rather than requiring a separate global top-level Reports group.

## 10. Scheduling / calendars must be calendars

A schedule screen should visibly show dates, not merely lists of records.

Required direction:
- actual day/week/month calendar views as appropriate
- visible dates and days of week
- click a date to see the items for that date
- click an item for detail
- resident/community/transport calendars draw from authoritative records
- status is visually understandable

Activities/programs, appointments, staffing where appropriate, and transportation may have different views but should share consistent calendar concepts rather than independent incompatible date systems.

## 11. Transportation needs an explicit process

A transportation request that says **Pending / not slotted yet** must have an understandable next step.

The product must distinguish:
- requested
- needs information
- pending scheduling
- scheduled/slotted
- confirmed
- driver assigned
- vehicle assigned where relevant
- in progress
- completed
- cancelled
- conflict

A transportation request is not a booking merely because a resident asked for it.

### Transportation calendar

The transportation calendar must show actual dates/days.

Desired interaction:
- calendar grid or clear dated day/week view
- select/click a day
- see trips/runs/riders for that day
- see pending unslotted requests that need action
- see conflicts
- see driver/vehicle assignment
- see shared rides where compatible

### Resources

Drivers and vehicles are separate resources.

Resource configuration should be understandable in human terms:
- driver identity / availability
- vehicle identity
- capacity if known/configured
- availability/status

Do not invent capacity, travel duration, or availability when the system does not know it.

## 12. Facility/community configuration

The current community must have a real facility record.

Minimum facility/community configuration should eventually include:
- community name
- address
- timezone
- phone / main contact
- Front Desk contact/routing
- basic operating configuration
- departments
- rooms/zones/floors/building map references
- transportation resources
- applicable device infrastructure

If the facility record does not exist, CAOSCARE should not pretend the downstream community operating environment is fully configured.

## 13. Dashboard philosophy

The community dashboard should answer operational questions, not maximize surveillance.

Useful questions include:
- what needs attention now?
- which requests are unacknowledged/aging?
- what transportation is pending today?
- what is scheduled today?
- which residents/rooms have current issues?
- which departments have open work?
- what system/device failures affect care operations?

Do not equate "kiosk online" with "resident physically present".

## 14. Blueprint-before-build rule

Before adding another major Admin tab/module, compare it against this map.

Do not create new disconnected surfaces merely because a backend model or endpoint exists.

For any major new feature, establish:
1. which company/community object owns it
2. which role uses it
3. where it appears in navigation
4. what human workflow it supports
5. what upstream prerequisites it needs
6. what downstream records/actions it creates
7. how Michael tests it from the browser

## 15. Current implementation priority

Voice remains the immediate engineering reliability priority from `CURRENT_DIRECTIVE.md`.

However, this blueprint is the governing structure for subsequent Admin/scheduling/calendar work. Do not continue willy-nilly Admin expansion while ignoring this map.

When Admin work resumes, first perform a gap inventory against this blueprint:
- WORKING
- PARTIAL
- BROKEN
- MISSING
- DUPLICATED / WRONG LOCATION

Then execute the highest-value workflow gaps in coherent milestones.

## 16. Standing engineering rules

- GitHub is the canonical shared project state.
- EliteDesk is the active development machine.
- Approximately 30-minute meaningful verified checkpoints → document → commit → push.
- Do not push knowingly broken main just to satisfy the clock.
- Handwritten production code normally stays around 300 lines or less.
- No God files; split by coherent responsibility.
- Reports/informational/generated/reference material are normal line-count exemptions.
- Inspect before destructive changes.
- Preserve evidence and historical records.

## 17. Working principle

CAOSCARE is not merely an AI chat interface with administrative tabs.

It is intended to become the operating system for the building:

**organization → community → people → residents → communication → work → schedules/resources → devices → history/verification.**

Every screen should make that operating model clearer, not more fragmented.
