#!/usr/bin/env python3
"""Local wake path between the coordination watch and the EXISTING coordinator session (no model, no network, starts nothing).

The coordinator session arms ONE listener as its own background command:
    python3 scripts/owner_intake/intake_inbox.py listen --session caoscare-1-4e
The listener records itself (pid + the Claude Code session pid it runs under), waits for an inbox entry addressed to that
session, prints it and exits - the exit is what re-invokes the session. The watcher only appends entries (deliver) and checks
that the armed listener really belongs to the pinned session (armed). Re-arm after every wake.

  intake_inbox.py listen --session NAME [--poll 2]
  intake_inbox.py armed --session NAME --session-pid PID
  intake_inbox.py deliver --session NAME --command cID --task T --url U --reason backfill   (the watcher's own append; for
      a command the pre-2026-10-16 watcher wrongly marked answered - same idempotency, never twice per command+reason)
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DIR = Path(os.environ.get("CAOS_COORD_STATE", Path.home() / ".local/state/caoscare-coordination"))
INBOX, LISTENER = DIR / "inbox.jsonl", DIR / "listener.json"


def _iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def entries() -> list:
    out = []
    if INBOX.exists():
        for line in INBOX.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def deliver(session: str, command: str, task: str, text: str, reason: str) -> dict:
    """Append one entry. The same (command, reason) is never appended twice - a replay is a no-op."""
    if any(e.get("command") == command and e.get("reason") == reason for e in entries()):
        return {"ok": True, "duplicate": True}
    e = {"seq": len(entries()) + 1, "at": _iso(), "session": session, "command": command, "task": task, "reason": reason, "text": text}
    DIR.mkdir(parents=True, exist_ok=True)
    with INBOX.open("a") as f:
        f.write(json.dumps(e) + "\n")
    return {"ok": True, "seq": e["seq"]}


def _ancestors(pid: int) -> list:
    chain = []
    while pid > 1 and len(chain) < 20:
        chain.append(pid)
        try:
            pid = int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return chain


def armed(session: str, session_pid) -> dict:
    """True only if a listener for `session` is running AND its process ancestry contains the session's own pid."""
    try:
        li = json.loads(LISTENER.read_text())
    except (OSError, ValueError):
        return {"armed": False, "why": "no listener record"}
    if li.get("session") != session:
        return {"armed": False, "why": f"listener is for {li.get('session')}"}
    if not Path(f"/proc/{li.get('pid')}").exists():
        return {"armed": False, "why": f"listener pid {li.get('pid')} not running"}
    if session_pid is None or int(session_pid) not in _ancestors(int(li["pid"])):
        return {"armed": False, "why": f"listener pid {li.get('pid')} does not run under session pid {session_pid}"}
    return {"armed": True, "pid": li["pid"], "since": li.get("armed_at"), "consumed_seq": li.get("consumed_seq", 0)}


def listen(session: str, poll: float) -> int:
    DIR.mkdir(parents=True, exist_ok=True)
    try:
        last = json.loads(LISTENER.read_text()).get("consumed_seq", 0)
    except (OSError, ValueError):
        last = 0
    LISTENER.write_text(json.dumps({"session": session, "pid": os.getpid(), "armed_at": _iso(), "consumed_seq": last}))
    while True:
        new = [e for e in entries() if e.get("session") == session and e.get("seq", 0) > last]
        if new:
            LISTENER.write_text(json.dumps({"session": session, "pid": None, "armed_at": None, "consumed_seq": new[-1]["seq"],
                                            "woke_at": _iso()}))
            for e in new:
                print(json.dumps(e))
            return 0
        time.sleep(poll)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("listen"); l.add_argument("--session", required=True); l.add_argument("--poll", type=float, default=2.0)
    a_ = sub.add_parser("armed"); a_.add_argument("--session", required=True); a_.add_argument("--session-pid", type=int)
    d = sub.add_parser("deliver")
    for f in ("--session", "--command", "--task", "--url", "--reason"):
        d.add_argument(f, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "deliver":
        text = (f"CAOSCARE INTAKE {a.reason.upper()} — owner command {a.command} ({a.url}), task {a.task}. Step 1: `python3 "
                f"{Path(__file__).resolve().parent}/receiver.py pickup {a.command} --task {a.task} --session {a.session}`; act ONLY on NEW.")
        print(json.dumps(deliver(a.session, a.command, a.task, text, a.reason)))
        return 0
    if a.cmd == "listen":
        return listen(a.session, a.poll)
    print(json.dumps(armed(a.session, a.session_pid)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
