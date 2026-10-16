#!/usr/bin/env python3
"""CAOSCare always-on coordination watch (one service, three checks).

Every poll (60 s): host evidence about the ONE existing Main Claude session
(coord_host), new comments on the authoritative issue(s) (coord_github), and
the dispatch gate (coord_queue). It publishes deduplicated receipts, detects
missed ACKs / stale workers / boundaries, and delivers the next already
authorized bounded item to the EXISTING coordinator through the intake it
already consumes (a comment on the authoritative issue). It never spawns a
Claude session, never calls a model, never reads transcripts, never posts
private resident content, and never uses a paid API (gh only).

State: ~/.local/state/caoscare-coordination/{state.json,events.jsonl}
Usage: coordination_watch.py --once | --loop | --status
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import coord_github as gh  # noqa: E402
import coord_host as host  # noqa: E402
import coord_queue as cq  # noqa: E402

STATE_DIR = Path(os.environ.get("CAOS_COORD_STATE", Path.home() / ".local/state/caoscare-coordination"))
STATE_FILE = STATE_DIR / "state.json"
EVENTS = STATE_DIR / "events.jsonl"
DRY = os.environ.get("CAOS_COORD_DRY_RUN") == "1"


def _now():
    return datetime.now(timezone.utc)


def _iso(dt=None):
    return (dt or _now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except ValueError:
            pass
    return {"cursor": _iso(_now() - timedelta(minutes=10)), "published": {}, "dispatched": {}, "last": {},
            "boundary_seen": False, "owner_open": {}}


def save_state(st: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(st, indent=1))


def record(kind: str, **fields) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with EVENTS.open("a") as f:
        f.write(json.dumps({"at": _iso(), "kind": kind, **fields}) + "\n")


def publish(st: dict, q: dict, key: str, title: str, fields: dict, wake: bool = False, mirror: bool = True) -> dict:
    """Exactly one GitHub receipt per dedup key. Returns the urls (or the reason it was skipped)."""
    if key in st["published"]:
        return {"skipped": "duplicate", "key": key}
    out = {"key": key}
    if DRY:
        out["dry_run"] = True
    else:
        out["issue_url"] = gh.post_comment(q["repo"], q["authoritative_issue"], gh.receipt_body(title, fields, wake=wake)) if wake or fields.get("_to_issue") else None
        if mirror and q.get("mirror_pr"):
            out["mirror_url"] = gh.post_comment(q["repo"], q["mirror_pr"], gh.receipt_body(title, fields, mirror=True))
    st["published"][key] = {"at": _iso(), **out}
    record("published", key=key, title=title, **{k: v for k, v in out.items() if k != "key"})
    return out


def base_fields(q: dict, hs: dict, task_id="UNKNOWN", state="observed", **extra) -> dict:
    f = {"timestamp": gh.chicago(), "task": task_id, "coordinator": q["coordinator"]["session_name"],
         "state": state, "branch": q.get("branch", "integration/2026-09-27"), "head_sha": "UNKNOWN", "tested_sha": "UNKNOWN",
         "loaded_sha": "UNKNOWN", "host_state": hs.get("verdict", "UNVERIFIED"),
         "last_host_evidence": "; ".join(hs.get("evidence", [])[-1:]) or "none",
         "receipt/evidence": "UNKNOWN", "eta": "UNKNOWN",
         "next_check_at": gh.chicago(_iso(_now() + timedelta(seconds=q["timers"]["poll_seconds"]))),
         "blocker": "NONE", "next_action": "keep watching"}
    # accept the older field names used by callers
    for a, b in (("task_id", "task"), ("branch_sha", "head_sha"), ("evidence", "receipt/evidence")):
        if a in extra:
            extra[b] = extra.pop(a)
    f.update(extra)
    return f


def tick(st: dict, q: dict) -> dict:
    pin, timers = q["coordinator"], q["timers"]
    hs = host.coordinator_state(pin, timers["stall_minutes"])
    dup = host.duplicate_guard(pin)
    summary = {"host": hs["verdict"], "sessions_in_cwd": dup["interactive_sessions_in_cwd"], "events": []}
    # --- GitHub transitions since the cursor
    newest = st["cursor"]
    seen = []
    for n in q["watch_issues"]:
        try:
            for c in gh.comments_since(q["repo"], n, st["cursor"]):
                if c.get("created_at", "") <= st["cursor"]:
                    continue
                cl = gh.classify(c)
                cl["issue"] = n
                seen.append(cl)
                newest = max(newest, c["created_at"])
        except RuntimeError as e:
            summary["events"].append({"github_error": str(e)[:120]})
    seen.sort(key=lambda x: x["created_at"])
    for cl in seen:
        if cl["kind"] == "watcher":
            continue
        key = f"c{cl['id']}"
        if cl["kind"] == "owner_directive":
            st["owner_open"][key] = {"at": cl["created_at"], "url": cl["url"], "issue": cl["issue"]}
            publish(st, q, key, f"OWNER DIRECTIVE observed on #{cl['issue']}",
                    base_fields(q, hs, state="DELIVERED (owner comment awaiting coordinator ACK/response)",
                                evidence=cl["url"], next_action="expect ACK/WORKING within %d min" % timers["ack_minutes"]))
        elif cl["kind"] in ("coordinator_receipt", "receiver_status", "da_delivery"):
            st["owner_open"] = {k: v for k, v in st["owner_open"].items() if v["at"] > cl["created_at"]}   # any coordinator post answers earlier directives
            st["last"] = {"state": cl["state"], "at": cl["created_at"], "url": cl["url"], "items": cl["items"], "header": cl["header"]}
            if cl["boundary"]:
                st["boundary_seen"] = True
            task = ", ".join(cl["items"]) or "UNKNOWN"
            publish(st, q, key, f"COORDINATOR {cl['state']}: {cl['header'][:90]}",
                    base_fields(q, hs, task_id=task, state=cl["state"] + (" / BOUNDARY" if cl["boundary"] else ""),
                                branch_sha=", ".join(cl["shas"]) or "UNKNOWN", evidence=cl["url"],
                                next_action="reconcile queue; dispatch next item at boundary" if cl["state"] == "DONE" else "keep watching"))
            # ACK detection for our own deliveries
            for item_id, d in st["dispatched"].items():
                if d.get("ack_url") is None and item_id in cl["items"] and cl["state"] in ("ACK", "WORKING", "DONE", "BLOCKED"):
                    d["ack_url"], d["ack_at"], d["ack_state"] = cl["url"], cl["created_at"], cl["state"]
                    publish(st, q, f"ack-{item_id}", f"ACK DETECTED for {item_id}",
                            base_fields(q, hs, task_id=item_id, state=f"{cl['state']} (coordinator acknowledged the automatic delivery)",
                                        evidence=cl["url"], next_action="watch for WORKING/DONE"))
        summary["events"].append({"kind": cl["kind"], "state": cl["state"], "url": cl["url"]})
    st["cursor"] = newest
    # --- exceptions: missed ACK on owner directives, stale/stopped host
    cutoff = _iso(_now() - timedelta(minutes=timers["ack_minutes"]))
    for key, od in list(st["owner_open"].items()):
        if od["at"] < cutoff:
            publish(st, q, f"missed-ack-{key}", "EXCEPTION: no coordinator response to an owner comment",
                    base_fields(q, hs, state="MISSED ACK" if hs["live"] else "MISSED ACK — APPEARS STALE — HOST STATE UNVERIFIED",
                                evidence=od["url"], blocker="coordinator has not acknowledged within %d min" % timers["ack_minutes"],
                                next_action="coordinator: respond on the issue; owner notified only if the host is proven stopped", _to_issue=True), wake=False)
    for item_id, d in list(st["dispatched"].items()):
        if d.get("ack_url") is None and d["at"] < cutoff and not d.get("missed_ack"):
            d["missed_ack"] = True
            publish(st, q, f"missed-ack-dispatch-{item_id}", f"EXCEPTION: delivery {item_id} not acknowledged",
                    base_fields(q, hs, task_id=item_id, state="MISSED ACK" if hs["live"] else "APPEARS STALE — HOST STATE UNVERIFIED",
                                evidence=d["url"], blocker="no ACK within %d min" % timers["ack_minutes"], next_action="hold; re-deliver only at owner instruction", _to_issue=True))
    if hs["verdict"] == "STOPPED":
        publish(st, q, f"stopped-{hs.get('pid')}", "NEED_OWNER: coordinator process is not running (host evidence)",
                base_fields(q, hs, state="BLOCKED", evidence="; ".join(hs["evidence"]), blocker="Main Claude session stopped; no automatic restart (duplicate-worker rule)",
                            next_action="owner: `claude --resume %s` in the coordinator tmux/terminal, then the watcher resumes" % pin["session_id"], _to_issue=True))
    elif hs["verdict"] in ("STALE", "UNVERIFIED") and st["last"].get("state") == "WORKING":
        publish(st, q, f"stale-{st['last'].get('url')}", "EXCEPTION: APPEARS STALE — HOST STATE UNVERIFIED" if hs["verdict"] == "UNVERIFIED" else "EXCEPTION: coordinator idle while WORKING",
                base_fields(q, hs, state="APPEARS STALE — HOST STATE UNVERIFIED" if hs["verdict"] == "UNVERIFIED" else "STALE",
                            evidence="; ".join(hs["evidence"]), blocker="no host activity for %d min" % timers["stall_minutes"], _to_issue=True))
    # --- dispatch: a pending coordination test first (ungated), then the next real item only through the gate
    dispatched_ids = set(st["dispatched"])
    test_item = cq.next_ready(q, dispatched_ids, kind="coordination_test")
    if test_item and hs["live"]:
        deliver(st, q, hs, test_item, "test (ungated, harmless)")
    else:
        ok, why = cq.gate_open(q, st["boundary_seen"], hs)
        nxt = cq.next_ready(q, dispatched_ids)
        if nxt and ok and all(d.get("ack_url") for d in st["dispatched"].values() if d.get("kind") != "coordination_test"):
            deliver(st, q, hs, nxt, why)
        summary["gate"] = why
        summary["prepared_next"] = nxt["id"] if nxt else None
    return summary


def deliver(st: dict, q: dict, hs: dict, item: dict, why: str) -> None:
    text = cq.delivery_text(item, q["authoritative_issue"], q["coordinator"]["session_name"])
    body = gh.WATCH + "\n" + text    # WATCH only: this must wake Main Claude's own watch
    url = None if DRY else gh.post_comment(q["repo"], q["authoritative_issue"], body)
    st["dispatched"][item["id"]] = {"at": _iso(), "url": url, "kind": item.get("kind", "task"), "why": why}
    record("delivered", item=item["id"], url=url, why=why, host=hs["verdict"])
    publish(st, q, f"delivered-{item['id']}", f"DELIVERED {item['id']} to the existing coordinator",
            base_fields(q, hs, task_id=item["id"], state="DELIVERED (awaiting ACK)", evidence=url or "dry-run",
                        next_action=f"coordinator posts ACK {item['id']} on #{q['authoritative_issue']}", eta="UNKNOWN"), wake=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    q = cq.load_queue()
    st = load_state()
    if a.status:
        hs = host.coordinator_state(q["coordinator"], q["timers"]["stall_minutes"])
        print(json.dumps({"host": hs, "duplicates": host.duplicate_guard(q["coordinator"]), "cursor": st["cursor"],
                          "last": st["last"], "boundary_seen": st["boundary_seen"], "dispatched": st["dispatched"],
                          "published": len(st["published"]), "gate": cq.gate_open(q, st["boundary_seen"], hs)[1]}, indent=1))
        return
    while True:
        try:
            s = tick(st, q)
            save_state(st)
            print(json.dumps({"at": _iso(), **s}), flush=True)
        except Exception as e:  # keep the service alive; the next tick retries
            record("error", error=repr(e)[:300])
            print(json.dumps({"at": _iso(), "error": repr(e)[:300]}), flush=True)
        if not a.loop:
            break
        time.sleep(q["timers"]["poll_seconds"])
        q = cq.load_queue()


if __name__ == "__main__":
    main()
