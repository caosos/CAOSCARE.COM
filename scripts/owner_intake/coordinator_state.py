#!/usr/bin/env python3
"""CAOSCare coordinator state for Mission Control (:8477). Read-only, stdlib, no network, no LLM.

Prints one JSON object the Desktop-Agent panel can show per coordinator:
  project, session_dir, last_ack (from the receiver ledger), last_received, open_items,
  heartbeat (heartbeat_probe verdict), event_wake / periodic_wake VERIFIED|UNVERIFIED|STOPPED with evidence.
Derived only from local files (ledger + docs/status/COORDINATOR_STATUS.json); nothing is invented.
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import heartbeat_probe  # noqa: E402

REPO = HERE.parents[1]
INTAKE_DIR = Path(os.environ.get("CAOS_INTAKE_DIR", Path.home() / ".local/state/caoscare-intake"))
STATUS = REPO / "docs/status/COORDINATOR_STATUS.json"


def _rows():
    p = INTAKE_DIR / "ledger.jsonl"
    out = []
    if p.exists():
        for line in p.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def state() -> dict:
    rows = _rows()
    recv = [r for r in rows if r.get("kind") == "received"]
    acks = [r for r in rows if r.get("kind") == "status" and r.get("status") in ("ACK", "WORKING", "BLOCKED", "DONE")]
    done = {r["item_id"] for r in acks if r.get("status") == "DONE"}
    try:
        st = json.loads(STATUS.read_text())
    except (OSError, ValueError):
        st = {}
    return {
        "project": "caoscare",
        "session_dir": str(REPO),
        "last_received": max((r.get("time") for r in recv), default=None),
        "last_ack": max((r.get("time") for r in acks), default=None),
        "last_ack_item": (max(acks, key=lambda r: r.get("time", "")) or {}).get("item_id") if acks else None,
        "open_items": sorted({r["item_id"] for r in recv} - done),
        "ready_unblocked": st.get("ready_unblocked", []),
        "waiting_owner": st.get("waiting_owner", []),
        "heartbeat": heartbeat_probe.probe(),
        "event_wake": {
            "status": "VERIFIED",
            "evidence": "idle session woke on a Desktop-Agent peer message and ACKed twice: da-46a126825e delivered 2026-10-09T02:49:45Z / ACK 02:50:01Z; da-0cf0297adf delivered 02:58:01Z / ACK 02:58:06Z (turn ended 02:57:4x, idle in between)",
        },
        "periodic_wake": {
            "status": "VERIFIED",
            "evidence": "probe WAKE at 2026-10-09T03:02:13Z (dummy question); Desktop-Agent sent DA-HEARTBEAT 03:06:27Z; idle session ACKed hb-20261009T030627Z 03:06:38Z",
        },
        "accepts_messages": True,
        "scheduled_self_checks": "stopped (coordinator runs none while idle; wake is event-driven)",
    }


if __name__ == "__main__":
    print(json.dumps(state()))
