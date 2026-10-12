# Housekeeping scheduled jobs (careops-housekeeping-schedule-001), 2026-10-12

## Inspected first
Housekeeping jobs are canonical StaffTasks; the shared queue's Plan sets `requested_for_date` /
`requested_for_time_label` with a receipt and the overlap check; `GET /tasks/upcoming` already orders by facility
day and time. Gap: no Housekeeping screen showed the upcoming schedule (only Therapy's workspace did).

## Changes
- `af52bfa`: `components/QueueWithUpcoming.jsx` — the queue with its "Upcoming" panel beside it, used by the
  housekeeper's `/workspace` and Admin → Housekeeping; the panel refreshes when the queue changes (it lagged up to
  20 s, seen live). Found on the way: a "Ride" button on a cleaning job — in-room departments (housekeeping,
  maintenance, kitchen) no longer offer or accept a ride (422; backend `task_ride_link.py` + frontend).
- `8d03c65`: Aria read only the newest of two planned housekeeping jobs ("10:00 AM"). `/resident-request/open`
  takes a `category`; when more than one is open in that department, Aria reads all of them.

## Live (dev backend `8d03c65`, demo room, synthetic resident)
1. Front desk (Demo - Dana Frost) entered two future jobs for the resident: deep clean, change linens.
2. Owner in Claude Chrome (Admin → Housekeeping): planned deep clean Oct 14 2:00 PM and linens Oct 13 10:00 AM;
   Upcoming listed them by facility date (Tomorrow, Oct 13 / Wednesday, Oct 14) right after saving (`01`).
3. Reschedule: deep clean → Oct 13 9:00 AM; it moved above linens (`02`). No overlap (one-hour slots).
4. Nurse rescheduling the deep clean: 403.
5. Housekeeper at 390 px on `/workspace`: Upcoming "Tomorrow, October 13 · 9:00 AM · 10:00 AM", no overflow, no
   failed API calls (`03`). Resident's own read (`/resident-request/upcoming`): both, in the same order.
6. Aria rt_dfwi8v3i_1791794082799: "You've got two housekeeping requests open. One is planned for 9:00 AM tomorrow
   for a deep clean, and the other is planned for 10:00 AM tomorrow…"
7. Housekeeper started and completed the deep clean; Upcoming then showed only the linens job.

Receipts (deep clean, one workflow id): resident_request_created (front_desk_entry) → task_schedule_updated
(admin_override:owner, before none → Oct 14 2:00 PM) → task_schedule_updated (Oct 14 2:00 PM → Oct 13 9:00 AM) →
task_in_progress (acts_for:housekeeping) → task_completed (assignee); no history entry without a receipt id.
The linens job stays open and planned for Oct 13 (demo data).

## Not in scope
Recurring jobs, inspections, supplies/linen tracking.

## Gates
Backend 594 passed / 0 failed / 31 skipped at `8d03c65`; frontend 88 suites / 633; build compiled. Dev backend loaded `8d03c65`. Production unchanged (`ff87c22`).
