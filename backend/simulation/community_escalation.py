"""Overdue simulated tickets escalate to the on-duty lead, once per level.

Real escalation (``routes/escalation_tick.py``) deliberately excludes the
living community; this is the simulator's own, measured in SIMULATED minutes
on the run's facility clock against
:mod:`simulation.community_response_thresholds`.

Truth sources, never guesses:

* the request minute is the executor OPEN receipt's ``requested_at_minute``;
* the claim minute is derived from the executor CLAIM receipt
  (``requested_at_minute + OPEN_TO_CLAIM_MINUTES + waited_minutes``);
* a ticket whose receipts cannot prove those minutes is reported
  ``unknown`` and is not escalated;
* who was told comes from the roster at that simulated minute
  (:mod:`simulation.community_escalation_leads`); nobody reachable is
  recorded as exactly that.

Each NEW level (1 = threshold reached -> department lead; 2 = twice the
threshold -> supervisor) writes exactly once, per phase (``pickup`` while
pending, ``complete`` while in progress): a receipt, a ``simulated``
notification record (never a provider), and an ``escalated`` event_log entry
with the level stored on the task.  Receipt and notification ids are
derived from (run, task, phase, level), so a retry after a partial write
reuses them instead of paging again.  These receipts carry no
``simulation_event_id``/``execution_cursor``: they are not executor events and
never enter the runner's cursor evidence window.
"""
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Awaitable, Callable, Optional

from routes.actor_context import ActorContext
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_capacity_schedule import HORIZON_MINUTES
from simulation.community_escalation_leads import lead_for, on_site_since
from simulation.community_response_thresholds import thresholds_for
from simulation.community_ticket_plan import OPEN_TO_CLAIM_MINUTES

ESCALATION_ACTION = "simulated_ticket_escalated"
MONITOR_AUTHORITY = "living_community_escalation_monitor"
EXECUTOR_AUTHORITY = "living_community_executor"
SESSION_PREFIX = "simulator:event:"
PICKUP, COMPLETE = "pickup", "complete"
MAX_LEVEL = 2
NO_LEAD = "no lead reachable"
MONITOR = ActorContext(
    actor_id="sim:system:escalation_monitor", actor_type="simulated-agent",
    identity_basis="synthetic", channel="simulator", name="SIM - Escalation monitor",
    role="system", simulated=True,
)


async def _default_receipt(**kwargs) -> dict:
    from routes.receipts import create_receipt
    return await create_receipt(**kwargs)


async def _default_task_update(task_id: str, set_fields: dict, entries: list) -> None:
    from routes.task_history import update_task_with_history
    await update_task_with_history(task_id, set_fields, entries)


async def _default_notification(doc: dict) -> dict:
    from routes.notification_delivery import _save
    return await _save(doc)


@dataclass(frozen=True)
class EscalationWriters:
    """Injected write boundary; defaults are the canonical writers."""
    receipt_writer: Callable[..., Awaitable[dict]] = _default_receipt
    task_updater: Callable[[str, dict, list], Awaitable[None]] = _default_task_update
    notification_saver: Callable[[dict], Awaitable[dict]] = _default_notification


def ticket_kind(routine: Optional[str]) -> str:
    """A resident's own call, a worker's report, or scheduled routine care."""
    routine = routine or ""
    if routine.startswith("resident_call_"):
        return "resident_call"
    if routine.startswith("staff_report_"):
        return "staff_report"
    return "scheduled_routine"


def _int(value) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def phase_minutes(task: dict, open_receipt: Optional[dict], claim_receipt: Optional[dict]) -> dict:
    """Request/claim minutes proven by the executor receipts (None if not proven)."""
    opened = (open_receipt or {}).get("after_state") or {}
    claimed = (claim_receipt or {}).get("after_state") or {}
    requested = _int(opened.get("requested_at_minute"))
    started = None
    if (claim_receipt and claim_receipt.get("status") == "completed"
            and _int(claimed.get("requested_at_minute")) == requested
            and requested is not None and _int(claimed.get("waited_minutes")) is not None):
        started = requested + OPEN_TO_CLAIM_MINUTES + claimed["waited_minutes"]
    return {"requested": requested, "started": started,
            "routine": (open_receipt or {}).get("action_type")}


def measure(task: dict, minutes: dict, sim_minute: int, cell: dict) -> dict:
    """How long this ticket has waited against its threshold, and which level.

    ``outcome`` is ``measured``, ``unknown`` (receipts cannot prove the
    minute), ``not_due`` (scheduled care before its minute) or ``deferred``
    (routine work while its department has nobody on site).
    """
    kind = ticket_kind(minutes["routine"])
    requested = minutes["requested"]
    if requested is None:
        return {"outcome": "unknown", "kind": kind}
    if sim_minute < requested:
        return {"outcome": "not_due", "kind": kind}
    if task.get("status") == "pending":
        phase, threshold, anchor, clock = PICKUP, cell["pickup_minutes"], requested, cell["clock"]
        if clock == "on_site":
            since = on_site_since(task.get("category"), sim_minute)
            if since is None:
                return {"outcome": "deferred", "kind": kind, "phase": phase}
            anchor = max(requested, since)
    else:
        started = minutes["started"]
        if started is None:
            return {"outcome": "unknown", "kind": kind}
        # Scheduled care is measured for completion only after its scheduled
        # minute; a resident's call or a staff report from its claim.
        anchor = max(started, requested) if kind == "scheduled_routine" else started
        phase, threshold, clock = COMPLETE, cell["complete_minutes"], "continuous"
    waited = max(0, sim_minute - anchor)
    level = min(MAX_LEVEL, waited // threshold)
    return {"outcome": "measured", "kind": kind, "phase": phase, "threshold": threshold,
            "anchor": anchor, "clock": clock, "waited": waited, "level": level}


def _ids(run_id: str, task_id: str, phase: str, level: int) -> tuple[str, str]:
    digest = sha256(f"{run_id}:{task_id}:{phase}:{level}".encode()).hexdigest()[:24]
    return f"rcpt_simesc_{digest}", f"notif_simesc_{digest}"


def _done_level(task: dict, phase: str) -> int:
    record = ((task.get("simulated_escalation") or {}).get(phase) or {})
    return _int(record.get("level")) or 0


async def _receipts(store, run_id: str, event_ids: list[str]) -> dict[str, dict]:
    if not event_ids:
        return {}
    rows = await store.receipts.find({
        "simulation_run_id": run_id, "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID, "authority": EXECUTOR_AUTHORITY,
        "simulation_event_id": {"$in": event_ids},
    }, {"_id": 0}).to_list(None)
    return {row["simulation_event_id"]: row for row in rows}


async def _escalate_level(store, writers: EscalationWriters, *, run_id: str, task: dict,
                          parent: dict, measured: dict, level: int, sim_minute: int,
                          now: datetime) -> dict:
    phase, department = measured["phase"], task.get("category")
    receipt_id, notification_id = _ids(run_id, task["task_id"], phase, level)
    lead = lead_for(level, department, sim_minute)
    told = f"{lead['name']} ({lead['status'].replace('_', ' ')})" if lead else NO_LEAD
    crossed = measured["anchor"] + measured["threshold"] * level
    waited_label = "unclaimed" if phase == PICKUP else "in progress"
    text = (f"Simulated escalation level {level}: {department} {task.get('priority')} ticket "
            f"{waited_label} {measured['waited']} simulated min (threshold {measured['threshold']}); "
            f"notified {told}.")
    detail = {
        "level": level, "phase": phase, "kind": measured["kind"], "department": department,
        "priority": task.get("priority"), "threshold_minutes": measured["threshold"],
        "waited_minutes": measured["waited"], "clock": measured["clock"],
        "anchor_minute": measured["anchor"], "crossed_at_minute": crossed,
        "detected_at_minute": sim_minute, "escalated_to": lead, "lead_reachable": lead is not None,
        "notification_id": notification_id, "emergency": False,
    }
    if not await store.receipts.find_one({"receipt_id": receipt_id}, {"_id": 0}):
        await writers.receipt_writer(
            action_type=ESCALATION_ACTION, related_object_type="task",
            related_object_id=task["task_id"], source="simulator",
            resident_id=task.get("resident_id"), room=task.get("room"),
            assigned_role=(lead or {}).get("department") or department,
            assigned_user=(lead or {}).get("actor_id"), status="completed", result=text,
            receipt_id=receipt_id,
            provenance={
                **MONITOR.receipt_fields(), "simulation_scope": SIMULATION_SCOPE,
                "simulation_community_id": COMMUNITY_ID, "simulation_run_id": run_id,
                "authority": MONITOR_AUTHORITY, "parent_receipt_id": parent.get("receipt_id"),
                "correlation_id": parent.get("correlation_id") or parent.get("receipt_id"),
                "before_state": {"task_id": task["task_id"], "status": task.get("status"),
                                 "escalation_level": level - 1},
                "after_state": {"task_id": task["task_id"], "status": task.get("status"),
                                "escalation_level": level, "escalation": detail},
                "result_label": "simulated", "provider_refs": [],
                "next_state": "awaiting_simulated_lead" if lead else "no_lead_reachable",
            },
        )
    if not await store.notifications.find_one({"notification_id": notification_id}, {"_id": 0}):
        from models import Notification
        from routes.notification_delivery import _simulated
        from routes.notifications import simulation_of

        doc = Notification(
            notification_id=notification_id, channel="inapp", to=(lead or {}).get("actor_id") or "",
            subject=f"Simulated escalation level {level}", body=text, department=department,
            resident_id=task.get("resident_id"), related_object_type="task",
            related_object_id=task["task_id"], receipt_id=receipt_id,
            route=f"simulated_escalation_level_{level}",
        ).model_dump()
        _simulated(doc, simulation_of(task, receipt_id))
        doc.update(recipient_reachable=lead is not None, recipient_name=(lead or {}).get("name"),
                   escalation_level=level, created_at=now.isoformat())
        await writers.notification_saver(doc)
    from routes.task_history import task_event

    entry = task_event("escalated", by=MONITOR.actor_id, by_name=MONITOR.name, frm=level - 1,
                       to=level, to_name=(lead or {}).get("name") or NO_LEAD, text=text,
                       receipt_id=receipt_id)
    entry.update(sim_level=level, sim_phase=phase, sim_minute=sim_minute,
                 threshold_minutes=measured["threshold"], waited_minutes=measured["waited"])
    record = {"level": level, "at_minute": sim_minute, "at": now.isoformat(),
              "receipt_id": receipt_id, "notification_id": notification_id,
              "escalated_to": (lead or {}).get("actor_id"), "lead_reachable": lead is not None}
    await writers.task_updater(task["task_id"], {
        f"simulated_escalation.{phase}": record,
        "simulated_escalation_level": max(level, _int(task.get("simulated_escalation_level")) or 0),
        "simulated_escalated_at_minute": sim_minute,
    }, [entry])
    return {"task_id": task["task_id"], "phase": phase, "level": level, "receipt_id": receipt_id,
            "notification_id": notification_id, "notified": (lead or {}).get("actor_id"),
            "lead_reachable": lead is not None}


async def escalate_overdue(store, run_id: str, sim_minute: int, *, now: datetime,
                           table: Optional[dict] = None,
                           writers: Optional[EscalationWriters] = None) -> dict:
    """Escalate this run's open simulated tickets that reached a new level."""
    writers = writers or EscalationWriters()
    summary = {"run_id": run_id, "sim_minute": sim_minute, "checked": 0, "escalated": [],
               "unknown": [], "deferred": 0}
    if not run_id or _int(sim_minute) is None or not 0 <= sim_minute < HORIZON_MINUTES:
        return summary
    tasks = await store.staff_tasks.find({
        "simulation_run_id": run_id, "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID, "simulated": True,
        "status": {"$in": ["pending", "in_progress"]},
    }, {"_id": 0}).to_list(None)
    tasks = [t for t in tasks if t.get("status") == "pending"
             or (t.get("assigned_to") or "").startswith("sim:staff:")]  # real staff own the rest
    workflows = {t["task_id"]: (t.get("conversation_session_id") or "").removeprefix(SESSION_PREFIX)
                 for t in tasks}
    receipts = await _receipts(store, run_id, [
        f"{wf}:ticket_{phase}" for wf in workflows.values() if wf for phase in ("open", "claim")])
    for task in sorted(tasks, key=lambda t: t["task_id"]):
        summary["checked"] += 1
        cell = thresholds_for(task.get("category"), task.get("priority"), table)
        workflow = workflows[task["task_id"]]
        opened = receipts.get(f"{workflow}:ticket_open")
        minutes = phase_minutes(task, opened, receipts.get(f"{workflow}:ticket_claim"))
        measured = measure(task, minutes, sim_minute, cell) if cell else {"outcome": "unknown"}
        if measured["outcome"] == "unknown":
            summary["unknown"].append(task["task_id"])
        summary["deferred"] += measured["outcome"] == "deferred"
        if measured["outcome"] != "measured":
            continue
        parent = receipts.get(f"{workflow}:ticket_{'open' if measured['phase'] == PICKUP else 'claim'}")
        for level in range(_done_level(task, measured["phase"]) + 1, measured["level"] + 1):
            summary["escalated"].append(await _escalate_level(
                store, writers, run_id=run_id, task=task, parent=parent, measured=measured,
                level=level, sim_minute=sim_minute, now=now))
    return summary
