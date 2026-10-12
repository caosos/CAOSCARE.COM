# Recurring housekeeping work (careops-housekeeping-recurrence-001), 2026-10-12

## Inspected first — what was wrong
Recurring work existed as task templates + a manual "Spawn today's tasks" button, and none of the dev stack's
templates existed yet. Proven in the code:
- the form sent `recur` and `resident_id`, but the server's create model dropped them silently;
- spawn ignored `recur` (a weekly series would run daily), used UTC dates, gave occurrences no planned date/time
  and no department (all-staff), and ran only by hand;
- template create/delete wrote no receipt.

## Built (`6cb1f2c`, `93c3c58`)
- Series fields: daily / weekly with day of week, time, department, resident (room from the resident).
  Validation: weekly needs a day; department and resident must exist; owner/admin only. Create and delete receipted
  (`task_template_created` / `task_template_deleted`, before/after).
- `routes/task_recurrence.py`: one generator, run by the existing escalation tick and by "Generate now". Facility
  dates; weekly → the next 7 days on its weekday, daily → today and tomorrow. Each occurrence is created once
  (`occurrence_key` unique index; tasks already spawned from the same template that day count too), planned on its
  day/time in the department queue, with an origin receipt by `system:recurrence` (authority `template:<id>`).
  Rescheduling an occurrence never makes the series create another. Deleting a series stops new ones; existing
  occurrences stay.
- Residents see recurring jobs for them (status, Upcoming, Aria). Unclaimed escalation ignores occurrences planned
  for a later day. Tasks page: "Generate now", accurate copy and message (it would have shown "undefined").

## Evidence
- `backend/tests/test_housekeeping_recurrence.py`: 403 for staff, 422 for weekly without a day / unknown department;
  three runs (two concurrent) → one occurrence on Tuesday 2026-10-13 at 9:00 AM in Housekeeping; next week adds
  2026-10-20 only; rescheduled occurrence not refilled; nurse reschedule 403; resident Upcoming lists it;
  start/complete; one workflow id; delete stops generation and is receipted. Making the occurrence key unique per
  run (no dedupe) fails it.
- Live (dev backend `6cb1f2c`, then `93c3c58`; demo room): owner in Claude Chrome created "weekly room clean, every
  Wednesday 11:00 AM, Housekeeping, demo resident" (`01`); 23 s later the tick created task_b16bbe18883b for
  Wednesday Oct 14 11:00 AM (`system:recurrence`), shown in Admin → Housekeeping Upcoming (`02`); owner moved this
  occurrence to 1:00 PM (`03`); after more ticks still one occurrence, series still 11:00 AM; nurse reschedule 403;
  housekeeper at 390 px saw Oct 13 10:00 AM and Oct 14 1:00 PM, no overflow, no failed API calls (`05`); Aria
  rt_534cie2z_1791795162596 named both jobs and times; housekeeper completed it; "Generate now" then said
  "Nothing new: every due occurrence already exists" (`04`).
  Chain: task_spawned_from_template (system) → task_schedule_updated (owner) → task_in_progress → task_completed.

## Not in scope
Per-shift series, editing a series, inspections, supplies/linen.

## Gates
Backend 595 passed / 0 failed / 31 skipped at `93c3c58`; frontend 89 suites / 635; build compiled. Dev backend `93c3c58`. Production unchanged (`ff87c22`). (A first gate at `6cb1f2c` failed 2 old tests: the renamed response key and a staff-visibility assertion; both fixed in `93c3c58`.)
