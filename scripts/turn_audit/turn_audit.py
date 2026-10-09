#!/usr/bin/env python3
"""Event-only audio-turn audit (RQ-054). No audio, no transcripts, read-only.

Joins two event streams that already exist:
  * realtime_diagnostics for one session (speech_started/stopped, response_created,
    output_audio_buffer_started/stopped(cleared)) - what the SERVER heard;
  * the wake listener's `audio_level` summaries (raw eMeet capture, before the
    browser's echo cancellation/noise suppression) - what the MIC heard.
Question answered per user turn: did the server end the turn where the raw
microphone says the person stopped, or earlier (clipped / quiet syllables)?
Also lists raw speech that the server never registered, split into "during
assistant playback" (owner double-talk OR the speaker's own voice - the raw
source has no echo cancellation, so these cannot be told apart) and "while
idle" (a real miss).

usage: turn_audit.py SESSION_ID  [--hold-ms 1000]   (Mongo + journalctl)
"""
import json, subprocess, sys
from datetime import datetime, timedelta

CLOSE_QUIET_S = 0.5   # LevelTracker closes a segment after 0.5 s of quiet


def ts(s):
    return datetime.fromisoformat(s).timestamp()


def raw_segments(levels):
    """audio_level events -> [(start, last_voiced, mean_dbfs)] in epoch seconds."""
    out = []
    for e in levels:
        end = ts(e["at"])
        out.append((end - e["duration_s"], end - CLOSE_QUIET_S, e["mean_dbfs"]))
    return out


def analyze(events, levels, hold_ms=1000):
    ev = sorted(events, key=lambda e: e["created_at"])
    lo, hi = ts(ev[0]["created_at"]), ts(ev[-1]["created_at"]) + 1.0
    segs = [g for g in raw_segments(levels) if g[1] >= lo and g[0] <= hi]
    play, user = [], []   # [(start, end)]
    cur_p = cur_u = None
    for e in ev:
        t, k = ts(e["created_at"]), e["event_type"]
        if k == "output_audio_buffer_started":
            cur_p = t
        elif k == "output_audio_buffer_stopped" and cur_p is not None:
            play.append((cur_p, t)); cur_p = None
        elif k == "speech_started":
            cur_u = t
        elif k == "speech_stopped" and cur_u is not None:
            user.append((cur_u, t)); cur_u = None
    turns = []
    for s, stop in user:
        voiced_server = stop - hold_ms / 1000.0
        near = [g for g in segs if g[0] <= voiced_server + 0.3 and g[1] >= s - 1.0]
        raw_end = max((g[1] for g in near), default=None)
        resumed = [round(stop - g[0], 2) for g in segs if voiced_server + 0.3 < g[0] <= stop]
        turns.append({"raw_speech_resumed_s_before_commit": resumed, "server_start_s": round(s, 2), "server_last_voiced_s": round(voiced_server, 2),
                      "raw_last_voiced_s": None if raw_end is None else round(raw_end, 2),
                      "end_delta_s": None if raw_end is None else round(voiced_server - raw_end, 2),
                      "raw_peak_mean_dbfs": max((g[2] for g in near), default=None)})
    unseen = []
    for a, b, mean in segs:
        if any(s - 0.3 <= b and a <= e + 0.3 for s, e in user):
            continue
        where = "during_assistant_playback" if any(ps <= b and a <= pe for ps, pe in play) else "while_idle"
        unseen.append({"start_s": round(a, 2), "end_s": round(b, 2), "mean_dbfs": mean, "where": where})
    return {"turns": turns, "raw_speech_unseen_by_server": unseen}


def load(session_id):
    from pymongo import MongoClient
    docs = list(MongoClient()["caoscare"].realtime_diagnostics.find({"session_id": session_id}))
    for d in docs:
        d["created_at"] = d["created_at"] if isinstance(d["created_at"], str) else d["created_at"].isoformat()
    t0 = datetime.fromisoformat(min(d["created_at"] for d in docs))
    since, until = (t0 - timedelta(seconds=15)).astimezone(), (t0 + timedelta(minutes=10)).astimezone()
    out = subprocess.run(["journalctl", "--user", "-u", "aria-wake.service", "-o", "cat", "--no-pager",
                          "--since", since.strftime("%Y-%m-%d %H:%M:%S"), "--until", until.strftime("%Y-%m-%d %H:%M:%S")],
                         capture_output=True, text=True).stdout
    levels = [j for j in (json.loads(x) for x in out.splitlines() if x.startswith("{")) if j.get("event") == "audio_level"]
    return docs, levels


if __name__ == "__main__":
    hold = int(sys.argv[sys.argv.index("--hold-ms") + 1]) if "--hold-ms" in sys.argv else 1000
    print(json.dumps(analyze(*load(sys.argv[1]), hold_ms=hold), indent=1))
