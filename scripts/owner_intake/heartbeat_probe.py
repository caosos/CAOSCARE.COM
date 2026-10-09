#!/usr/bin/env python3
"""No-LLM heartbeat probe (RQ-044). Prints one JSON line {"verdict": "WAKE"|"IDLE", "reasons": [...]}.

Run by the Desktop-Agent bridge (the single central monitor) on its own schedule; it never
polls GitHub, never calls a model, never posts. WAKE only when the coordinator has something
safe to read:
  - docs/status/COORDINATOR_STATUS.json lists ready_unblocked work or open questions,
  - a worker listed there made no progress for STALL_MINUTES (worktree untouched),
  - an intake item was received but not ACKed for ACK_MINUTES (receiver ledger).
Otherwise IDLE: stay quiet, spend nothing.
Env: CAOS_STATUS_FILE, CAOS_INTAKE_DIR, CAOS_STALL_MINUTES (45), CAOS_ACK_MINUTES (30).
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STATUS_FILE = Path(os.environ.get("CAOS_STATUS_FILE", REPO / "docs/status/COORDINATOR_STATUS.json"))
INTAKE_DIR = Path(os.environ.get("CAOS_INTAKE_DIR", Path.home() / ".local/state/caoscare-intake"))
STALL = float(os.environ.get("CAOS_STALL_MINUTES", "45"))
ACKWAIT = float(os.environ.get("CAOS_ACK_MINUTES", "30"))


def _parse(ts):
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


def _latest_change(path: Path) -> float:
    """Newest of: last commit time, any tracked-file change time under the worktree (no content read)."""
    newest = 0.0
    try:
        out = subprocess.run(["git", "-C", str(path), "log", "-1", "--format=%ct"], capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            newest = float(out.stdout.strip())
        st = subprocess.run(["git", "-C", str(path), "status", "--porcelain"], capture_output=True, text=True, timeout=10)
        for line in st.stdout.splitlines():
            f = path / line[3:].strip().strip('"')
            if f.exists():
                newest = max(newest, f.stat().st_mtime)
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return newest


def probe(now=None) -> dict:
    now = now or time.time()
    reasons = []
    try:
        st = json.loads(STATUS_FILE.read_text())
    except (OSError, ValueError) as e:
        return {"verdict": "WAKE", "reasons": [f"status file unreadable: {e}"]}
    if st.get("ready_unblocked"):
        reasons.append(f"{len(st['ready_unblocked'])} ready unblocked item(s)")
    if st.get("questions"):
        reasons.append(f"{len(st['questions'])} open question(s)")
    for w in st.get("workers", []):
        wt = w.get("worktree")
        if not wt:
            continue
        last = _latest_change(Path(os.path.expanduser(wt)))
        if last and (now - last) / 60 > STALL:
            reasons.append(f"worker {w.get('name', wt)} idle {int((now - last) / 60)} min")
    ledger = INTAKE_DIR / "ledger.jsonl"
    if ledger.exists():
        latest = {}
        for line in ledger.read_text().splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            latest.setdefault(r.get("item_id"), []).append(r)
        for item, rows in latest.items():
            statuses = {r.get("status") for r in rows}
            if statuses & {"ACK", "WORKING", "BLOCKED", "DONE"}:
                continue
            t = _parse(rows[0].get("time") or rows[0].get("received_at") or rows[0].get("at"))
            if t and (now - t.timestamp()) / 60 > ACKWAIT:
                reasons.append(f"intake item {item} received but not ACKed for {int((now - t.timestamp()) / 60)} min")
    return {"verdict": "WAKE" if reasons else "IDLE", "reasons": reasons}


if __name__ == "__main__":
    print(json.dumps(probe()))
    sys.exit(0)
