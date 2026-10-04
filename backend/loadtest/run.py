"""Voice-bridge load harness: simulated Home Assistant Voice PE rooms against
the real /api/voice-bridge/turn route.

Starts a private backend (loadtest.mock_app: real app, simulated language
model, blank provider keys, throwaway caos_vb_load_* database), seeds one
community/apartment/resident/device per room, runs rooms concurrently with
simulated speech-to-text and text-to-speech latency and limits, samples CPU,
memory, descriptors and connections, verifies receipts and workflow state,
and writes machine-readable results.

    cd backend && .venv/bin/python -m loadtest.run --scenario levels
    .venv/bin/python -m loadtest.run --scenario saturation --max-active 8 --reserved 2
    .venv/bin/python -m loadtest.run --scenario failure
"""
import argparse
import asyncio
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
TOKEN_HDR = "load-test-bridge-token"
BLANK = ("OPENAI_API_KEY", "RESEND_API_KEY", "RESEND_FROM_EMAIL", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN",
         "TWILIO_FROM_NUMBER", "TWILIO_FROM_PHONE", "PERPLEXITY_API_KEY", "HA_TOKEN", "HA_BASE_URL")


def pct(v, q):
    v = sorted(v)
    return round(v[min(len(v) - 1, int(q * (len(v) - 1) + 0.5))], 1) if v else None


class Limiter:
    """Simulated HA-side STT/TTS provider: per-request latency + concurrency cap."""
    def __init__(self, ms, jitter_ms, max_conc):
        self.ms, self.jitter, self.sem = ms, jitter_ms, asyncio.Semaphore(max_conc)
        self.waits = []

    async def run(self):
        t0 = time.monotonic()
        async with self.sem:
            self.waits.append(time.monotonic() - t0)
            await asyncio.sleep(max(0.0, (self.ms + random.uniform(-1, 1) * self.jitter) / 1000))


async def room_session(client, url, r, script, conv, stt, tts, start, out):
    from routes.voice_bridge_admission import CLASS_NAMES, classify
    await start.wait()
    prev = None
    for idx, (text, kind) in enumerate(script):
        if kind == "retry":
            text = prev
        else:
            await stt.run()
        rec = {"room": r["room"], "resident_id": r["resident_id"], "kind": kind, "turn": idx,
               "expected_class": "session_end" if kind == "ending" else "retry" if kind == "retry"
               else CLASS_NAMES[classify(text)], "t0": time.monotonic()}
        try:
            resp = await client.post(url, headers={"Authorization": f"Bearer {TOKEN_HDR}"}, json={
                "text": text, "conversation_id": conv, "device_id": r["device_id"], "language": "en"})
            rec["response_s"] = time.monotonic() - rec["t0"]
            rec["status"] = resp.status_code
            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            for k in ("session_id", "receipt_id", "continue_conversation", "deferred", "duplicate",
                      "degraded", "priority_class", "queue_wait_ms", "session_ended"):
                rec[k] = body.get(k)
            reply = body.get("response_text") or ""
            import re
            others = set(re.findall(r"LT\d{3}[A-Z]{2}", reply)) - {r["token"]}
            rec["leak"] = sorted(others)
            if resp.status_code == 200 and not rec.get("deferred"):
                await tts.run()
            rec["complete_s"] = time.monotonic() - rec["t0"]
        except Exception as e:  # dropped: no answer reached the room
            rec.update(status=None, error=f"{type(e).__name__}: {e}", response_s=time.monotonic() - rec["t0"])
        out.append(rec)
        prev = text
        if rec.get("continue_conversation") is False:
            break


def summarize(turns, duration, resources, checks, admission):
    ok = [t for t in turns if t.get("status") == 200]
    served = [t for t in ok if not t.get("deferred") and not t.get("degraded")]
    first = {}
    for t in turns:
        first.setdefault(t["resident_id"], t)
    by_class = {}
    for t in turns:
        c = by_class.setdefault(t["expected_class"], {"turns": 0, "deferred": 0, "degraded": 0, "resp": []})
        c["turns"] += 1
        c["deferred"] += bool(t.get("deferred"))
        c["degraded"] += bool(t.get("degraded"))
        if t.get("response_s") is not None:
            c["resp"].append(t["response_s"])
    for c in by_class.values():
        r = c.pop("resp")
        c.update(p50_s=pct(r, .5), p95_s=pct(r, .95), max_s=pct(r, 1))
    resp = [t["response_s"] for t in ok]
    comp = [t["complete_s"] for t in served if t.get("complete_s")]
    return {
        "rooms": len(first), "turns": len(turns), "duration_s": round(duration, 1),
        "throughput_turns_per_s": round(len(turns) / duration, 2) if duration else None,
        "accepted_sessions": sum(1 for t in first.values() if t.get("status") == 200 and not t.get("deferred")),
        "rejected_sessions": sum(1 for t in first.values() if t.get("status") not in (200, None)),
        "deferred_first_turns": sum(1 for t in first.values() if t.get("deferred")),
        "queued_turns": sum(1 for t in ok if (t.get("queue_wait_ms") or 0) > 0),
        "max_queue_wait_ms": max([t.get("queue_wait_ms") or 0 for t in ok] or [0]),
        "deferred_turns": sum(1 for t in ok if t.get("deferred")),
        "dropped_turns": sum(1 for t in turns if t.get("status") is None),
        "http_errors": sum(1 for t in turns if t.get("status") not in (200, None)),
        "degraded_turns": sum(1 for t in ok if t.get("degraded")),
        "duplicates_answered_once": sum(1 for t in ok if t.get("duplicate")),
        "first_ack_s": {"p50": pct(resp, .5), "p95": pct(resp, .95), "p99": pct(resp, .99), "max": pct(resp, 1)},
        "complete_response_s": {"p50": pct(comp, .5), "p95": pct(comp, .95), "p99": pct(comp, .99),
                                "max": pct(comp, 1)},
        "client_leaks": sum(1 for t in turns if t.get("leak")),
        "dropped_examples": [{k: t.get(k) for k in ("room", "kind", "error", "response_s")}
                             for t in turns if t.get("status") is None][:10],
        "by_class": by_class, "resources": resources, "checks": checks, "server": admission,
    }


def read_stats(stats_dir):
    out = {"calls": 0, "rate_limited": 0, "failed": 0, "timeouts": 0, "leak_contexts": 0, "workers": 0,
           "prompt_chars_total": 0, "prompt_chars_max": 0,
           "admission": []}
    for f in Path(stats_dir).glob("[0-9]*.json"):
        d = json.loads(f.read_text())
        out["workers"] += 1
        for k in ("calls", "rate_limited", "failed", "timeouts", "leak_contexts", "prompt_chars_total"):
            out[k] += d.get(k, 0)
        out["prompt_chars_max"] = max(out["prompt_chars_max"], d.get("prompt_chars_max", 0))
        out["admission"].append(d.get("admission"))
    return out


async def run_level(db, port, server_pid, rooms, args, stt, tts, stats_dir, control=None, rounds=1):
    import httpx
    from loadtest.sampler import Sampler
    from loadtest.scenarios import room_script
    from loadtest.verify import verify
    for f in Path(stats_dir).glob("*.json"):
        f.unlink()
    url = f"http://127.0.0.1:{port}/api/voice-bridge/turn"
    turns, start = [], asyncio.Event()
    limits = httpx.Limits(max_connections=len(rooms) * 2, max_keepalive_connections=len(rooms) * 2)
    async with httpx.AsyncClient(timeout=25.0, limits=limits) as client:
        sampler = Sampler(server_pid, port)
        sampler.start()

        async def one_room(r, i):
            k = 0
            while k < rounds or (args.duration and time.monotonic() - t0 < args.duration):
                await room_session(client, url, r, room_script(i), f"{args.run_id}-{r['room']}-{k}",
                                   stt, tts, start, turns)
                k += 1
                if args.duration:
                    await asyncio.sleep(random.uniform(0.5, 1.5))  # pause before the resident speaks again
        t0 = time.monotonic()
        tasks = [asyncio.create_task(one_room(r, r["i"])) for r in rooms]
        if control:
            tasks.append(asyncio.create_task(control(start)))
        start.set()
        await asyncio.gather(*tasks)
        duration = time.monotonic() - t0
        resources = await sampler.stop()
    checks = await verify(db, turns, rooms)
    return summarize(turns, duration, resources, checks, read_stats(stats_dir)), turns


def start_server(args, db_name, stats_dir, control_file):
    env = {**os.environ, "DB_NAME": db_name, "CAOSCARE_VOICE_BRIDGE_TOKEN": TOKEN_HDR,
           "CAOSCARE_ENABLE_DEMO_SEED": "false", "CAOSCARE_VOICE_BRIDGE_MAX_ACTIVE": str(args.max_active),
           "CAOSCARE_VOICE_BRIDGE_RESERVED": str(args.reserved), "LOAD_LLM_LATENCY_MS": str(args.llm_ms),
           "LOAD_LLM_JITTER_MS": str(args.llm_jitter_ms), "LOAD_LLM_MAX_CONC": str(args.llm_max_conc),
           "LOAD_LLM_RPM": str(args.llm_rpm), "LOAD_STATS_DIR": stats_dir, "LOAD_CONTROL_FILE": control_file,
           "OPENAI_API_BASE": "http://127.0.0.1:9", **{k: "" for k in BLANK}}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "loadtest.mock_app:app", "--host", "127.0.0.1",
                             "--port", str(args.port), "--workers", str(args.workers), "--log-level", "warning"],
                            cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=open(f"{stats_dir}/server.log", "w"))
    import urllib.request
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{args.port}/api/health", timeout=1)
            return proc
        except Exception:
            time.sleep(0.5)
    proc.kill()
    raise SystemExit("load server did not start - see " + stats_dir + "/server.log")


async def main(args):
    db_name = f"caos_vb_load_{int(time.time())}"
    os.environ["DB_NAME"] = db_name
    for k in BLANK:
        os.environ[k] = ""
    sys.path.insert(0, str(BACKEND))
    from deps import db
    from loadtest.scenarios import room_ids, seed
    stats_dir = tempfile.mkdtemp(prefix="vbload_")
    control_file = f"{stats_dir}/control.json"
    Path(control_file).write_text('{"mode": "ok"}')
    levels = [int(x) for x in args.levels.split(",")]
    total = sum(levels) if args.scenario == "levels" else max(levels)
    await seed(db, total)
    if args.simulated_rooms:
        await db.residents.update_many({"resident_id": {"$in": [room_ids(i)["resident_id"]
                                                                for i in range(args.simulated_rooms)]}},
                                       {"$set": {"synthetic": True}})
    rooms_all = [{**room_ids(i), "i": i} for i in range(total)]
    args.run_id = db_name
    server = start_server(args, db_name, stats_dir, control_file)
    results = {"scenario": args.scenario, "config": vars(args), "db": db_name, "levels": {}}
    try:
        offset = 0
        for n in levels:
            rooms = rooms_all[offset:offset + n] if args.scenario == "levels" else rooms_all[:n]
            offset += n if args.scenario == "levels" else 0
            stt = Limiter(args.stt_ms, args.stt_ms * 0.3, args.stt_max_conc)
            tts = Limiter(args.tts_ms, args.tts_ms * 0.3, args.tts_max_conc)
            control, rounds = None, 1
            if args.scenario == "failure":
                rounds = 1
                args.duration = args.duration or 30
                log = []

                async def control(start, log=log):
                    await start.wait()
                    for mode, secs in (("ok", 4), ("down", 8), ("ok", 4), ("slow", 6), ("ok", 0)):
                        Path(control_file).write_text(json.dumps({"mode": mode}))
                        log.append({"mode": mode, "at_s": round(time.monotonic() - t_start, 1)})
                        if secs:
                            await asyncio.sleep(secs)
                t_start = time.monotonic()
            summary, turns = await run_level(db, args.port, server.pid, rooms, args, stt, tts, stats_dir,
                                             control, rounds)
            summary["stt_wait_max_s"] = round(max(stt.waits or [0]), 2)
            summary["tts_wait_max_s"] = round(max(tts.waits or [0]), 2)
            if args.scenario == "failure":
                summary["control_timeline"] = log
                for t in turns:
                    t["t_rel"] = round(t["t0"] - t_start, 1)
                summary["turn_timeline"] = [{k: t.get(k) for k in ("t_rel", "kind", "status", "degraded",
                                                                   "deferred", "response_s")} for t in turns]
            results["levels"][str(n)] = summary
            print(json.dumps({"rooms": n, "turns": summary["turns"], "first_ack_p95": summary["first_ack_s"]["p95"],
                              "deferred": summary["deferred_turns"], "degraded": summary["degraded_turns"],
                              "dropped": summary["dropped_turns"], "app_cpu_p95": summary["resources"]["app_cpu_pct"]["p95"],
                              "missing_receipts": summary["checks"]["missing_receipts"]}), flush=True)
    finally:
        server.terminate()
        try:
            server.wait(10)
        except subprocess.TimeoutExpired:
            server.kill()
        if not args.keep_db:
            await db.client.drop_database(db_name)
        log = Path(stats_dir) / "server.log"
        if log.exists():
            bad = [ln for ln in log.read_text().splitlines() if "ERROR" in ln or "Traceback" in ln or "Exception" in ln]
            if bad:
                Path(str(args.out) + ".server-errors.log").write_text("\n".join(bad))
        shutil.rmtree(stats_dir, ignore_errors=True)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=1, default=str))
    print("wrote", out)


def parse(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", choices=("levels", "saturation", "failure"), default="levels")
    p.add_argument("--levels", default="1,5,10,20,40,80")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--port", type=int, default=8097)
    p.add_argument("--max-active", type=int, default=16)
    p.add_argument("--reserved", type=int, default=4)
    p.add_argument("--llm-ms", type=int, default=1200)
    p.add_argument("--llm-jitter-ms", type=int, default=400)
    p.add_argument("--llm-max-conc", type=int, default=0)
    p.add_argument("--llm-rpm", type=int, default=0)
    p.add_argument("--stt-ms", type=int, default=400)
    p.add_argument("--stt-max-conc", type=int, default=1000)
    p.add_argument("--tts-ms", type=int, default=600)
    p.add_argument("--tts-max-conc", type=int, default=1000)
    p.add_argument("--keep-db", action="store_true")
    p.add_argument("--simulated-rooms", type=int, default=0, help="mark the first N residents synthetic")
    p.add_argument("--duration", type=float, default=0, help="keep rooms talking for this many seconds")
    p.add_argument("--out", default=str(BACKEND / "loadtest" / "results" / "levels.json"))
    return p.parse_args(argv)


if __name__ == "__main__":
    asyncio.run(main(parse()))
