#!/usr/bin/env python3
"""Dispatch side of the coordination watch.

The prepared next bounded items live in docs/status/COORDINATION_QUEUE.json - a mirror
of issue #166's order with the task text written out, never a competing queue (#166
stays authoritative; an item is dispatchable only while #166 says it is next).

Delivery uses the intake Main Claude already consumes: a comment on the authoritative
issue by the owner login without the Main-Claude marker. Main Claude's own GitHub watch
exits on that comment and re-invokes the session with its text. Nothing is spawned,
no second worker is created, no model is called by the watcher.
"""
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QUEUE_FILE = Path(os.environ.get("CAOS_COORD_QUEUE", REPO_ROOT / "docs/status/COORDINATION_QUEUE.json"))


def load_queue() -> dict:
    return json.loads(QUEUE_FILE.read_text())


def next_ready(queue: dict, dispatched_ids: set, kind=None):
    """First READY item in file order not yet dispatched. kind='coordination_test' selects only
    test items; kind=None selects only real items (tests never count as the next task)."""
    for item in queue.get("items", []):
        if item.get("id") in dispatched_ids or item.get("status") != "READY":
            continue
        if kind and item.get("kind") != kind:
            continue
        if not kind and item.get("kind") == "coordination_test":
            continue
        return item
    return None


def gate_open(queue: dict, boundary_seen: bool, host: dict) -> tuple:
    """Real dispatch only when: the queue's gate is enabled, the required boundary receipt has been
    observed (or none is required), and the coordinator is live and not busy. Returns (ok, why)."""
    gate = queue.get("dispatch_gate") or {}
    if not gate.get("enabled"):
        return False, f"dispatch gate disabled: {gate.get('reason', 'no reason recorded')}"
    if gate.get("require_boundary") and not boundary_seen:
        return False, "waiting for the coordinator's boundary receipt (" + str(gate.get("require_boundary")) + ")"
    if host.get("verdict") == "LIVE_BUSY":
        return False, "coordinator is busy; holding the prepared item until its boundary"
    if host.get("verdict") not in ("LIVE_IDLE",):
        return False, f"coordinator host verdict {host.get('verdict')}; not dispatching"
    return True, "gate open"


def delivery_text(item: dict, authoritative_issue: int, coordinator_name: str) -> str:
    return (f"COORDINATION DELIVERY {item['id']} (kind: {item.get('kind', 'task')}) for the existing coordinator "
            f"`{coordinator_name}` - from the local coordination watch (systemd user service `caoscare-coordination`; "
            f"queue mirror `docs/status/COORDINATION_QUEUE.json`; authority: this issue #{authoritative_issue}).\n\n"
            f"{item['text']}\n\n"
            f"Acknowledge here with one comment containing `ACK {item['id']}` (carry your usual marker), then "
            f"`WORKING {item['id']}`, `BLOCKED {item['id']}` or `DONE {item['id']}` as you go. Delivered automatically; "
            f"Michael did not relay this.")
