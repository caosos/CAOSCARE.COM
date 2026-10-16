"""Read-only restart planner for the living-community simulator.

The planner compares a persisted run cursor with a deterministic event stream
and durable event receipts.  It never executes an event, advances a cursor, or
writes storage.  A future executor may consume ``recovery_steps`` one at a time
under :mod:`simulation.community_run_lease` and must reconcile again after
each write.
"""
from collections import Counter, defaultdict
from dataclasses import asdict, is_dataclass
from typing import Iterable, Mapping

from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE


RUN_STATES = ("RUNNING", "PAUSED", "STOPPED")
TERMINAL_RECEIPT_STATUSES = ("completed", "failed", "cancelled")
MAX_RECOVERY_EVENTS = 100


class ReconciliationError(ValueError):
    """Input cannot identify one unambiguous living-community timeline."""


def _row(value, label: str) -> dict:
    if is_dataclass(value):
        value = asdict(value)
    if not isinstance(value, Mapping):
        raise ReconciliationError(f"{label} must be a mapping or dataclass")
    return dict(value)


def _required_text(row: dict, key: str, label: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReconciliationError(f"{label} {key} must be non-empty text")
    return value.strip()


def _validate_scope(row: dict, label: str, run_id: str | None = None) -> None:
    if row.get("simulation_scope") != SIMULATION_SCOPE:
        raise ReconciliationError(f"{label} has the wrong simulation scope")
    if row.get("simulation_community_id") != COMMUNITY_ID:
        raise ReconciliationError(f"{label} has the wrong simulation community")
    if run_id is not None and row.get("simulation_run_id", row.get("run_id")) != run_id:
        raise ReconciliationError(f"{label} belongs to a different run")


def _event_rows(events: Iterable) -> list[dict]:
    rows = []
    seen = set()
    prior_minute = None
    for index, value in enumerate(events):
        row = _row(value, f"event {index}")
        event_id = _required_text(row, "event_id", f"event {index}")
        if event_id in seen:
            raise ReconciliationError(f"duplicate planned event_id: {event_id}")
        seen.add(event_id)
        day, minute = row.get("day_index"), row.get("minute")
        if not isinstance(day, int) or isinstance(day, bool) or day < 0:
            raise ReconciliationError(f"event {event_id} has an invalid day_index")
        if not isinstance(minute, int) or isinstance(minute, bool) or not 0 <= minute < 1440:
            raise ReconciliationError(f"event {event_id} has an invalid minute")
        absolute_minute = day * 1440 + minute
        if prior_minute is not None and absolute_minute < prior_minute:
            raise ReconciliationError("planned events are not in deterministic order")
        prior_minute = absolute_minute
        row["event_id"] = event_id
        row["absolute_minute"] = absolute_minute
        rows.append(row)
    return rows


def _receipt_rows(receipts: Iterable, event_ids: set[str], run_id: str) -> dict[str, list[dict]]:
    by_event = defaultdict(list)
    receipt_ids = set()
    for index, value in enumerate(receipts):
        row = _row(value, f"receipt {index}")
        receipt_id = _required_text(row, "receipt_id", f"receipt {index}")
        if receipt_id in receipt_ids:
            raise ReconciliationError(f"duplicate receipt_id: {receipt_id}")
        receipt_ids.add(receipt_id)
        _validate_scope(row, f"receipt {receipt_id}", run_id)
        event_id = _required_text(row, "simulation_event_id", f"receipt {receipt_id}")
        if event_id not in event_ids:
            raise ReconciliationError(f"receipt {receipt_id} references an unknown event_id")
        row["receipt_id"] = receipt_id
        row["simulation_event_id"] = event_id
        by_event[event_id].append(row)
    return by_event


def _is_blocked(event: dict) -> bool:
    return bool(
        event.get("blocked") is True
        or event.get("execution_state") == "blocked"
        or event.get("adapter_status") == "blocked"
    )


def _base_classification(event: dict, run_state: str, sim_minute: int) -> tuple[str, str]:
    if run_state == "STOPPED" or event.get("terminal") is True:
        return "terminal", "The run or event is terminal; no recovery execution is permitted."
    if _is_blocked(event):
        return "blocked", "The event is explicitly blocked and cannot be recovered by execution."
    if event["absolute_minute"] <= sim_minute:
        return "due_catch_up", "The unreceipted event is due at the persisted simulated time."
    return "future", "The event is later than the persisted simulated time."


def reconcile_run(
    run,
    planned_events: Iterable,
    receipts: Iterable = (),
    *,
    max_recovery_events: int = 25,
) -> dict:
    """Build a bounded, non-mutating recovery plan for one persisted run."""
    run = _row(run, "run")
    run_id = _required_text(run, "run_id", "run")
    _validate_scope(run, "run")
    state = run.get("state")
    if state not in RUN_STATES:
        raise ReconciliationError("run state must be RUNNING, PAUSED, or STOPPED")
    cursor, sim_minute = run.get("cursor"), run.get("sim_minute")
    if not isinstance(cursor, int) or isinstance(cursor, bool) or cursor < 0:
        raise ReconciliationError("run cursor must be a non-negative integer")
    if not isinstance(sim_minute, int) or isinstance(sim_minute, bool) or sim_minute < 0:
        raise ReconciliationError("run sim_minute must be a non-negative integer")
    if not isinstance(max_recovery_events, int) or not 1 <= max_recovery_events <= MAX_RECOVERY_EVENTS:
        raise ReconciliationError(f"max_recovery_events must be between 1 and {MAX_RECOVERY_EVENTS}")

    events = _event_rows(planned_events)
    if cursor > len(events):
        raise ReconciliationError("run cursor is beyond the planned event stream")
    by_receipt = _receipt_rows(receipts, {row["event_id"] for row in events}, run_id)

    inconsistencies = []
    last_event_id = run.get("last_event_id")
    expected_last = events[cursor - 1]["event_id"] if cursor else None
    if last_event_id is not None and last_event_id != expected_last:
        inconsistencies.append("last_event_id does not match the persisted cursor")

    classified = []
    for index, event in enumerate(events):
        event_receipts = by_receipt.get(event["event_id"], [])
        terminal = [row for row in event_receipts if row.get("status") in TERMINAL_RECEIPT_STATUSES]
        nonterminal = [row for row in event_receipts if row.get("status") not in TERMINAL_RECEIPT_STATUSES]
        issue = None
        if len(event_receipts) > 1:
            issue = "multiple receipts ambiguously reference this event"
        elif nonterminal:
            issue = "the event has a receipt without a terminal result"
        elif terminal and event["absolute_minute"] > sim_minute:
            issue = "the event has a terminal receipt later than persisted simulated time"
        elif index < cursor and not terminal:
            issue = "the cursor passed this event without a terminal receipt"
        if issue:
            classification, reason = "inconsistent", issue
            inconsistencies.append(f"{event['event_id']}: {issue}")
        elif terminal:
            classification = "already_receipted"
            reason = "A single terminal receipt proves an attempt/result; do not replay execution."
        else:
            classification, reason = _base_classification(event, state, sim_minute)
        classified.append({
            "cursor_index": index,
            "event_id": event["event_id"],
            "absolute_minute": event["absolute_minute"],
            "classification": classification,
            "receipt_id": terminal[0]["receipt_id"] if len(terminal) == 1 else None,
            "receipt_status": terminal[0]["status"] if len(terminal) == 1 else None,
            "reason": reason,
            "represents_execution": False,
        })

    # A receipt beyond the cursor is valid crash recovery only when every
    # preceding event from the cursor through it is also receipted.  Otherwise
    # the persisted timeline contains a gap and the planner refuses all work.
    seen_gap = False
    for row in classified[cursor:]:
        if row["classification"] != "already_receipted":
            seen_gap = True
        elif seen_gap:
            message = f"{row['event_id']}: receipt exists after an unresolved cursor gap"
            row.update(classification="inconsistent", reason=message)
            inconsistencies.append(message)

    steps = []
    recoverable_count = 0
    if state == "RUNNING" and not inconsistencies:
        for row in classified[cursor:]:
            if row["classification"] == "already_receipted":
                action = "advance_cursor_from_receipt"
            elif row["classification"] == "due_catch_up":
                action = "execute_event_then_advance"
            else:
                break
            recoverable_count += 1
            if len(steps) < max_recovery_events:
                steps.append({
                    "action": action,
                    "event_id": row["event_id"],
                    "expected_cursor": row["cursor_index"],
                    "next_cursor": row["cursor_index"] + 1,
                    "receipt_id": row["receipt_id"],
                    "represents_execution": False,
                })

    counts = Counter(row["classification"] for row in classified)
    status = "inconsistent" if inconsistencies else (
        "terminal" if state == "STOPPED" or cursor == len(events) else
        "paused" if state == "PAUSED" else "ready"
    )
    return {
        "schema_version": 1,
        "run_id": run_id,
        "run_state": state,
        "cursor": cursor,
        "sim_minute": sim_minute,
        "status": status,
        "read_only": True,
        "represents_execution": False,
        "execution_allowed_now": bool(steps),
        "event_count": len(events),
        "classification_counts": dict(sorted(counts.items())),
        "classified_events": classified,
        "recovery_steps": steps,
        "recovery_limit": max_recovery_events,
        "has_more_recovery": recoverable_count > len(steps),
        "inconsistencies": inconsistencies,
    }
