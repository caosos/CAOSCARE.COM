# Unclaimed Nursing request escalation (careops-nursing-unclaimed-escalation-001), 2026-10-12

## Gap
The escalation tick (`escalation_tick.run_tick`) escalated only alerts. A Nursing request nobody claimed stayed
"pending, unassigned" with no supervisor signal.

## Built (`e2a8770`, labels `<this commit>`)
- `backend/routes/task_unclaimed_escalation.py`, called from the same tick (no new timer). A Nursing request still
  pending and unassigned `nursing_unclaimed_seconds` after it was raised (EscalationRule, default 600) is flagged
  once: atomic claim, then `task_lifecycle.transition` with the system actor → receipt `task_unclaimed_escalated`
  (authority `escalation_rule:<facility>:nursing_unclaimed`) chained to the origin. The request stays open.
  Assigned, closed and older-than-current (operations_currency "review") requests are skipped. No SMS/email.
- Routing exceptions: class `unclaimed`, listed while the request is still unassigned.
- Aria: "…no one has picked it up yet. Because no one has taken it, it has been flagged to a supervisor."
- Queue badge "Flagged to a supervisor: nobody claimed it in N min"; history and latest-action labels.

## Evidence
- `backend/tests/test_nursing_unclaimed_escalation.py`: not flagged before the threshold; two concurrent ticks + a
  repeated tick flag once (one receipt, one history entry with its receipt id, same workflow id as the origin);
  assigned and closed requests not flagged; Aria wording; admin sees it, maintenance does not; after claim it
  leaves the list and another tick adds nothing. Removing the atomic claim makes it fail.
- Live, dev backend `e2a8770` with the background tick (no rule change): the five old unassigned Nursing records
  (Aug 23–25) were not flagged. Demo request task_63bc1794b15d raised by a typed Aria call at 07:38:36 UTC was
  flagged by the tick at 07:49:01 (10 min), one receipt `system:escalation` on its chain. Owner in Claude Chrome:
  Routing exceptions "Unclaimed, flagged (1)" and the Nursing queue badge (`01`, `02`). Nurse at 390 px: badge,
  no overflow, no failed API calls (`03`). Maintenance: not listed for them. Aria rt_xl5l4ezc_1791791425175:
  "…Since it's been waiting, it's been flagged to a supervisor." Nurse claimed it; after two more ticks it was not
  listed and still had one flag receipt; then completed.
- Also seen: a typed request while an earlier one was open merged into it (dedup) and Aria said so truthfully.

## Gates
Backend 593 passed / 0 failed / 31 skipped at `e2a8770`; frontend 88 suites / 631; build compiled. Production
unchanged (`ff87c22`).

## Limits
Nursing only (`DEPARTMENTS`); one flag per request (no second-level re-escalation); the supervisor is informed
in CAOSCare only (no phone/email).
