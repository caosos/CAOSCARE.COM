#!/usr/bin/env python3
"""Local host evidence for the coordination watch (owner-authorized 2026-10-16).

Reads Claude Code's own session registry (~/.claude/sessions/<pid>.json), checks /proc/<pid>,
and uses the registry's status stamp as last activity. Starts nothing. GitHub silence is never
host evidence.

Verdicts: LIVE_BUSY / LIVE_IDLE / STALE / STOPPED (pid proof only) / UNVERIFIED.
"""
import json
import os
import time
from pathlib import Path

SESSIONS = Path(os.environ.get("CLAUDE_SESSIONS_DIR", Path.home() / ".claude/sessions"))


def _records():
    out = []
    try:
        for p in sorted(SESSIONS.glob("*.json")):
            try:
                out.append(json.loads(p.read_text()))
            except (ValueError, OSError):
                continue
    except OSError:
        return None
    return out


def _alive(pid) -> bool:
    try:
        return Path(f"/proc/{int(pid)}").exists()
    except (ValueError, TypeError):
        return False


def coordinator_state(pin: dict, stall_minutes: float = 45.0) -> dict:
    recs = _records()
    if recs is None:
        return {"verdict": "UNVERIFIED", "evidence": ["session registry unreadable"], "live": False}
    match = [r for r in recs if r.get("name") == pin.get("session_name")] or \
            [r for r in recs if r.get("sessionId") == pin.get("session_id")]
    if not match:
        alive_others = [r.get("name") for r in recs if _alive(r.get("pid"))]
        return {"verdict": "UNVERIFIED", "live": False,
                "evidence": [f"no registry record for {pin.get('session_name')} / {pin.get('session_id')}; "
                             f"live sessions: {alive_others}"]}
    r = match[0]
    pid = r.get("pid")
    if pin.get("session_id") and r.get("sessionId") != pin.get("session_id") or pin.get("session_name") and r.get("name") != pin.get("session_name"):
        # stale pin: the name now belongs to another session (or the id to another name) - never deliver on a guess
        return {"verdict": "PIN_MISMATCH", "live": False, "pid": pid, "name": r.get("name"), "session_id": r.get("sessionId"),
                "evidence": [f"pin {pin.get('session_name')}/{pin.get('session_id')} but registry has {r.get('name')}/{r.get('sessionId')} (pid {pid})"]}
    ev = [f"registry {SESSIONS / (str(pid) + '.json')}",
          f"name {r.get('name')} session {r.get('sessionId')} cwd {r.get('cwd')}"]
    if not _alive(pid):
        return {"verdict": "STOPPED", "live": False, "pid": pid, "name": r.get("name"),
                "evidence": ev + [f"pid {pid} is not running (/proc/{pid} absent)"]}
    stamp_ms = r.get("statusUpdatedAt") or r.get("updatedAt") or 0
    age = time.time() - stamp_ms / 1000.0 if stamp_ms else None
    busy = (r.get("status") == "busy")
    verdict = "LIVE_BUSY" if busy else "LIVE_IDLE"
    if age is not None and age > stall_minutes * 60:
        verdict = "STALE"
    if age is not None:
        ev.append(f"pid {pid} alive; registry status {r.get('status')}; status stamp {int(age)} s old")
    else:
        ev.append(f"pid {pid} alive; registry status {r.get('status')}; no status stamp")
    return {"verdict": verdict, "live": True, "busy": busy, "pid": pid, "name": r.get("name"),
            "session_id": r.get("sessionId"), "cwd": r.get("cwd"), "activity_age_sec": age, "evidence": ev}


def known_sessions() -> set:
    """Every session name Claude Code's registry has recorded on this host (live or not): provenance for unmarked receipts."""
    return {r.get("name") for r in (_records() or []) if r.get("name")}


def duplicate_guard(pin: dict) -> dict:
    recs = _records() or []
    same = [r.get("name") for r in recs
            if _alive(r.get("pid")) and r.get("kind") == "interactive"
            and str(r.get("cwd", "")).startswith(pin.get("cwd_prefix", "/nonexistent"))]
    return {"interactive_sessions_in_cwd": same, "pinned": pin.get("session_name")}
