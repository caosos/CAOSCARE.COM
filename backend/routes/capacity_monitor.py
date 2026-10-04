"""Capacity monitor: sampling loop, request middleware and admin API.

Every worker publishes its own counters (capacity_telemetry.RECORDER, voice
admission, its CPU) to `capacity_worker_stats`. One worker at a time holds
`capacity_monitor_lock` and turns the published counters, host readings and
database counts into a `capacity_samples` document every interval, then
evaluates capacity alerts (capacity_alerts.py). Samples are kept 30 days.

    CAOSCARE_CAPACITY_MONITOR      1 (default) / 0 to switch off
    CAOSCARE_CAPACITY_INTERVAL_S   15
"""
import asyncio
import hashlib
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError

from deps import db, require_admin
from models import uid
from routes import capacity_alerts, capacity_model
from routes.capacity_telemetry import RECORDER, SIM_HEADER, classify_request, host_counters, host_reading
from routes.receipts import create_receipt

router = APIRouter(prefix="/capacity", tags=["capacity"])
INTERVAL = float(os.environ.get("CAOSCARE_CAPACITY_INTERVAL_S") or 15)
WORKER_ID = f"{os.uname().nodename}:{os.getpid()}"
_state = {"host_prev": None, "cpu_prev": None, "mongod_prev": None, "loops": 0}


# ------------------------------------------------------------ middleware --

async def capacity_middleware(request, call_next):
    t0 = time.monotonic()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        path = request.url.path
        if path.startswith("/api") and not path.startswith("/api/health"):
            simulated = request.headers.get(SIM_HEADER, "").lower() == "simulator"
            try:
                simulated = simulated or response.headers.get("x-caoscare-simulated") == "1"
            except NameError:
                pass
            auth = request.headers.get("authorization") or request.cookies.get("session_token") or ""
            client = hashlib.sha256(auth.encode()).hexdigest()[:12] if auth else None
            RECORDER.request(classify_request(path, request.method, simulated),
                             (time.monotonic() - t0) * 1000, status, path, client)


# ---------------------------------------------------------- per worker ----

def _proc_cpu_pct() -> Optional[float]:
    t, cpu = time.monotonic(), sum(os.times()[:2])
    prev, _state["cpu_prev"] = _state["cpu_prev"], (t, cpu)
    if not prev:
        return None
    return round((cpu - prev[1]) / max(t - prev[0], 1e-6) * 100, 1)


async def publish_worker_stats():
    from routes.voice_bridge_admission import ADMISSION
    snap = RECORDER.snapshot()
    await db.capacity_worker_stats.update_one({"worker": WORKER_ID}, {"$set": {
        "worker": WORKER_ID, "at": datetime.now(timezone.utc), "cpu_pct": _proc_cpu_pct(),
        "recorder": snap, "admission": ADMISSION.snapshot()}}, upsert=True)


async def _is_leader() -> bool:
    now = datetime.now(timezone.utc)
    try:
        await db.capacity_monitor_lock.find_one_and_update(
            {"_id": "leader", "$or": [{"holder": WORKER_ID}, {"expires": {"$lt": now}}]},
            {"$set": {"holder": WORKER_ID, "expires": now + timedelta(seconds=INTERVAL * 3)}}, upsert=True)
        return True
    except DuplicateKeyError:  # another worker holds an unexpired lock
        return False


# ------------------------------------------------------------- sampling ---

def _mongod_cpu_pct() -> Optional[float]:
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                with open(f"/proc/{p}/comm") as f:
                    if f.read().strip() != "mongod":
                        continue
                with open(f"/proc/{p}/stat") as f:
                    parts = f.read().rsplit(")", 1)[1].split()
                ticks = (int(parts[11]) + int(parts[12])) / os.sysconf("SC_CLK_TCK")
            except (OSError, IndexError, ValueError):
                continue
            t = time.monotonic()
            prev, _state["mongod_prev"] = _state["mongod_prev"], (t, ticks)
            return round((ticks - prev[1]) / max(t - prev[0], 1e-6) * 100, 1) if prev else None
    return None


def _merge(workers: list) -> dict:
    voice = {"turns": 0, "real": 0, "simulated": 0, "timeouts": 0, "llm_failures": 0, "rate_limited": 0,
             "outcomes": {}, "classes": {}}
    lat, api, receipts_ms, writes, reports = [], {}, [], 0, 0
    staff, board = set(), set()
    adm = {"active": 0, "queued": 0, "slots": 0, "reserved": 0, "reserved_in_use": 0, "oldest_queued_s": 0.0,
           "workers": len(workers)}
    for w in workers:
        r = w.get("recorder") or {}
        v = r.get("voice") or {}
        for k in ("turns", "real", "simulated", "timeouts", "llm_failures", "rate_limited"):
            voice[k] += v.get(k, 0)
        for k in ("outcomes", "classes"):
            for name, n in (v.get(k) or {}).items():
                voice[k][name] = voice[k].get(name, 0) + n
        lat += v.get("latency_s") or []
        for c, a in (r.get("api") or {}).items():
            x = api.setdefault(c, {"requests": 0, "errors": 0, "latency_sum_ms": 0.0, "p95_ms": None})
            x["requests"] += a.get("requests", 0)
            x["errors"] += a.get("errors", 0)
            x["latency_sum_ms"] += a.get("latency_sum_ms", 0)
            x["p95_ms"] = max(filter(None, [x["p95_ms"], a.get("p95_ms")]), default=None)
        receipts_ms += (r.get("receipts") or {}).get("write_ms") or []
        writes += (r.get("receipts") or {}).get("writes", 0)
        reports += r.get("reports", 0)
        staff |= set(r.get("staff_users") or [])
        board |= set(r.get("live_board_users") or [])
        a = w.get("admission") or {}
        for k in ("active", "queued", "reserved_in_use"):
            adm[k] += a.get(k, 0)
        adm["slots"] = max(adm["slots"], a.get("slots", 0))
        adm["reserved"] = max(adm["reserved"], a.get("reserved", 0))
        adm["oldest_queued_s"] = max(adm["oldest_queued_s"], a.get("oldest_queued_s") or 0.0)

    def pct(v, q):
        v = sorted(v)
        return round(v[min(len(v) - 1, int(q * (len(v) - 1) + 0.5))], 2) if v else None
    voice.update(latency_p50_s=pct(lat, .5), latency_p95_s=pct(lat, .95), latency_p99_s=pct(lat, .99),
                 admission=adm)
    return {"voice": voice, "api": api,
            "receipts": {"writes": writes, "write_p95_ms": pct(receipts_ms, .95), "backlog": 0},
            "staff": {"active_clients": len(staff), "live_board_clients": len(board), "reports": reports}}


async def _db_metrics() -> dict:
    t0 = time.monotonic()
    await db.command("ping")
    ping = round((time.monotonic() - t0) * 1000, 2)
    try:
        conns = (await db.client.admin.command("serverStatus")).get("connections", {})
    except Exception:
        conns = {}
    return {"ping_ms": ping, "connections_current": conns.get("current"), "connections_available": conns.get("available")}


async def _domain_counts(since: datetime, now: datetime) -> dict:
    s_iso = since.isoformat()
    open_sessions = await db.voice_bridge_sessions.count_documents(
        {"status": "open", "last_turn_at": {"$gte": now - timedelta(minutes=10)}})
    new_sessions = await db.voice_bridge_sessions.count_documents({"opened_at": {"$gte": since}})
    devices = await db.smart_devices.count_documents({})
    online = await db.smart_devices.count_documents({"online": {"$ne": False}})
    cmds = await db.device_commands.find({"issued_at": {"$gte": s_iso}},
                                         {"_id": 0, "status": 1, "issued_at": 1, "acked_at": 1}).to_list(5000)
    acks = []
    for c in cmds:
        try:
            acks.append((datetime.fromisoformat(c["acked_at"]) - datetime.fromisoformat(c["issued_at"])).total_seconds() * 1000)
        except (KeyError, TypeError, ValueError):
            pass
    pendant = await db.rf_events.count_documents({"received_at": {"$gte": s_iso}})
    recent_tasks = await db.staff_tasks.find({"created_at": {"$gte": (now - timedelta(hours=1)).isoformat(),
                                                             "$lt": (now - timedelta(seconds=30)).isoformat()}},
                                             {"_id": 0, "task_id": 1}).to_list(500)
    orphans = 0
    for t in recent_tasks:
        if not await db.receipts.count_documents({"related_object_id": t["task_id"]}, limit=1):
            orphans += 1
    window_min = max((now - since).total_seconds() / 60, 1e-6)
    return {
        "voice_sessions": {"active": open_sessions, "new_per_min": round(new_sessions / window_min, 2)},
        "devices": {"configured": devices, "online": online, "offline": devices - online,
                    "commands": len(cmds), "failed_commands": sum(1 for c in cmds if c.get("status") == "failed"),
                    "events_per_min": round((len(cmds) + pendant) / window_min, 1),
                    "pendant_events": pendant, "ack_p95_ms": sorted(acks)[int(0.95 * (len(acks) - 1))] if acks else None},
        "receipts_orphan_recent_tasks": orphans,
    }


async def take_sample(config: Optional[dict] = None) -> dict:
    now = datetime.now(timezone.utc)
    since = now - timedelta(seconds=INTERVAL * 2)
    workers = await db.capacity_worker_stats.find({"at": {"$gte": since}}, {"_id": 0}).to_list(64)
    merged = _merge(workers)
    cur = await asyncio.to_thread(host_counters)
    prev, _state["host_prev"] = _state["host_prev"], cur
    host = host_reading(prev, cur) if prev else None
    worker_cpu = [w.get("cpu_pct") for w in workers if w.get("cpu_pct") is not None]
    mongod = _mongod_cpu_pct()
    cores = (host or {}).get("cores") or os.cpu_count() or 1
    own = round((sum(worker_cpu) + (mongod or 0)) / cores, 1) if worker_cpu else None
    sample = {"sample_id": uid("capsample"), "at": now.isoformat(), "at_dt": now, "interval_s": INTERVAL,
              "host": host, "db": await _db_metrics(), **merged, **await _domain_counts(since, now),
              "caoscare_worker_cpu_pct": worker_cpu, "caoscare_worker_cpu_max_pct": max(worker_cpu) if worker_cpu else None,
              "mongod_cpu_pct": mongod, "caoscare_cpu_share_pct": own,
              "background": {"monitor_loops": _state["loops"]}}
    sample["voice"]["active_sessions"] = sample["voice_sessions"]["active"]
    config = config or await get_config()
    sample["utilization"] = capacity_model.utilization(sample, config)
    sample["headroom"] = capacity_model.headroom(sample, config)
    await db.capacity_samples.insert_one(dict(sample))
    return sample


async def tick():
    """One monitor step: publish this worker; if leader, sample and evaluate."""
    _state["loops"] += 1
    await publish_worker_stats()
    if not await _is_leader():
        return None
    config = await get_config()
    sample = await take_sample(config)
    recent = await db.capacity_samples.find({}, {"_id": 0}).sort("at_dt", -1).to_list(30)
    return await capacity_alerts.evaluate(list(reversed(recent)), config, sample["at"])


async def run_forever():
    await db.capacity_samples.create_index("at_dt", expireAfterSeconds=30 * 24 * 3600)
    await db.capacity_alerts.create_index([("metric", 1), ("status", 1)])
    while True:
        try:
            await tick()
        except Exception as e:  # monitoring must never take the service down
            logging.warning("capacity monitor tick failed: %s", e)
        await asyncio.sleep(INTERVAL)


# --------------------------------------------------------------- config ---

async def get_config() -> dict:
    doc = await db.capacity_config.find_one({"_id": "current"}, {"_id": 0}) or {}
    cfg = {**capacity_model.DEFAULT_CONFIG, **{k: v for k, v in doc.items() if k != "safe"}}
    cfg["safe"] = {**capacity_model.DEFAULT_CONFIG["safe"], **(doc.get("safe") or {})}
    return cfg


class ConfigUpdate(BaseModel):
    safe: Optional[dict] = None
    levels: Optional[dict] = None
    sustain_samples: Optional[dict] = None
    clear_margin: Optional[float] = None
    clear_samples: Optional[int] = None
    cooldown_s: Optional[int] = None
    hardware_after_s: Optional[int] = None
    reason: str


class AckBody(BaseModel):
    note: Optional[str] = ""


class ResolveBody(BaseModel):
    evidence: str
    action_taken: Optional[str] = None


# ------------------------------------------------------------------ API ----

def _daily_peaks(rows: list, key: str) -> list:
    by_day = {}
    for r in rows:
        u = (r.get("utilization") or {}).get(key)
        if u is not None:
            d = r["at"][:10]
            by_day[d] = max(by_day.get(d, 0), u)
    return sorted(by_day.items())


@router.get("/status")
async def status(user=Depends(require_admin)):
    config = await get_config()
    latest = await db.capacity_samples.find_one({}, {"_id": 0, "at_dt": 0}, sort=[("at_dt", -1)])
    alerts = await db.capacity_alerts.find({"status": {"$in": ["open", "acknowledged"]}}, {"_id": 0}).to_list(50)
    level = max([a["level"] for a in alerts], key=capacity_model.LEVELS.index, default="NORMAL")
    proj = None
    if latest and latest.get("headroom", {}).get("bottleneck"):
        since = datetime.now(timezone.utc) - timedelta(days=14)
        rows = await db.capacity_samples.find({"at_dt": {"$gte": since}}, {"_id": 0, "at": 1, "utilization": 1}).to_list(100000)
        proj = capacity_model.projection(_daily_peaks(rows, latest["headroom"]["bottleneck"]),
                                         config["levels"]["ACTION_NEEDED"])
    return {"status": level, "latest": latest, "alerts": alerts, "projection": proj, "config": config,
            "monitor": {"interval_s": INTERVAL, "enabled": os.environ.get("CAOSCARE_CAPACITY_MONITOR", "1") != "0"}}


@router.get("/samples")
async def samples(minutes: int = 60, user=Depends(require_admin)):
    since = datetime.now(timezone.utc) - timedelta(minutes=max(1, min(minutes, 7 * 24 * 60)))
    return await db.capacity_samples.find({"at_dt": {"$gte": since}}, {"_id": 0, "at_dt": 0}).sort("at_dt", 1).to_list(5000)


@router.get("/alerts")
async def alerts(status: Optional[str] = None, user=Depends(require_admin)):
    q = {"status": status} if status else {}
    return await db.capacity_alerts.find(q, {"_id": 0}).sort("opened_at", -1).to_list(200)


@router.post("/alerts/{alert_id}/acknowledge")
async def ack(alert_id: str, body: AckBody, user=Depends(require_admin)):
    r = await capacity_alerts.acknowledge(alert_id, user, body.note or "")
    if not r["ok"]:
        raise HTTPException(409, r["detail"])
    return r


@router.post("/alerts/{alert_id}/resolve")
async def resolve(alert_id: str, body: ResolveBody, user=Depends(require_admin)):
    alert = await db.capacity_alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    if not alert:
        raise HTTPException(404, "alert not found")
    latest = await db.capacity_samples.find_one({}, {"_id": 0, "utilization": 1}, sort=[("at_dt", -1)])
    r = await capacity_alerts.resolve_manually(alert_id, user, body.evidence,
                                               ((latest or {}).get("utilization") or {}).get(alert["metric"]),
                                               await get_config(), body.action_taken)
    if not r["ok"]:
        raise HTTPException(409, r["detail"])
    return r


@router.get("/config")
async def read_config(user=Depends(require_admin)):
    return await get_config()


@router.put("/config")
async def update_config(body: ConfigUpdate, user=Depends(require_admin)):
    before = await get_config()
    changes = body.model_dump(exclude_none=True)
    reason = changes.pop("reason")
    for k in ("safe", "levels", "sustain_samples"):
        if k in changes:
            changes[k] = {**before[k], **changes[k]}
    if "levels" in changes and not (0 < changes["levels"]["WATCH"] < changes["levels"]["ACTION_NEEDED"]
                                    < changes["levels"]["CRITICAL"] <= 1.5):
        raise HTTPException(422, "levels must rise: 0 < WATCH < ACTION_NEEDED < CRITICAL <= 1.5")
    if any((v or 0) <= 0 for v in changes.get("safe", {}).values()):
        raise HTTPException(422, "safe values must be positive")
    await db.capacity_config.update_one({"_id": "current"}, {"$set": changes}, upsert=True)
    after = await get_config()
    await create_receipt(
        action_type="capacity_configuration_changed", related_object_type="capacity_config",
        related_object_id="current", source="staff", status="completed", result=reason[:300],
        provenance={**capacity_alerts.user_actor(user), "before_state": {k: before.get(k) for k in changes},
                    "after_state": {k: after.get(k) for k in changes}, "result_label": "verified",
                    "next_state": "applied"})
    return after


@router.post("/evaluate")
async def evaluate_now(user=Depends(require_admin)):
    """Take one sample and evaluate alerts now (also runs every interval)."""
    return {"actions": await tick() or []}
