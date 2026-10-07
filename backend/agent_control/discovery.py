"""Read-only discovery of the Claude Code sessions running on this host
(docs/CAOSCARE_AGENT_CONTROL_PLANE.md §16).

Sources, read only:
  ~/.claude/sessions/<pid>.json   Claude Code's own local session registry.
                                  Only ALLOWED_FIELDS are read out of it.
  /proc/<pid>                      liveness, parent process, terminal, start time.
  git -C <cwd>                     current branch, only if cwd is a git checkout.

Never read: the *.key files, the messaging socket, transcripts. Nothing here
writes, signals or attaches to a process. It does NOT decide which agent a
session is - identity binding stays a human decision (registry stays
OFFLINE/UNKNOWN until Michael confirms).
"""
import json
import os
import subprocess
from pathlib import Path
from typing import Optional

ALLOWED_FIELDS = ("pid", "sessionId", "name", "status", "kind", "cwd", "version",
                  "startedAt", "updatedAt", "statusUpdatedAt", "procStart", "entrypoint")


def sessions_dir() -> Path:
    return Path(os.environ.get("CAOSCARE_CLAUDE_SESSIONS_DIR",
                               str(Path.home() / ".claude" / "sessions")))


def _read(path: str) -> Optional[str]:
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return None


def _proc(pid: int, proc_root: str) -> dict:
    """Facts from /proc. procStart in the registry is /proc/<pid>/stat field
    22 (start time); comparing them guards against a reused pid."""
    stat = _read(f"{proc_root}/{pid}/stat")
    if not stat:
        return {"alive": False}
    rest = stat.rsplit(")", 1)[-1].split()
    ppid, start = rest[1], rest[19]
    try:
        tty = os.readlink(f"{proc_root}/{pid}/fd/0")
    except OSError:
        tty = None
    return {"alive": True, "ppid": int(ppid), "start_time": start, "tty": tty,
            "parent_comm": (_read(f"{proc_root}/{ppid}/comm") or "").strip() or None}


def _git_branch(cwd: Optional[str]) -> Optional[str]:
    if not cwd or not Path(cwd, ".git").exists():
        return None
    try:
        out = subprocess.run(["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
                             capture_output=True, text=True, timeout=3, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def discover(proc_root: str = "/proc") -> list:
    sessions = []
    base = sessions_dir()
    if not base.is_dir():
        return sessions
    for f in sorted(base.glob("*.json")):          # *.key files never match
        try:
            raw = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        s = {k: raw.get(k) for k in ALLOWED_FIELDS}
        if not isinstance(s.get("pid"), int):
            continue
        p = _proc(s["pid"], proc_root)
        s.update(p)
        s["pid_matches_registry"] = (p.get("alive") and s.get("procStart") is not None
                                     and str(s["procStart"]) == p.get("start_time"))
        # Branch of the directory the session was started in - not proof of
        # the worktree it is working in now (most sessions start in ~).
        s["cwd_branch"] = _git_branch(s.get("cwd"))
        sessions.append(s)
    # A session id resumed by two live processes cannot identify one of them.
    counts: dict = {}
    for s in sessions:
        if s.get("alive"):
            counts[s.get("sessionId")] = counts.get(s.get("sessionId"), 0) + 1
    for s in sessions:
        s["session_id_shared"] = counts.get(s.get("sessionId"), 0) > 1
        s["stable_key"] = f"{s['pid']}:{s.get('procStart')}" if s["pid_matches_registry"] else None
    return sessions
