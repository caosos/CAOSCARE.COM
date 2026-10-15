"""Real worker capacity: one active ticket per on-site worker, truthful queues.

Deterministic simulated-time scheduling over the whole 90-day plan.

* A resident's request opens at its real request time and waits in its
  department's canonical queue.
* Each ticket carries its own hands-on minutes
  (:data:`simulation.community_ticket_plan.ROUTINE_WORK_MINUTES`).
* It is claimed only by an on-site worker of that department who holds no
  other active ticket and whose shift covers the whole job, so work never
  continues after the worker leaves and nobody holds two tickets at once.
* Waiting is recorded with the blocker that held the ticket until its
  claim (the department's state the minute before): staff all busy,
  department closed, or only off-site on-call cover (routine work waits for
  on-site staff).
* Requests or work that would fall after the 90-day horizon are not
  planned; a ticket still waiting at the end stays open, truthfully.

Order is deterministic: higher priority first (aged one level per day waited),
then earliest request, then
workflow id; free workers are taken by fewest tickets so far, then actor id.
The same invariant is enforced against persisted state at execution time.
"""
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Optional

from simulation.community_coverage import department_status
from simulation.community_staffing import ON_CALL, ON_SITE, _day_rota
from simulation.community_ticket_plan import OPEN_TO_CLAIM_MINUTES

HORIZON_MINUTES = 90 * 1440
NO_WAIT = "none"
STAFF_BUSY = "waiting_for_available_staff"
DEPARTMENT_CLOSED = "waiting_for_department_opening"
ON_CALL_ONLY = "waiting_for_on_site_staff_on_call_only"
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


class _Windows:
    """On-site / on-call duty windows of one department, absolute minutes."""

    def __init__(self, department: str, horizon: int):
        rows = defaultdict(list)
        for day in range(-1, horizon // 1440 + 1):
            for row in _day_rota(day):
                if row["department"] != department:
                    continue
                start = day * 1440 + row["start_minute"]
                end = day * 1440 + row["end_minute"] + (1440 if row["spans_midnight"] else 0)
                rows[row["duty"]].append((start, end, row))
        self.on_site = sorted(rows[ON_SITE], key=lambda item: item[0])
        self.on_call = sorted(rows[ON_CALL], key=lambda item: item[0])
        self.starts = [start for start, _end, _row in self.on_site]

    def _active(self, windows, at: int) -> list:
        return [item for item in windows if item[0] <= at < item[1]]

    def present(self, at: int) -> list:
        # On-site windows are a few hours long; only recent starts can cover ``at``.
        index = bisect_right(self.starts, at)
        return [item for item in self.on_site[max(0, index - 40):index] if at < item[1]]

    def on_call_count(self, at: int) -> int:
        return len(self._active(self.on_call, at))

    def next_start_after(self, at: int) -> Optional[int]:
        index = bisect_right(self.starts, at)
        return self.starts[index] if index < len(self.starts) else None


def _reason(department: str, windows: _Windows, at: int) -> str:
    status = department_status(department, at % 1440, len(windows.present(at)),
                               windows.on_call_count(at))
    return {"on_call": ON_CALL_ONLY, "closed": DEPARTMENT_CLOSED}.get(status, STAFF_BUSY)


def _schedule_department(department: str, tickets: list, horizon: int) -> list[ScheduledTicket]:
    """``tickets``: (workflow_id, department, priority, requested_at, work_minutes)."""
    windows = _Windows(department, horizon)
    pending = sorted(tickets, key=lambda t: (t[3] + OPEN_TO_CLAIM_MINUTES, t[0]))
    busy_until, claims, ready, result = {}, defaultdict(int), [], []
    position, at = 0, None
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
        present = [(end, row) for _start, end, row in windows.present(at)
                   if busy_until.get(row["actor_id"], 0) <= at]
        present.sort(key=lambda item: (claims[item[1]["actor_id"]], item[1]["actor_id"]))
        waiting = []
        for ticket in ready:
            work = ticket[4]
            index = next((i for i, (end, _row) in enumerate(present)
                          if end >= at + work and at + work < horizon), None)
            if index is None:
                waiting.append(ticket)
                continue
            _end, worker = present.pop(index)
            eligible = ticket[3] + OPEN_TO_CLAIM_MINUTES
            busy_until[worker["actor_id"]] = at + work
            claims[worker["actor_id"]] += 1
            result.append(ScheduledTicket(
                ticket[0], department, ticket[3], at, at + work, worker,
                NO_WAIT if at == eligible else _reason(department, windows, at - 1),
                at - eligible,
            ))
        ready = waiting
        if not ready:
            continue
        candidates = [value for value in busy_until.values() if value > at]
        start = windows.next_start_after(at)
        if start is not None:
            candidates.append(start)
        if position < len(pending):
            candidates.append(pending[position][3] + OPEN_TO_CLAIM_MINUTES)
        if not candidates or min(candidates) >= horizon:
            break
        at = min(candidates)
    for ticket in ready + pending[position:]:
        result.append(ScheduledTicket(ticket[0], department, ticket[3], None, None,
                                      None, UNCLAIMED_AT_END, None))
    return result


def schedule_tickets(
    tickets: Iterable[tuple[str, str, str, int, int]], horizon: int = HORIZON_MINUTES,
) -> dict[str, ScheduledTicket]:
    """``tickets``: (workflow_id, department, priority, requested_at minute, work minutes)."""
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
