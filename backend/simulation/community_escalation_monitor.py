"""Loop hook: run simulated escalation at most once per simulated minute.

The community loop calls this with the RUNNING run's simulated minute before
each tick.  It reads tickets and receipts and writes escalation receipts,
notification records and task history only; it never touches the run row,
cursor, plan revision or plan digest, so the running plan stays valid.

A failure is logged and kept on :attr:`EscalationMonitor.last_error`; it is
never raised into the loop.  The minute is consumed even when it fails, so a
broken pass is retried on the next simulated minute rather than hammered.
"""
import logging
from datetime import datetime
from typing import Awaitable, Callable, Optional

from simulation.community_escalation import escalate_overdue

logger = logging.getLogger(__name__)
Escalator = Callable[..., Awaitable[dict]]


class EscalationMonitor:
    def __init__(self, *, store, escalate: Escalator = escalate_overdue):
        self.store, self.escalate = store, escalate
        self._last_minute: dict[str, int] = {}
        self.passes = 0
        self.errors = 0
        self.last_error: Optional[str] = None
        self.last_summary: Optional[dict] = None

    async def __call__(self, *, run_id: str, sim_minute: int, now: datetime) -> Optional[dict]:
        if self._last_minute.get(run_id) == sim_minute:
            return None
        self._last_minute[run_id] = sim_minute
        try:
            summary = await self.escalate(self.store, run_id, sim_minute, now=now)
        except Exception as exc:  # noqa: BLE001 - escalation must never stop the loop
            self.errors += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("simulated escalation failed for run %s at minute %s: %s",
                           run_id, sim_minute, self.last_error)
            return None
        self.passes += 1
        self.last_summary = summary
        if summary.get("escalated"):
            logger.info("simulated escalation run %s minute %s: %d level(s) escalated",
                        run_id, sim_minute, len(summary["escalated"]))
        return summary
