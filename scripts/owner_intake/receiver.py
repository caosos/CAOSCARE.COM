#!/usr/bin/env python3
"""Receiving side of owner instruction intake (RQ-042). See docs/OWNER_INTAKE.md.

Desktop-Agent polls GitHub and delivers items (ids like da-<hex>). This script only
records that CAOSCare received an item and posts the acknowledgement comment.
Standard library + the authenticated `gh` CLI. No polling, no model calls.

  receiver.py received <item_id> --issue N [--note T]
  receiver.py status <item_id> ACK|WORKING|BLOCKED|DONE --issue N [--note T] [--post]
  receiver.py list [--open]
"""
import argparse, json, os, socket, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

MARKER = "<!-- caos:coordinator -->"
STATUSES = ("ACK", "WORKING", "BLOCKED", "DONE")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ledger_path():
    d = Path(os.environ.get("CAOS_INTAKE_DIR") or Path.home() / ".local/state/caoscare-intake")
    d.mkdir(parents=True, exist_ok=True)
    return d / "ledger.jsonl"


def read():
    p = ledger_path()
    out = []
    if p.exists():
        for line in p.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def append(entry):
    entry.update(time=now(), host=socket.gethostname())
    with open(ledger_path(), "a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def repo():
    return os.environ.get("CAOS_INTAKE_REPO", "caosos/CAOSCARE.COM")


def post(issue, body):
    r = subprocess.run([os.environ.get("CAOS_INTAKE_GH", "gh"), "api", "-X", "POST",
                        f"repos/{repo()}/issues/{issue}/comments", "-f", f"body={body}"],
                       capture_output=True, text=True, timeout=60)
    if r.returncode:
        print((r.stderr or r.stdout).strip()[:300], file=sys.stderr)
        return False
    return True


def latest(item_id):
    st = None
    for e in read():
        if e["item_id"] == item_id and e["kind"] in ("received", "status"):
            st = e
    return st


def cmd_received(a):
    if any(e["item_id"] == a.item_id for e in read()):
        print(f"{a.item_id} already recorded")
        return 0
    append(dict(kind="received", item_id=a.item_id, issue=a.issue, status="RECEIVED", note=a.note))
    print(f"{a.item_id} received")
    return 0


def cmd_status(a):
    posted = {(e["item_id"], e["status"]) for e in read() if e.get("posted")}
    already = (a.item_id, a.status) in {(e["item_id"], e["status"]) for e in read() if e["kind"] == "status"}
    do_post = a.post and (a.item_id, a.status) not in posted
    if already and not do_post:
        print(f"{a.item_id} already {a.status}; nothing to do")
        return 0
    ok = True
    if do_post:
        body = f"{MARKER}\n{a.status} {a.item_id}" + (f" {a.note}" if a.note else "")
        ok = post(a.issue, body)
    if ok:
        if not already:
            append(dict(kind="status", item_id=a.item_id, issue=a.issue, status=a.status,
                        note=a.note, posted=do_post))
        elif do_post:
            append(dict(kind="post", item_id=a.item_id, issue=a.issue, status=a.status, posted=True))
    print(f"{a.item_id} -> {a.status} (posted: {do_post and ok})")
    return 0 if ok else 1


def cmd_list(a):
    items = {}
    for e in read():
        if e["kind"] in ("received", "status"):
            items[e["item_id"]] = e
    for iid, e in items.items():
        if a.open and e["status"] == "DONE":
            continue
        print(f"{iid}\t#{e['issue']}\t{e['status']}\t{e['time']}\t{e.get('note') or ''}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("received")
    r.add_argument("item_id"); r.add_argument("--issue", type=int, required=True); r.add_argument("--note", default="")
    s = sub.add_parser("status")
    s.add_argument("item_id"); s.add_argument("status", choices=STATUSES)
    s.add_argument("--issue", type=int, required=True); s.add_argument("--note", default="")
    s.add_argument("--post", action="store_true")
    l = sub.add_parser("list")
    l.add_argument("--open", action="store_true")
    a = ap.parse_args(argv)
    return {"received": cmd_received, "status": cmd_status, "list": cmd_list}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
