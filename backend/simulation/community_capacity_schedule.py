"""Real worker capacity: one active ticket per qualified worker, truthful queues.

Deterministic simulated-time scheduling over the whole 90-day plan.

* A resident's request opens at its real request time and waits in its
  department's canonical queue.
* Each ticket carries its own hands-on minutes
  (:data:`simulation.community_ticket_plan.ROUTINE_WORK_MINUTES`).
* It is claimed only by an on-site worker of that department whose job role
  may do the routine (:mod:`simulation.community_role_eligibility`, most
  preferred role first), who holds no other active ticket and whose shift
  covers the whole job.  Nobody holds two tickets at once and no ticket goes
  to an unqualified worker.
* With no qualified worker on site, a high or urgent ticket calls in the
  on-call worker, who claims it after a response delay
  (:mod:`simulation.community_on_call`); other work waits for on-site hours.
* A meal or activity not claimed before its service window closes is not
  served (:mod:`simulation.community_service_windows`); the department lead
  closes it, rather than serving dinner the next morning.
* Every waited minute is attributed to the blocker of that minute
  (:mod:`simulation.community_wait_blockers`); ``wait_reason`` is the
  dominant blocker over the whole wait.
* Requests or work that would fall after the 90-day horizon are not
  planned; a ticket still waiting at the end stays open, truthfully.

Order is deterministic: higher priority first (aged one level per day
waited), then earliest request, then workflow id; free qualified workers are
taken by role preference, then fewest tickets so far, then actor id.  The
one-active-ticket rule is also enforced against persisted state.
"""
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Optional

from simulation import community_wait_blockers as blockers
from simulation.community_on_call import call_in
from simulation.community_role_eligibility import eligible_roles, role_rank
from simulation.community_service_windows import NOT_SERVED, department_lead, service_deadline
from simulation.community_staffing import ON_CALL, ON_SITE
from simulation.community_ticket_plan import OPEN_TO_CLAIM_MINUTES

HORIZON_MINUTES = 90 * 1440
NO_WAIT = blockers.NO_WAIT
STAFF_BUSY = blockers.STAFF_BUSY
QUALIFIED_ABSENT = blockers.QUALIFIED_ABSENT
DEPARTMENT_CLOSED = blockers.DEPARTMENT_CLOSED
ON_CALL_ONLY = blockers.ON_CALL_ONLY
ON_CALL_RESPONSE = blockers.ON_CALL_RESPONSE
UNCLAIMED_AT_END = "still_waiting_at_simulation_end"
_PRIORITY_RANK = {"urgent": 0, "high": 1, "normal": 2, "low": 3}


@dataclass(frozen=True)
class ScheduledTicket:
    workflow_id: str
    department: str
    requested_at: int
    claim_at: Optional[int]
    complete_at: Optional[int]
    worker: Optional[dict]
    wait_reason: str
    waited_minutes: Optional[int]
    # Minutes per blocker over the whole wait; sums to the waited minutes.
    wait_breakdown: tuple = ()
    called_in_on_call: bool = False
    # A time-bound ticket closed unserved when its window ended, and by whom.
    expire_at: Optional[int] = None
    expired_by: Optional[dict] = None


class _Windows:
    """On-site / on-call duty windows of one department, absolute minutes."""

    def __init__(self, department: str, horizon: int):
        rows = blockers.duty_windows(department, horizon)
        self.on_site, self.on_call = rows[ON_SITE], rows[ON_CALL]
        self.starts = [start for start, _end, _row in self.on_site]
        self.call_starts = [start for start, _end, _row in self.on_call]

    def present(self, at: int) -> list:
        # On-site windows are a few hours long; only recent starts can cover ``at``.
        index = bisect_right(self.starts, at)
        return [item for item in self.on_site[max(0, index - 40):index] if at < item[1]]

    def on_call_at(self, at: int) -> list:
        return [item for item in self.on_call if item[0] <= at < item[1]]

    def next_start_after(self, at: int, roles: Optional[tuple] = None,
                         starts: Optional[list] = None) -> Optional[int]:
        windows, marks = (self.on_site, self.starts) if starts is None else (self.on_call, starts)
        for index in range(bisect_right(marks, at), len(marks)):
            if roles is None or windows[index][2]["job_role"] in roles:
                return marks[index]
        return None


def _ticket(row: tuple):
    """(workflow_id, department, priority, requested_at, work_minutes, routine)."""
    return row[0], row[1], row[2], row[3], row[4], row[5]


class _Department:
    """One department's capacity schedule (the state of one sweep)."""

    def __init__(self, department: str, horizon: int):
        self.department, self.horizon = department, horizon
        self.windows = _Windows(department, horizon)
        self.busy_until, self.on_site_until, self.claims = {}, {}, defaultdict(int)
        self.result = []

    def _finish(self, ticket, end: int, **fields) -> None:
        eligible = eligible_roles(self.department, ticket[5])
        start = ticket[3] + OPEN_TO_CLAIM_MINUTES
        breakdown = blockers.wait_breakdown(self.department, eligible, start, end, self.horizon,
                                            called_in=fields.get("called_in_on_call", False))
        reason = fields.pop("reason", None) or blockers.dominant(breakdown)
        self.result.append(ScheduledTicket(
            ticket[0], self.department, ticket[3], wait_reason=reason,
            waited_minutes=end - start if fields.get("claim_at") is not None else None,
            wait_breakdown=breakdown, **{"claim_at": None, "complete_at": None, "worker": None, **fields}))

    def _book(self, ticket, at: int, worker: dict, claim: int, *, called_in: bool = False) -> None:
        actor = worker["actor_id"]
        self.busy_until[actor] = claim + ticket[4]
        if called_in:
            self.on_site_until[actor] = claim + ticket[4]
        self.claims[actor] += 1
        self._finish(ticket, claim, claim_at=claim, complete_at=claim + ticket[4], worker=worker,
                     called_in_on_call=called_in)

    def _expire(self, ticket, deadline: int) -> None:
        lead = department_lead(self.windows.present(deadline - 1))
        if lead is None:  # nobody on site to close it: it stays open, truthfully
            self._finish(ticket, min(self.horizon, deadline), reason=UNCLAIMED_AT_END)
            return
        self._finish(ticket, deadline, reason=NOT_SERVED, expire_at=deadline, expired_by=lead)

    def assign(self, ready: list, at: int) -> list:
        """Claim what can be claimed at ``at``; return the tickets still waiting."""
        present = [(end, row) for _start, end, row in self.windows.present(at)
                   if self.busy_until.get(row["actor_id"], 0) <= at]
        waiting = []
        for ticket in ready:
            deadline = service_deadline(ticket[5], ticket[3])
            if deadline is not None and at >= deadline:
                self._expire(ticket, deadline)
                continue
            eligible, work = eligible_roles(self.department, ticket[5]), ticket[4]
            options = [(role_rank(eligible, row["job_role"]), self.claims[row["actor_id"]],
                        row["actor_id"], index)
                       for index, (end, row) in enumerate(present)
                       if role_rank(eligible, row["job_role"]) is not None
                       and end >= at + work and at + work < self.horizon]
            if options:
                _end, worker = present.pop(min(options)[3])
                self._book(ticket, at, worker, at)
                continue
            if not any(row["job_role"] in eligible for _s, _e, row in self.windows.present(at)):
                called = call_in(
                    department=self.department, priority=ticket[2], eligible=eligible, at=at,
                    work=work, horizon=self.horizon, on_call_rows=self.windows.on_call_at(at),
                    busy_until=self.busy_until, on_site_until=self.on_site_until,
                    next_on_site_start=self.windows.next_start_after(at, eligible))
                if called is not None:
                    self._book(ticket, at, called[1], called[0], called_in=True)
                    continue
            waiting.append(ticket)
        return waiting

    def wake_after(self, at: int, next_arrival: Optional[int]) -> Optional[int]:
        candidates = [value for value in self.busy_until.values() if value > at]
        for start in (self.windows.next_start_after(at),
                      self.windows.next_start_after(at, starts=self.windows.call_starts), next_arrival):
            if start is not None:
                candidates.append(start)
        return min(candidates) if candidates else None


def _schedule_department(department: str, tickets: list, horizon: int) -> list[ScheduledTicket]:
    """``tickets``: (workflow_id, department, priority, requested_at, work_minutes, routine)."""
    sweep = _Department(department, horizon)
    pending = sorted((_ticket(t) for t in tickets), key=lambda t: (t[3] + OPEN_TO_CLAIM_MINUTES, t[0]))
    ready, position, at = [], 0, None
    while position < len(pending) or ready:
        if not ready:
            at = max(at or 0, pending[position][3] + OPEN_TO_CLAIM_MINUTES)
        while position < len(pending) and pending[position][3] + OPEN_TO_CLAIM_MINUTES <= at:
            ready.append(pending[position])
            position += 1
        # A work order that has waited a full day moves up one priority level
        # per day waited, as a real department escalates old orders, so low
        # priority work is never starved by a steady stream of newer requests.
        ready.sort(key=lambda t: (max(0, _PRIORITY_RANK.get(t[2], 2) - (at - t[3]) // 1440), t[3], t[0]))
        ready = sweep.assign(ready, at)
        if not ready:
            continue
        next_arrival = pending[position][3] + OPEN_TO_CLAIM_MINUTES if position < len(pending) else None
        wake = sweep.wake_after(at, next_arrival)
        if wake is None or wake >= horizon:
            break
        at = wake
    for ticket in ready + pending[position:]:
        deadline = service_deadline(ticket[5], ticket[3])
        if deadline is not None and deadline < horizon:
            sweep._expire(ticket, deadline)
        else:
            sweep._finish(ticket, horizon, reason=UNCLAIMED_AT_END)
    return sweep.result


def schedule_tickets(
    tickets: Iterable[tuple[str, str, str, int, int, str]], horizon: int = HORIZON_MINUTES,
) -> dict[str, ScheduledTicket]:
    """``tickets``: (workflow_id, department, priority, requested_at, work minutes, routine)."""
    by_department = defaultdict(list)
    for ticket in tickets:
        if ticket[3] < horizon:
            by_department[ticket[1]].append(ticket)
    scheduled = {}
    for department, rows in sorted(by_department.items()):
        for row in _schedule_department(department, rows, horizon):
            scheduled[row.workflow_id] = row
    return scheduled


def peak_active_tickets(scheduled: Iterable[ScheduledTicket]) -> dict[str, int]:
    """Largest number of tickets each worker holds at the same moment."""
    points = defaultdict(list)
    for row in scheduled:
        if row.worker is not None:
            points[row.worker["actor_id"]] += [(row.claim_at, 1), (row.complete_at, -1)]
    peaks = {}
    for actor_id, marks in points.items():
        current = peak = 0
        for _at, delta in sorted(marks):
            current += delta
            peak = max(peak, current)
        peaks[actor_id] = peak
    return peaks
