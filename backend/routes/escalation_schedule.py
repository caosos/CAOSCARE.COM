"""The escalation schedule: the one background loop that runs
escalation_tick.run_tick, and its health (careops-alerts-fallback-contract-001,
-loop-liveness-001, -loop-death-receipt-001).

Started and stopped by the server lifespan. Each change of the schedule's
state - healthy, failing (a tick raised), disabled (switched off at startup),
stopped (the loop ended without a shutdown) - is receipted once on
`escalation_schedule/default`, chained to the previous one; /api/health reads
`escalation_status()`. None of this touches alerts: they stay listed and
actionable, and nothing claims an escalation or a delivery.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone

from deps import db
from routes.escalation_tick import ACTOR_ID, run_tick
from routes.receipts import create_receipt

log = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 30


def auto_interval_seconds() -> int | None:
    """Schedule interval from CAOSCARE_ESCALATION_INTERVAL; None = disabled
    (CAOSCARE_ESCALATION_AUTO=0)."""
    if os.environ.get("CAOSCARE_ESCALATION_AUTO", "1").strip().lower() in ("0", "false", "no", "off"):
        return None
    try:
        return max(5, int(os.environ.get("CAOSCARE_ESCALATION_INTERVAL", DEFAULT_INTERVAL_SECONDS)))
    except ValueError:
        return DEFAULT_INTERVAL_SECONDS


_HEALTH = {"type": "escalation_schedule", "id": "default"}
_health_state: dict = {}   # in-process cache of the latest health receipt; loaded from receipts once
_ACTION = {"failing": "escalation_tick_failed", "healthy": "escalation_tick_recovered",
           "disabled": "escalation_schedule_disabled", "stopped": "escalation_schedule_stopped"}
_STATE_OF = {v: k for k, v in _ACTION.items()}
_RESULT = {"failing": "escalation tick failed; alerts stay open on the dashboard but are not escalated",
           "healthy": "escalation tick running",
           "disabled": "escalation schedule switched off at startup; alerts stay open on the dashboard but are not escalated",
           "stopped": "escalation loop ended unexpectedly; alerts stay open on the dashboard but are not escalated"}
_schedule: dict = {"task": None, "interval": None, "last_tick_at": None}   # this process's loop


async def _latest_health() -> dict:
    if "state" not in _health_state:
        last = await db.receipts.find_one(
            {"related_object_type": _HEALTH["type"], "related_object_id": _HEALTH["id"]},
            {"_id": 0, "receipt_id": 1, "action_type": 1}, sort=[("created_at", -1)])
        _health_state.update(state=_STATE_OF.get((last or {}).get("action_type"), "healthy"),
                             receipt_id=(last or {}).get("receipt_id"))
    return _health_state


async def _record_health(after: str, *, error: str | None = None, result: dict | None = None,
                         authority: str = "escalation_schedule") -> None:
    """Only a change of state is receipted (healthy / failing / disabled), so a
    tick that keeps failing, or a restart that stays switched off, leaves one
    record, not thousands."""
    h = await _latest_health()
    if h["state"] == after:
        return
    bad = after in ("failing", "stopped")
    detail = {"error": error} if bad else {"tick_result": result} if result else {}
    rcpt = await create_receipt(
        action_type=_ACTION[after], related_object_type=_HEALTH["type"], related_object_id=_HEALTH["id"],
        source="system", status="failed" if bad else "completed",
        result=_RESULT[after], failure_reason=error,
        provenance={"actor_id": ACTOR_ID, "actor_type": "system", "actor_name": "Escalation tick",
                    "authority": authority,
                    "before_state": {"tick": h["state"]},
                    "after_state": {"tick": after, **detail},
                    "parent_receipt_id": h["receipt_id"],
                    "result_label": "failed" if bad else "verified",
                    "next_state": {"failing": "retry_next_interval", "healthy": "escalating",
                                   "disabled": "not_escalating_until_enabled",
                                   "stopped": "not_escalating_until_restart"}[after]})
    h.update(state=after, receipt_id=rcpt["receipt_id"])


async def tick_once() -> None:
    """One scheduled pass: run the tick, and receipt a failure or a recovery."""
    _schedule["last_tick_at"] = datetime.now(timezone.utc)
    try:
        result = await run_tick()
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.warning("escalation tick failed: %s", e)
        try:
            await _record_health("failing", error=f"{type(e).__name__}: {e}"[:500])
        except Exception as e2:   # the receipt store itself may be what is down
            log.warning("could not record escalation tick failure: %s", e2)
        return
    try:
        await _record_health("healthy", result=result)
    except Exception as e:
        log.warning("could not record escalation tick recovery: %s", e)


async def run_escalation_loop(interval: int) -> None:
    """Background schedule. Never imports simulator code."""
    while True:
        await tick_once()
        await asyncio.sleep(interval)


async def start_schedule() -> asyncio.Task | None:
    """Called once from the server lifespan. Switched off -> receipted (once)
    and reported by /api/health; never silently absent."""
    interval = auto_interval_seconds()
    if interval is None:
        _schedule.update(task=None, interval=None)
        try:
            await _record_health("disabled", authority="env:CAOSCARE_ESCALATION_AUTO")
        except Exception as e:
            log.warning("could not record escalation schedule disabled: %s", e)
        return None
    task = asyncio.create_task(run_escalation_loop(interval))
    _schedule.update(task=task, interval=interval, last_tick_at=None, stopping=False,
                     started_at=datetime.now(timezone.utc))
    task.add_done_callback(_on_loop_end)
    return task


def _on_loop_end(task: asyncio.Task) -> None:
    """The loop never returns by design; if it ends and the lifespan did not
    stop it, receipt the stop once (the recorder skips an unchanged state)."""
    if _schedule.get("stopping") and task is _schedule.get("task"):
        return
    if task.cancelled():
        error = "CancelledError: loop cancelled without a server shutdown"
    else:
        exc = task.exception()
        error = f"{type(exc).__name__}: {exc}"[:500] if exc else "loop returned"
    log.warning("escalation loop ended: %s", error)

    async def record():
        try:
            await _record_health("stopped", error=error)
        except Exception as e:
            log.warning("could not record escalation loop stop: %s", e)
    _schedule["stop_record"] = asyncio.get_event_loop().create_task(record())   # keep a reference


async def stop_schedule() -> None:
    """Server shutdown: an intentional stop, not a failure."""
    task = _schedule.get("task")
    _schedule["stopping"] = True
    if task and not task.done():
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


def escalation_status(now: datetime | None = None) -> dict:
    """Read-only: what /api/health reports. Only "running" means escalation is happening."""
    now = now or datetime.now(timezone.utc)
    task, interval, last = _schedule["task"], _schedule["interval"], _schedule["last_tick_at"]
    if task is None:
        state = "disabled"
    elif task.done():
        state = "stopped"
    elif last is None:
        state = "starting"
    elif (now - last).total_seconds() > 3 * interval + 60:
        state = "stale"
    elif _health_state.get("state") == "failing":
        state = "failing"
    else:
        state = "running"
    return {"state": state, "interval_seconds": interval, "last_tick_at": last.isoformat() if last else None}
