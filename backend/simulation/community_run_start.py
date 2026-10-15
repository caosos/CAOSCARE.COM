"""A run that starts on the real clock, mid-day, without inventing the morning.

Michael, 2026-10-14: the simulator is for working a department in real time,
closing tickets as they arrive, not for racing through days. A run created
with ``start_minute`` begins its simulated clock at that minute of day 0 (the
facility's real local time when it was created) and runs at 1x.

Plan events that would have happened before the start - a ticket whose
request time is earlier, a shift milestone earlier in the day - are not
simulated and not skipped silently: each gets one ``cancelled`` executor
receipt saying it was before the run started, so the cursor and the receipt
chain stay complete and nothing is claimed to have happened.
"""
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_executor import ExecutionContext, ExecutorEvent

FACILITY_TZ = ZoneInfo("America/Chicago")


def local_minute_of_day(now: datetime) -> int:
    """The facility's local minute of day (0..1439) at ``now``."""
    local = now.astimezone(FACILITY_TZ)
    return local.hour * 60 + local.minute


def origin_minute(event: ExecutorEvent) -> int:
    """When the event's work began: a ticket's request time, else its own time."""
    if event.requested_at_minute is not None:
        return event.requested_at_minute
    return event.day_index * 1440 + event.minute


async def run_start_minute(store, run_id: str, cache: dict) -> int:
    if run_id not in cache:
        row = await store.sim_runs.find_one({"run_id": run_id}, {"_id": 0, "started_at_minute": 1})
        cache[run_id] = int((row or {}).get("started_at_minute") or 0)
    return cache[run_id]


async def record_before_start(receipt_writer, authority: str, event: ExecutorEvent,
                              context: ExecutionContext, start: int) -> dict:
    """One ``cancelled`` receipt: this planned event predates the run's start."""
    hh, mm = divmod(start % 1440, 60)
    return await receipt_writer(
        action_type=event.action_type,
        related_object_type=event.target_type,
        related_object_id=event.target_id,
        source="simulator",
        resident_id=event.target_id if event.target_type == "resident" else None,
        assigned_role=event.department,
        status="cancelled",
        result=(f"Not simulated: planned before this run started at {hh:02d}:{mm:02d} "
                "facility time. Nothing was done or claimed."),
        provenance={
            "actor_id": event.actor_id,
            "actor_type": event.actor_type,
            "identity_basis": event.identity_basis,
            "channel": "simulator",
            "name": event.actor_name,
            "simulated": True,
            "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
            "simulation_run_id": context.run_id,
            "simulation_event_id": event.event_id,
            "execution_cursor": context.cursor,
            "execution_fence": context.fence,
            "authority": authority,
            "before_state": None,
            "after_state": {"not_simulated_before_run_start": True, "run_started_at_minute": start},
            "result_label": "not_simulated",
            "provider_refs": [],
            "next_state": "executor_cursor_ready",
        },
    )


def before_start(event: ExecutorEvent, start: Optional[int]) -> bool:
    return bool(start) and origin_minute(event) < start
