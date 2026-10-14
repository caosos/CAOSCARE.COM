"""Which synthetic worker claims and completes each routine ticket.

Deterministic and pure.  Tickets are taken in claim order; each goes to the
on-site worker of its department who currently holds the fewest open tickets
(ties by actor id), so work spreads across everyone actually on shift.  The
worker who claims a ticket also completes it while still on site; otherwise
the ticket is handed to an on-site colleague at completion time.

This balances load but does not yet model a hard per-worker capacity: when
more tickets are due than staff on site, a worker may still hold several at
once.  ``peak_concurrent_tickets`` reports that truthfully.
"""
from collections import defaultdict
from typing import Iterable

from simulation.community_staffing import active_assignments


class TicketAssignmentError(RuntimeError):
    """A ticket phase has no on-site worker in its department."""


def _on_site(department: str, absolute_minute: int) -> list[dict]:
    day_index, minute = divmod(absolute_minute, 1440)
    return [row for row in active_assignments(day_index, minute)
            if row["department"] == department]


class _Load:
    def __init__(self):
        self.spans = defaultdict(list)

    def held(self, actor_id: str, at: int) -> int:
        return sum(start <= at < end for start, end in self.spans[actor_id])

    def least_loaded(self, workers: list[dict], at: int) -> dict:
        return min(workers, key=lambda row: (self.held(row["actor_id"], at), row["actor_id"]))


def assign_ticket_workers(tickets: Iterable[tuple[str, str, int, int]]) -> dict[str, tuple[dict, dict]]:
    """Map workflow id -> (claim worker, completion worker).

    ``tickets`` are ``(workflow_id, department, claim_minute, complete_minute)``
    in absolute simulated minutes.
    """
    load, result = _Load(), {}
    for workflow_id, department, claim_at, complete_at in sorted(
            tickets, key=lambda row: (row[2], row[0])):
        claimers = _on_site(department, claim_at)
        finishers = _on_site(department, complete_at)
        if not claimers or not finishers:
            raise TicketAssignmentError(f"ticket phase has no on-shift actor: {workflow_id}")
        claimer = load.least_loaded(claimers, claim_at)
        stays = any(row["actor_id"] == claimer["actor_id"] for row in finishers)
        finisher = claimer if stays else load.least_loaded(finishers, complete_at)
        if stays:
            load.spans[claimer["actor_id"]].append((claim_at, complete_at))
        else:
            # Handoff: the claimer holds it until leaving, the colleague after.
            load.spans[finisher["actor_id"]].append((complete_at, complete_at + 1))
        result[workflow_id] = (claimer, finisher)
    return result


def peak_concurrent_tickets(spans_by_actor: dict[str, list[tuple[int, int]]]) -> dict[str, int]:
    """Largest number of tickets any one worker holds at the same time."""
    peaks = {}
    for actor_id, spans in spans_by_actor.items():
        points = sorted([(start, 1) for start, _ in spans] + [(end, -1) for _, end in spans])
        current = peak = 0
        for _at, delta in points:
            current += delta
            peak = max(peak, current)
        peaks[actor_id] = peak
    return peaks
