#!/usr/bin/env python3
"""Tally a physical wake-word session from the listener's JSON-lines log.

  wake_stats.py summary [--log FILE|-] [--since ISO] [--marks FILE] [--backend URL --room 214]
  wake_stats.py mark miss  [--note TEXT]    # "I said it and nothing happened"
  wake_stats.py mark false [--note TEXT]    # "it woke and I did not say it"
  wake_stats.py mark note  --note TEXT

The listener log is the stdout of aria_wake.py (journalctl -o cat -u aria-wake, or a
file). Marks are Michael's own observations, one JSON line each in a local file
(default ~/.local/state/aria_wake/marks.jsonl, env ARIA_WAKE_MARKS). Standard
library only; no audio, no transcripts.

What the log can and cannot say:
  wake_detected       the detector fired and a page was connected
  confirmed           the page then reported "conversation" (it started a session)
  unconfirmed         no page confirmation within 20 s (pending_wake_expired)
  suppressed          a detection while a conversation/pending wake was running
                      (Aria's own speech or the resident talking) - NOT acted on
  no_client           detected, but no room page was connected, so nothing happened
Which Realtime session a wake became is in the backend's activation events
(wake_word_session_bound, admin timeline) - not reconstructed here.
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

DEFAULT_MARKS = os.path.expanduser(os.environ.get("ARIA_WAKE_MARKS", "~/.local/state/aria_wake/marks.jsonl"))


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def read_jsonl(fh):
    for line in fh:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            yield json.loads(line)
        except ValueError:
            continue


def summarize(events, marks, since=None):
    s = {"wakes": 0, "confirmed": 0, "unconfirmed": 0, "no_client": 0, "suppressed": 0,
         "suppressed_by_mode": {}, "sessions": 0, "confirm_latency_s": [], "session_s": [],
         "capture_restarts": 0, "refused_to_start": 0, "first": None, "last": None, "phrases": set()}
    pending = None       # (wake time) awaiting page confirmation
    conv_start = None
    wake_times = []
    for e in events:
        t = parse_ts(e["at"])
        if since and t < since:
            continue
        s["first"] = s["first"] or e["at"]
        s["last"] = e["at"]
        ev = e.get("event")
        if ev == "wake_detected":
            s["wakes"] += 1
            pending = t
            wake_times.append(t)
            if e.get("phrase"):
                s["phrases"].add(e["phrase"])
        elif ev == "detection_suppressed":
            s["suppressed"] += 1
            m = e.get("mode", "?")
            s["suppressed_by_mode"][m] = s["suppressed_by_mode"].get(m, 0) + 1
        elif ev == "detection_no_client":
            s["no_client"] += 1
        elif ev == "pending_wake_expired":
            s["unconfirmed"] += 1
            pending = None
        elif ev == "mode_conversation":
            if pending is not None:
                s["confirmed"] += 1
                s["confirm_latency_s"].append((t - pending).total_seconds())
                pending = None
            conv_start = t
        elif ev == "mode_listening":
            if conv_start is not None:
                s["sessions"] += 1
                s["session_s"].append((t - conv_start).total_seconds())
                conv_start = None
        elif ev == "capture_started":
            s["capture_restarts"] += 1
        elif ev == "refused_to_start":
            s["refused_to_start"] += 1
    m = {"miss": 0, "false": 0, "note": 0, "false_matched_to_wake": 0}
    for r in marks:
        t = parse_ts(r["at"])
        if since and t < since:
            continue
        m[r["kind"]] = m.get(r["kind"], 0) + 1
        if r["kind"] == "false" and any(0 <= (t - w).total_seconds() <= 30 for w in wake_times):
            m["false_matched_to_wake"] += 1
    s["marks"] = m
    return s


def avg(xs):
    return round(sum(xs) / len(xs), 2) if xs else None


def render(s, hours=None):
    ph = ", ".join(sorted(s["phrases"])) or "(none logged)"
    lines = [f"window: {s['first']} -> {s['last']}", f"phrase: {ph}",
             f"wakes (detector fired, page connected): {s['wakes']}",
             f"  confirmed by the page (session started): {s['confirmed']}  (avg {avg(s['confirm_latency_s'])} s after detection)",
             f"  unconfirmed (expired after 20 s): {s['unconfirmed']}",
             f"detected with no page connected (nothing happened): {s['no_client']}",
             f"detections suppressed during a conversation/pending wake: {s['suppressed']} {s['suppressed_by_mode'] or ''}",
             f"conversations ended back to listening: {s['sessions']}  (avg {avg(s['session_s'])} s)",
             f"capture (re)starts: {s['capture_restarts']}   refused to start: {s['refused_to_start']}",
             f"MARKED by Michael: miss={s['marks']['miss']}  false wake={s['marks']['false']} "
             f"(of which within 30 s after a logged wake: {s['marks']['false_matched_to_wake']})  notes={s['marks']['note']}"]
    if hours:
        lines.append(f"false wakes per hour of ambient test: {s['marks']['false'] / hours:.2f} over {hours} h")
    return "\n".join(lines)


def backend_lease(base, room):
    try:
        with urllib.request.urlopen(f"{base.rstrip('/')}/api/realtime/room/{room}/status", timeout=5) as r:
            lease = (json.loads(r.read()) or {}).get("lease")
    except Exception as exc:
        return f"backend not reachable ({exc.__class__.__name__}); wake-to-session binding is in the admin activation timeline"
    return f"backend reachable; room {room} lease now: {json.dumps(lease) if lease else 'none (no live session)'}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sm = sub.add_parser("summary")
    sm.add_argument("--log", default="-", help="listener log file, or - for stdin")
    sm.add_argument("--since", help="ISO time; ignore anything earlier")
    sm.add_argument("--marks", default=DEFAULT_MARKS)
    sm.add_argument("--hours", type=float, help="length of an ambient false-wake test, for per-hour rate")
    sm.add_argument("--backend", help="e.g. http://127.0.0.1:8092 - also show the room's live lease")
    sm.add_argument("--room", default="214")
    mk = sub.add_parser("mark")
    mk.add_argument("kind", choices=["miss", "false", "note"])
    mk.add_argument("--note", default="")
    mk.add_argument("--marks", default=DEFAULT_MARKS)
    a = ap.parse_args(argv)

    if a.cmd == "mark":
        os.makedirs(os.path.dirname(a.marks), exist_ok=True)
        rec = {"at": datetime.now(timezone.utc).isoformat(), "kind": a.kind, "note": a.note}
        with open(a.marks, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(f"recorded {a.kind} at {rec['at']} -> {a.marks}")
        return 0

    events = list(read_jsonl(sys.stdin if a.log == "-" else open(a.log, encoding="utf-8", errors="replace")))
    marks = list(read_jsonl(open(a.marks, encoding="utf-8"))) if os.path.exists(a.marks) else []
    since = parse_ts(a.since) if a.since else None
    print(render(summarize(events, marks, since), a.hours))
    if a.backend:
        print(backend_lease(a.backend, a.room))
    return 0


if __name__ == "__main__":
    sys.exit(main())
