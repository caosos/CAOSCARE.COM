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
import intake_inbox as inbox  # noqa: E402
import receiver  # noqa: E402

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
            "boundary_seen": False, "owner_open": {}, "owner_acked": {}, "seen_ids": [], "known_sessions": []}


def save_state(st: dict) -> None:
    if DRY:  # a dry run never persists: it must not mark items dispatched or receipts published
        return
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(st, indent=1))


def record(kind: str, **fields) -> None:
    if DRY:
        return
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


ACK_STATES = ("ACK", "WORKING", "DONE", "BLOCKED")
RECEIPT_KINDS = ("coordinator_receipt", "receiver_status")     # DELIVERED / watcher / DA posts never answer anything


def _ack_seconds(timers: dict) -> int:
    return int(timers.get("ack_seconds", timers.get("ack_minutes", 30) * 60))


def _age(iso: str) -> float:
    return (_now() - datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds()


def correlated(od: dict, cl: dict) -> bool:
    """A receipt answers an owner command only if it is a coordinator receipt posted after it, in an ACK/WORKING/DONE/
    BLOCKED state, that cites the command id (c<id> / its URL) or one of the command's own task ids."""
    return (cl["kind"] in RECEIPT_KINDS and cl["state"] in ACK_STATES and cl["created_at"] > od["at"]
            and (str(od.get("id")) in cl.get("commands", []) or bool(set(od.get("tasks") or []) & set(cl["items"]))))


def pickup_rows(command: str) -> list:
    try:
        return [r for r in receiver.read() if r.get("kind") == "pickup" and r.get("command") == command]
    except (OSError, ValueError):
        return []


def intake_text(q: dict, command: str, task: str, url: str, why: str) -> str:
    pin = q["coordinator"]["session_name"]
    return (f"CAOSCARE INTAKE {why} — owner command {command} on #{q['authoritative_issue']} ({url}), task {task}. "
            f"Step 1: `python3 {HERE}/receiver.py pickup {command} --task {task} --session {pin}`; act ONLY on NEW "
            f"(DUPLICATE/COMPLETED = do nothing). Then post a receipt whose first line is `ACK — {task} (session {pin})` citing {command}, "
            f"and re-arm `intake_inbox.py listen --session {pin}`.")


def send(q: dict, hs: dict, command: str, tasks: list, url: str, reason: str) -> dict:
    """Queue one entry for the EXISTING pinned coordinator's armed in-session listener (its exit wakes the session).
    Starts nothing. Reports honestly whether the listener is armed under the pinned session's own pid."""
    pin = q["coordinator"]
    task = (tasks or [command])[0]
    arm = inbox.armed(pin["session_name"], hs.get("pid")) if hs.get("live") else {"armed": False, "why": f"coordinator {hs.get('verdict')}"}
    if DRY:
        return {"at": _iso(), "ok": None, "armed": arm.get("armed"), "note": "dry run: not queued"}
    r = inbox.deliver(pin["session_name"], command, task, intake_text(q, command, task, url, reason.upper()), reason)
    note = f"queued (seq {r.get('seq', 'dup')}) for listener pid {arm['pid']}" if arm.get("armed") else f"queued, but NOT armed: {arm.get('why')}"
    record("intake", command=command, task=task, reason=reason, armed=arm.get("armed"), note=note)
    return {"at": _iso(), "ok": bool(arm.get("armed")), "armed": arm.get("armed"), "note": note}


def tick(st: dict, q: dict) -> dict:
    pin, timers = q["coordinator"], q["timers"]
    hs = host.coordinator_state(pin, timers["stall_minutes"])
    dup = host.duplicate_guard(pin)
    summary = {"host": hs["verdict"], "sessions_in_cwd": dup["interactive_sessions_in_cwd"], "events": []}
    # --- GitHub transitions since the cursor
    newest = st["cursor"]
    seen = []
    known = host.known_sessions() | set(st.setdefault("known_sessions", []))
    st["known_sessions"] = sorted(known)
    seen_ids = set(st.setdefault("seen_ids", []))
    # overlap window: a comment created in the same second as the cursor (or listed late by GitHub) is still read once;
    # comment ids, not timestamps, decide what is new. No overlap until ids are tracked (upgrade from an older state).
    floor = _iso(datetime.fromisoformat(st["cursor"].replace("Z", "+00:00")) - timedelta(minutes=5)) if seen_ids else st["cursor"]
    for n in q["watch_issues"]:
        try:
            for c in gh.comments_since(q["repo"], n, floor):
                if c.get("id") in seen_ids or c.get("created_at", "") <= floor:
                    continue
                seen_ids.add(c.get("id"))
                cl = gh.classify(c, known_sessions=known)
                cl["issue"] = n
                seen.append(cl)
                newest = max(newest, c["created_at"])
        except RuntimeError as e:
            summary["events"].append({"github_error": str(e)[:120]})
    st["seen_ids"] = sorted(i for i in seen_ids if i is not None)[-5000:]
    seen.sort(key=lambda x: x["created_at"])
    for cl in seen:
        if cl["kind"] == "watcher":
            continue
        key = f"c{cl['id']}"
        if cl["kind"] == "owner_directive":
            st["owner_open"][key] = {"at": cl["created_at"], "url": cl["url"], "issue": cl["issue"], "id": str(cl["id"]),
                                     "tasks": cl["tasks"], "recipient": pin["session_name"]}
            st["owner_open"][key]["delivery"] = send(q, hs, key, cl["tasks"], cl["url"], "delivery")
            publish(st, q, key, f"OWNER DIRECTIVE observed on #{cl['issue']}",
                    base_fields(q, hs, state="DELIVERED (owner comment awaiting coordinator ACK/response)",
                                evidence=cl["url"], next_action="expect a correlated ACK/WORKING within %d s" % _ack_seconds(timers)))
        elif cl["kind"] in ("coordinator_receipt", "receiver_status", "da_delivery"):
            for k, od in list(st["owner_open"].items()):          # only a correlated receipt answers a command
                if correlated(od, cl):
                    st.setdefault("owner_acked", {})[k] = {**st["owner_open"].pop(k), "ack_url": cl["url"], "ack_at": cl["created_at"],
                                                           "ack_state": cl["state"], "ack_session": cl.get("session")}
                    publish(st, q, f"ack-{k}", f"ACK DETECTED for owner command {k}",
                            base_fields(q, hs, task_id=", ".join(od.get("tasks") or []) or k, state=f"{cl['state']} (correlated to {k})",
                                        evidence=cl["url"], coordinator=cl.get("session") or pin["session_name"], next_action="watch for WORKING/DONE"))
            if cl["kind"] not in RECEIPT_KINDS:
                summary["events"].append({"kind": cl["kind"], "state": cl["state"], "url": cl["url"]})
                continue
            st["last"] = {"state": cl["state"], "at": cl["created_at"], "url": cl["url"], "items": cl["items"], "header": cl["header"]}
            if cl["boundary"] and cl["issue"] in q.get("boundary_issues", [q["authoritative_issue"]]):
                st["boundary_seen"] = True
                st["boundary_url"] = cl["url"]
            task = ", ".join(cl["items"]) or "UNKNOWN"
            publish(st, q, key, f"COORDINATOR {cl['state']}: {cl['header'][:90]}",
                    base_fields(q, hs, task_id=task, state=cl["state"] + (" / BOUNDARY" if cl["boundary"] else ""),
                                branch_sha=", ".join(cl["shas"]) or "UNKNOWN", evidence=cl["url"],
                                next_action="reconcile queue; dispatch next item at boundary" if cl["state"] == "DONE" else "keep watching"))
            # ACK / DONE detection for our own deliveries
            for item_id, d in st["dispatched"].items():
                if item_id in cl["items"] and cl["state"] == "DONE" and d.get("done_url") is None and cl["created_at"] > d["at"]:
                    d["done_url"], d["done_at"] = cl["url"], cl["created_at"]      # task boundary for the next real item
                    publish(st, q, f"done-{item_id}", f"DONE DETECTED for {item_id} — task boundary",
                            base_fields(q, hs, task_id=item_id, state="DONE (task boundary; next authorized item may dispatch)",
                                        evidence=cl["url"], next_action="dispatch the next READY queue item when the coordinator is idle"))
                if d.get("ack_url") is None and item_id in cl["items"] and cl["state"] in ACK_STATES and cl["created_at"] > d["at"]:
                    d["ack_url"], d["ack_at"], d["ack_state"] = cl["url"], cl["created_at"], cl["state"]
                    publish(st, q, f"ack-{item_id}", f"ACK DETECTED for {item_id}",
                            base_fields(q, hs, task_id=item_id, state=f"{cl['state']} (coordinator acknowledged the automatic delivery)",
                                        evidence=cl["url"], next_action="watch for WORKING/DONE"))
                    if d.get("kind") != "coordination_test":   # a real ACK proves the intake: earlier tests are implicitly ACKed
                        for t_id, t in st["dispatched"].items():
                            if t.get("kind") == "coordination_test" and t.get("ack_url") is None and t["at"] <= d["at"]:
                                t["ack_url"], t["ack_at"], t["ack_state"] = cl["url"], cl["created_at"], "IMPLICIT"
        summary["events"].append({"kind": cl["kind"], "state": cl["state"], "url": cl["url"]})
    st["cursor"] = newest
    # --- exceptions: missed ACK -> ONE redelivery through the armed in-session listener -> ONE NEED if still unanswered
    limit = _ack_seconds(timers)
    for key, od in list(st["owner_open"].items()):
        od.setdefault("id", key[1:]); od.setdefault("tasks", [])   # entries written before 2026-10-16 correlate by command id only
        rows = pickup_rows(key)
        if rows and not od.get("pickup_at"):
            od["pickup_at"], od["pickup_session"] = rows[0]["time"], rows[0].get("session")
            publish(st, q, f"pickup-{key}", f"PICKUP OBSERVED for owner command {key}",
                    base_fields(q, hs, task_id=", ".join(od.get("tasks") or []) or key, state=f"PICKED UP by {od['pickup_session']} at {od['pickup_at']} (intake ledger)",
                                evidence=od["url"], next_action="expect a correlated ACK/WORKING within %d s" % limit))
        if od.get("pickup_at") or _age(od["at"]) < limit:
            continue
        if not od.get("recovery"):
            od["recovery"] = send(q, hs, key, od.get("tasks"), od["url"], "redelivery")
            publish(st, q, f"missed-ack-{key}", "EXCEPTION: no correlated ACK to an owner command — one redelivery",
                    base_fields(q, hs, task_id=", ".join(od.get("tasks") or []) or key,
                                state="MISSED ACK — REDELIVERED to the armed listener" if od["recovery"].get("ok") else "MISSED ACK — COORDINATOR NOT REACHABLE",
                                evidence=od["url"], blocker="no correlated ACK within %d s; %s" % (limit, od["recovery"].get("note")),
                                next_action=("coordinator: receiver.py pickup %s, then ACK citing it" % key) if od["recovery"].get("ok") else
                                ("in session %s run (background): python3 %s/intake_inbox.py listen --session %s" % (pin["session_name"], HERE, pin["session_name"])),
                                _to_issue=True), wake=False)
        elif _age(od["recovery"]["at"]) >= limit and not od.get("need_owner"):
            od["need_owner"] = True
            publish(st, q, f"need-{key}", "NEED_OWNER: owner command still unanswered after one redelivery",
                    base_fields(q, hs, task_id=", ".join(od.get("tasks") or []) or key, state="BLOCKED",
                                evidence=od["url"], blocker="redelivery: %s; no pickup or ACK %d s later" % (od["recovery"].get("note"), limit),
                                next_action="owner: paste the command URL into the %s terminal (never a second session)" % pin["session_name"], _to_issue=True))
    for item_id, d in list(st["dispatched"].items()):
        if d.get("ack_url") is None and _age(d["at"]) >= limit and not d.get("missed_ack"):
            d["missed_ack"] = True
            d["recovery"] = send(q, hs, item_id, [item_id], d["url"], "redelivery")
            publish(st, q, f"missed-ack-dispatch-{item_id}", f"EXCEPTION: delivery {item_id} not acknowledged — one redelivery",
                    base_fields(q, hs, task_id=item_id, state="MISSED ACK — REDELIVERED to the armed listener" if d["recovery"].get("ok") else "MISSED ACK — COORDINATOR NOT REACHABLE",
                                evidence=d["url"], blocker="no ACK within %d s; %s" % (limit, d["recovery"].get("note")),
                                next_action="coordinator: receiver.py pickup, then ACK %s" % item_id, _to_issue=True))
    if hs["verdict"] == "STOPPED":
        publish(st, q, f"stopped-{hs.get('pid')}", "NEED_OWNER: coordinator process is not running (host evidence)",
                base_fields(q, hs, state="BLOCKED", evidence="; ".join(hs["evidence"]), blocker="Main Claude session stopped; no automatic restart (duplicate-worker rule)",
                            next_action="owner: `claude --resume %s` in the coordinator tmux/terminal, then the watcher resumes" % pin["session_id"], _to_issue=True))
    elif hs["verdict"] == "PIN_MISMATCH":
        publish(st, q, f"pin-mismatch-{hs.get('session_id')}", "NEED: coordinator pin is stale (registry name/id disagree)",
                base_fields(q, hs, state="BLOCKED", evidence="; ".join(hs["evidence"]), blocker="pinned identity does not match the registry; nothing is delivered on a guess",
                            next_action="verify the legitimate coordinator by session id/cwd/receipts, then update coordinator in COORDINATION_QUEUE.json by commit", _to_issue=True))
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
        # serial rule: every earlier delivery ACKed, and every earlier REAL item DONE (the task boundary), before the next real item
        prior_done = all(d.get("done_url") for d in st["dispatched"].values() if d.get("kind") != "coordination_test")
        if nxt and ok and prior_done and all(d.get("ack_url") for d in st["dispatched"].values()):
            deliver(st, q, hs, nxt, why)
        summary["gate"] = why if (ok and prior_done) or not ok else "waiting for DONE of the active item (task boundary)"
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
                          "last": st["last"], "boundary_seen": st["boundary_seen"], "boundary_url": st.get("boundary_url"), "dispatched": st["dispatched"],
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
