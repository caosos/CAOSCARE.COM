#!/usr/bin/env python3
"""Owner instruction intake (RQ-042). See docs/OWNER_INTAKE.md.

Polls watched GitHub issues with the authenticated `gh` CLI and keeps a durable,
idempotent local inbox. No model calls, no new secrets. Standard library only.

  poll.py                     one poll (what the timer runs)
  poll.py --replay            list owner items not yet DONE
  poll.py show <item_id>      print one item
  poll.py status <item_id> ACK|WORKING|BLOCKED|DONE [--note T] [--post]
"""
import argparse, fcntl, hashlib, json, os, socket, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1"
MARKER = "<!-- caos:coordinator -->"
STATUSES = ("ACK", "WORKING", "BLOCKED", "DONE")
HERE = Path(__file__).resolve().parent


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def intake_dir():
    d = Path(os.environ.get("CAOS_INTAKE_DIR") or Path.home() / ".local/state/caoscare-intake")
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_config():
    cfg = json.loads((HERE / "config.json").read_text())
    extra = os.environ.get("CAOS_INTAKE_CONFIG")
    if extra:
        cfg.update(json.loads(Path(extra).read_text()))
    return cfg


def log(msg):
    line = f"{now()} {msg}"
    print(line, file=sys.stderr)
    with open(intake_dir() / "intake.log", "a") as f:
        f.write(line + "\n")


def read_jsonl(path):
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def append_jsonl(path, obj):
    with open(path, "a") as f:
        f.write(json.dumps(obj, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def receipt(d, kind, item_id, result, **extra):
    append_jsonl(d / "receipts.jsonl", {
        "time": now(), "kind": kind, "item_id": item_id, "result": result,
        "poller_version": VERSION, "host": socket.gethostname(), **extra})


def load_cursor(d):
    p = d / "cursor.json"
    return json.loads(p.read_text()) if p.exists() else {"issues": {}}


def save_cursor(d, cur):
    tmp = d / "cursor.json.tmp"
    tmp.write_text(json.dumps(cur, indent=1, sort_keys=True))
    os.replace(tmp, d / "cursor.json")


class GhError(Exception):
    pass


def gh(args, calls):
    """One gh invocation. Counts against the per-run call budget."""
    calls[0] += 1
    try:
        r = subprocess.run([os.environ.get("CAOS_INTAKE_GH", "gh")] + args,
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise GhError(str(e))
    if r.returncode != 0:
        raise GhError((r.stderr or r.stdout).strip()[:300] or f"exit {r.returncode}")
    try:
        return json.loads(r.stdout) if r.stdout.strip() else None
    except ValueError as e:
        raise GhError(f"bad json: {e}")


def make_item(cfg, issue, kind, obj):
    body = obj.get("body") or ""
    first = body.lstrip().splitlines()[0] if body.strip() else ""
    repo = cfg["repo"]
    if MARKER in first:
        source, status = "coordinator", "n/a"
    elif obj.get("author_association") in cfg["trusted_associations"]:
        source, status = "owner", "NEW"
    else:
        source, status = "untrusted", "n/a"
    iid = f"gh:{repo}#{issue}:" + ("body" if kind == "body" else f"comment:{obj['id']}")
    return {"item_id": iid, "issue": issue, "kind": kind, "source": source,
            "author": (obj.get("user") or {}).get("login"),
            "association": obj.get("author_association"),
            "created_at": obj.get("created_at"), "url": obj.get("html_url"),
            "sha256": hashlib.sha256(body.encode()).hexdigest(), "body": body,
            "first_seen": now(), "status": status}


def nudge(item_id):
    target = os.environ.get("CAOS_INTAKE_NUDGE_TMUX")
    if not target:
        return None
    try:
        if subprocess.run(["tmux", "list-panes", "-t", target], capture_output=True).returncode:
            return "pane_not_found"
        cmd = f"NEW OWNER INSTRUCTION {item_id} - run: python3 scripts/owner_intake/poll.py show {item_id}"
        subprocess.run(["tmux", "send-keys", "-t", target, cmd, "Enter"], check=True, capture_output=True)
        return "sent"
    except (OSError, subprocess.CalledProcessError):
        return "failed"


def post_comment(cfg, issue, text, d, cur):
    last = cur.get("last_post_at", 0)
    if time.time() - last < cfg["min_post_interval_seconds"]:
        return "rate_limited"
    try:
        gh(["api", "-X", "POST", f"repos/{cfg['repo']}/issues/{issue}/comments",
            "-f", f"body={MARKER}\n{text}"], [0])
    except GhError as e:
        log(f"post failed: {e}")
        return "failed"
    cur["last_post_at"] = time.time()
    save_cursor(d, cur)
    return "posted"


def current_status(d, item_id):
    st = None
    for r in read_jsonl(d / "receipts.jsonl"):
        if r.get("kind") == "status" and r["item_id"] == item_id:
            st = r
    return st


def poll(args):
    d, cfg = intake_dir(), load_config()
    cur = load_cursor(d)
    bo = cur.get("backoff", {})
    if bo.get("until", 0) > time.time():
        log(f"backing off until {datetime.fromtimestamp(bo['until'], timezone.utc).isoformat()}")
        return 0
    seen = {i["item_id"] for i in read_jsonl(d / "inbox.jsonl")}
    calls, new = [0], []
    budget = cfg["max_items_per_run"]
    repo = cfg["repo"]
    try:
        issues = list(cfg["issues"])
        if cfg.get("label"):
            for it in gh(["api", f"repos/{repo}/issues?state=open&labels={cfg['label']}&per_page=30"], calls) or []:
                if "pull_request" not in it and it["number"] not in issues:
                    issues.append(it["number"])
        for n in issues:
            if calls[0] >= cfg["max_gh_calls_per_run"] or budget <= 0:
                break
            ic = cur["issues"].setdefault(str(n), {})
            batch = []
            if not ic.get("body_seen"):
                body = gh(["api", f"repos/{repo}/issues/{n}"], calls)
                batch.append(("body", body))
            q = f"repos/{repo}/issues/{n}/comments?per_page=100"
            if ic.get("last_created_at"):
                q += "&since=" + ic["last_created_at"]
            for c in gh(["api", q], calls) or []:
                batch.append(("comment", c))
            for kind, obj in batch:
                if budget <= 0:
                    break
                item = make_item(cfg, n, kind, obj)
                if item["item_id"] not in seen:
                    append_jsonl(d / "inbox.jsonl", item)
                    receipt(d, "ingested", item["item_id"], "ok", source=item["source"],
                            sha256=item["sha256"])
                    seen.add(item["item_id"])
                    new.append(item)
                    budget -= 1
                # cursor moves only past items that are durably stored
                if kind == "body":
                    ic["body_seen"] = True
                else:
                    ic["last_comment_id"] = obj["id"]
                    ic["last_created_at"] = obj["created_at"]
                save_cursor(d, cur)
    except GhError as e:
        fails = bo.get("failures", 0) + 1
        wait = min(300 * 2 ** (fails - 1), 3600)
        cur["backoff"] = {"failures": fails, "until": time.time() + wait}
        save_cursor(d, cur)
        receipt(d, "poll_error", "-", "gh_failed", error=str(e), retry_in_seconds=wait)
        log(f"gh failed ({e}); backoff {wait}s")
        return 1
    if cur.pop("backoff", None):
        save_cursor(d, cur)
    owner_items = [i for i in new if i["source"] == "owner"]
    for it in owner_items:
        r = nudge(it["item_id"])
        if r:
            receipt(d, "nudge", it["item_id"], r)
    if args.auto_ack and owner_items:
        ids = ", ".join(i["item_id"] for i in owner_items[:5])
        res = post_comment(cfg, owner_items[0]["issue"],
                           f"ACK: received by intake at {now()}, items {ids}", d, cur)
        for it in owner_items:
            receipt(d, "status", it["item_id"], "ok", status="ACK", note="auto-ack", post_result=res)
    log(f"poll ok: {len(new)} new ({len(owner_items)} owner), {calls[0]} gh calls")
    return 0


def find_item(d, item_id):
    for i in read_jsonl(d / "inbox.jsonl"):
        if i["item_id"] == item_id:
            return i
    return None


def cmd_status(args):
    d, cfg = intake_dir(), load_config()
    item = find_item(d, args.item_id)
    if not item:
        print("unknown item", file=sys.stderr)
        return 2
    if item["source"] != "owner":
        print("only owner items have a status", file=sys.stderr)
        return 2
    prev = current_status(d, args.item_id)
    posted_ok = prev and prev.get("post_result") == "posted"
    if prev and prev["status"] == args.status and (posted_ok or not args.post):
        print(f"{args.item_id} already {args.status}; nothing to do")
        return 0
    res = "not_requested"
    if args.post:
        cur = load_cursor(d)
        text = f"{args.status}: {args.item_id}" + (f" - {args.note}" if args.note else "")
        res = post_comment(cfg, item["issue"], text, d, cur)
    receipt(d, "status", args.item_id, "ok", status=args.status, note=args.note, post_result=res)
    print(f"{args.item_id} -> {args.status} (post: {res})")
    return 0 if res != "failed" else 1


def cmd_replay(args):
    d = intake_dir()
    n = 0
    for i in read_jsonl(d / "inbox.jsonl"):
        if i["source"] != "owner":
            continue
        st = current_status(d, i["item_id"])
        if st and st["status"] == "DONE":
            continue
        n += 1
        print(f"{i['item_id']}\t{(st or {}).get('status', 'NEW')}\t{i['author']}\t{i['created_at']}\t"
              f"{i['body'].strip().splitlines()[0][:80] if i['body'].strip() else ''}")
    return 0


def cmd_show(args):
    i = find_item(intake_dir(), args.item_id)
    if not i:
        print("unknown item", file=sys.stderr)
        return 2
    st = current_status(intake_dir(), args.item_id)
    print(f"{i['item_id']}  {i['author']}  {i['created_at']}  status={(st or {}).get('status', i['status'])}\n{i['url']}\n\n{i['body']}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--auto-ack", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("status")
    s.add_argument("item_id")
    s.add_argument("status", choices=STATUSES)
    s.add_argument("--note", default="")
    s.add_argument("--post", action="store_true")
    sh = sub.add_parser("show")
    sh.add_argument("item_id")
    a = ap.parse_args(argv)
    lock = open(intake_dir() / ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("another intake process holds the lock", file=sys.stderr)
        return 0
    if a.cmd == "status":
        return cmd_status(a)
    if a.cmd == "show":
        return cmd_show(a)
    if a.replay:
        return cmd_replay(a)
    return poll(a)


if __name__ == "__main__":
    sys.exit(main())
