# Recurring therapy appointments (careops-therapy-recurrence-001), 2026-10-12

## Gaps found (in order)
1. A series could not carry provider, discipline or location, so therapy occurrences lost the appointment details.
2. Admin had no Therapy tab: the owner could not see the Therapy queue or its upcoming schedule.
3. Live: "When is my physical therapy this week?" → Aria called the activities calendar seven times (one per day),
   which knows nothing about the resident's own appointments, said none was planned although it existed, and the
   seven parallel calls produced six "active response" errors (one reply requested per call).

## Changes
- `92aa098`: series fields provider/discipline/location (same limits as visit details, blanks dropped), inherited by
  every occurrence; template form "With / Kind / Where"; series table shows them.
- `9571aa0`: Admin → Community → Therapy (queue + Upcoming); the overview's Therapy card opens it.
- `468cbc8`: the schedule tool's answer adds the resident's own planned appointments for that day; its description
  points "this week" questions at `check_request_status`; the handler sends ONE reply after the last of several
  concurrent tool calls (test fails on the old handler).

## Evidence
- `backend/tests/test_therapy_recurrence.py`: details on both weekly occurrences; concurrent runs create each once;
  reschedule one and cancel another without refill and without changing the series; housekeeper 403; resident
  upcoming carries the provider; cancelled one not upcoming; Aria status names provider and new time; lifecycle
  receipts. Dropping the details from the generator fails it.
- Live (dev backend `468cbc8`; demo room; there is no therapy staff account on the dev stack, so the therapist side
  is covered by the test): owner in Claude Chrome created "knee physical therapy, every Wednesday 10:00 AM, Therapy,
  With Demo - Pat Lee, PT (Physical therapy), Where Therapy gym" (`01`); the tick created task_c747430cd480 for
  Wed Oct 14 with all details; Admin → Therapy showed it in the queue and Upcoming (`02`); owner moved it to Thu
  Oct 15 2:00 PM (`03`); housekeeper reschedule → 403; resident room screen at 390 px "Coming up — Thursday,
  October 15, 2:00 PM … With: Demo - Pat Lee, PT (Physical therapy) · Where: Therapy gym", no failed API calls
  (`05`; the page's 390 px horizontal overflow is the known pre-existing accessibility-row issue); after the fix,
  Aria rt_tsujpccx_1791798467141: "It's currently planned for Thursday, October 15th at 2:00 PM in the therapy
  gym…" (one lookup, no errors); owner cancelled it with a reason (`04`); after more ticks still one occurrence and
  the series unchanged (Wednesday 10:00 AM). Chain: spawned_from_template → schedule_updated → cancelled.

## Gates
Backend 600 passed / 0 failed / 31 skipped at `468cbc8` (also at `92aa098`); frontend 90 suites / 641; build
compiled. Production unchanged (`ff87c22`).
