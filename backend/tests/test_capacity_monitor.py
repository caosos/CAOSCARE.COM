"""Capacity monitoring: traffic separation, alert levels, hysteresis,
cooldown, recommendations, acknowledgment, resolution, projection and
receipts. Runs in a child process against a throwaway caos_cap_test_* DB with
synthetic samples (no load is generated; host readings are exercised once)."""
import os
from pathlib import Path
import subprocess
import sys
import uuid


def test_capacity_monitor():
    env = {**os.environ, "DB_NAME": f"caos_cap_test_{uuid.uuid4().hex[:12]}", "OPENAI_API_KEY": ""}
    r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--isolated"], env=env, text=True,
                       capture_output=True, timeout=120)
    print(r.stdout)
    assert r.returncode == 0, r.stdout + r.stderr


def sample(i=0, *, voice_turns=0, sim_turns=0, rate_limited=0, llm_failures=0, worker_cpu=20.0, host_cpu=20.0,
           own_share=None, mem=40.0, swap_out=0.0, disk=40.0, db_ping=2.0, receipt_p95=5.0, device_epm=10.0,
           api=None, latency_p95=2.0, active=0, slots=40, reserved=8):
    return {"sample_id": f"s{i}", "at": f"2026-10-04T{10 + i // 60:02d}:{i % 60:02d}:00+00:00", "interval_s": 15,
            "host": {"cpu_pct": host_cpu, "memory": {"used_pct": mem}, "swap_out_per_s": swap_out,
                     "disk_used_pct": disk, "cores": 8},
            "voice": {"turns": voice_turns + sim_turns, "real": voice_turns, "simulated": sim_turns,
                      "rate_limited": rate_limited, "llm_failures": llm_failures, "timeouts": 0,
                      "latency_p95_s": latency_p95,
                      "admission": {"active": active, "slots": slots, "reserved": reserved, "workers": 1}},
            "api": api or {"staff_dashboard": {"requests": 10, "errors": 0, "latency_sum_ms": 50}},
            "db": {"ping_ms": db_ping}, "receipts": {"write_p95_ms": receipt_p95},
            "devices": {"events_per_min": device_epm}, "caoscare_worker_cpu_max_pct": worker_cpu,
            "caoscare_cpu_share_pct": own_share if own_share is not None else host_cpu}


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    assert os.environ["DB_NAME"].startswith("caos_cap_test_")
    import asyncio
    from deps import db
    from routes import capacity_alerts as ca, capacity_model as cm
    from routes.capacity_telemetry import Recorder, classify_request, host_counters, host_reading

    cfg = {**cm.DEFAULT_CONFIG, "safe": dict(cm.DEFAULT_CONFIG["safe"])}

    def series(n, start=0, **kw):
        out = []
        for i in range(n):
            s = sample(start + i, **kw)
            s["utilization"] = cm.utilization(s, cfg)
            out.append(s)
        return out

    async def run():
        # ---- traffic classes: real vs simulated never mixed -------------
        assert classify_request("/api/voice-bridge/turn", "POST") == "resident_voice"
        assert classify_request("/api/voice-bridge/turn", "POST", simulated=True) == "simulator_resident"
        assert classify_request("/api/tasks", "GET", simulated=True) == "simulator_staff"
        assert classify_request("/api/rf/event", "POST") == "pendant_help"
        assert classify_request("/api/devices/public/room/101/command", "POST") == "resident_device"
        assert classify_request("/api/tasks/t1/complete", "POST") == "staff_workflow"
        rec = Recorder()
        rec.voice_turn("information", "served", 2.0, simulated=False)
        rec.voice_turn("conversation", "served", 2.0, simulated=True)
        rec.voice_turn("operational", "degraded", 3.0, simulated=False, error="HTTP 429 rate limited")
        snap = rec.snapshot()
        assert snap["voice"]["real"] == 2 and snap["voice"]["simulated"] == 1 and snap["voice"]["rate_limited"] == 1
        print("OK traffic classes and real/simulated separation")

        a = cm.attribution(sample(voice_turns=200), "voice_turns_per_min")
        assert a == {"traffic_class": "resident_voice", "simulated": False, "simulated_share": 0.0}
        a = cm.attribution(sample(voice_turns=20, sim_turns=300), "voice_turns_per_min")
        assert a["traffic_class"] == "simulator_resident" and a["simulated"]
        a = cm.attribution(sample(api={"staff_dashboard": {"requests": 900, "latency_sum_ms": 9000},
                                       "resident_voice": {"requests": 10, "latency_sum_ms": 100}}), "worker_cpu_pct")
        assert a["traffic_class"] == "staff_dashboard"
        a = cm.attribution(sample(api={"staff_dashboard": {"requests": 300, "latency_sum_ms": 3000},
                                       "resident_voice": {"requests": 300, "latency_sum_ms": 6000}}), "worker_cpu_pct")
        assert a["traffic_class"] == "resident_voice"
        print("OK resident-only, staff-only, combined attribution")

        # ---- alert opens only when sustained; hysteresis -----------------
        quiet = series(10)
        assert await ca.evaluate(quiet, cfg, quiet[-1]["at"]) == []
        spike = quiet + series(1, 10, worker_cpu=99)          # one sample: not sustained
        assert not [x for x in await ca.evaluate(spike, cfg, spike[-1]["at"]) if x[0] == "opened"]
        hot = spike + series(4, 11, worker_cpu=99)
        acts = await ca.evaluate(hot, cfg, hot[-1]["at"])
        assert ("opened", "worker_cpu_pct", "CRITICAL") in acts, acts
        assert ("recommended", "worker_cpu_pct", "add_voice_worker") in acts
        alert = await db.capacity_alerts.find_one({"metric": "worker_cpu_pct"}, {"_id": 0})
        for f in ("component", "measured_value", "tested_safe_value", "traffic_class", "simulated",
                  "recommendation", "telemetry", "opened_at", "origin_receipt_id"):
            assert f in alert, f
        # oscillating just under/over the threshold does not resolve it
        wobble = hot + series(3, 16, worker_cpu=90) + series(1, 19, worker_cpu=97) + series(3, 20, worker_cpu=90)
        assert not [x for x in await ca.evaluate(wobble, cfg, wobble[-1]["at"]) if x[0] == "resolved"]
        assert await db.capacity_alerts.count_documents({"metric": "worker_cpu_pct"}) == 1
        print("OK sustained opening, CPU saturation recommendation, hysteresis")

        # ---- acknowledgment and manual resolution need evidence -----------
        user = {"user_id": "user_admin_t", "name": "T Admin", "role": "admin"}
        assert (await ca.acknowledge(alert["alert_id"], user, "looking"))["ok"]
        r = await ca.resolve_manually(alert["alert_id"], user, "", 0.99, cfg)
        assert not r["ok"] and "evidence" in r["detail"]
        r = await ca.resolve_manually(alert["alert_id"], user, "spike over", 0.99, cfg)
        assert not r["ok"] and "action taken" in r["detail"]
        r = await ca.resolve_manually(alert["alert_id"], user, "second worker started, CPU now 45%", 0.99, cfg,
                                      action_taken="CAOSCARE workers 1 -> 2")
        assert r["ok"]
        chain = await db.receipts.find({"related_object_id": alert["alert_id"]}, {"_id": 0}).sort("created_at", 1).to_list(20)
        kinds = [x["action_type"] for x in chain]
        assert kinds == ["capacity_alert_opened", "capacity_recommendation_issued", "capacity_alert_acknowledged",
                         "capacity_added_or_configuration_changed", "capacity_alert_resolved"], kinds
        assert all(x["correlation_id"] == chain[0]["receipt_id"] for x in chain)
        assert all(chain[i]["parent_receipt_id"] == chain[i - 1]["receipt_id"] for i in range(1, len(chain)))
        assert chain[2]["identity_basis"] == "authenticated" and chain[0]["identity_basis"] == "system"
        print("OK acknowledgment, evidence-gated resolution, receipt chain")

        # ---- cooldown: same level does not reopen at once; higher does ----
        again = series(6, 30, worker_cpu=99)
        from datetime import datetime, timedelta, timezone
        t = datetime.now(timezone.utc)
        acts = await ca.evaluate(again, cfg, (t + timedelta(seconds=60)).isoformat())
        assert ("cooldown", "worker_cpu_pct", "CRITICAL") in acts
        later = await ca.evaluate(again, cfg, (t + timedelta(hours=2)).isoformat())
        assert ("opened", "worker_cpu_pct", "CRITICAL") in later
        await db.capacity_alerts.delete_many({})
        print("OK cooldown")

        # ---- automatic resolution after sustained recovery ----------------
        up = series(6, 0, receipt_p95=90)
        assert ("opened", "receipt_write_p95_ms", "ACTION_NEEDED") in await ca.evaluate(up, cfg, up[-1]["at"])
        down = up + series(8, 6, receipt_p95=5)
        assert ("resolved", "receipt_write_p95_ms", "ACTION_NEEDED") in await ca.evaluate(down, cfg, down[-1]["at"])
        print("OK receipt-latency alert (investigate database) and automatic resolution")

        # ---- recommendations by cause ----------------------------------
        def rec_for(key, attr_sample, level="ACTION_NEEDED", held=0):
            return cm.recommendation(key, level, cm.attribution(attr_sample, key), held, cfg)["type"]
        assert rec_for("voice_rate_limited_per_min", sample(voice_turns=100)) == "increase_provider_quota"
        assert rec_for("voice_provider_errors_per_min", sample(voice_turns=100)) == "repair_provider"
        assert rec_for("voice_turns_per_min", sample(voice_turns=10, sim_turns=500)) == "pause_simulator"
        assert rec_for("host_cpu_pct", sample(host_cpu=95, own_share=10)) == "reduce_background"
        assert rec_for("device_events_per_min", sample()) == "correct_device_flood"
        assert cm.attribution(sample(mem=95, sim_turns=900), "memory_used_pct")["simulated"] is False
        assert rec_for("memory_used_pct", sample(mem=95)) is None                 # not sustained long enough
        assert rec_for("memory_used_pct", sample(mem=95), held=1200) == "add_ram"
        assert rec_for("disk_used_pct", sample(disk=95), held=1200) == "add_storage"
        assert rec_for("host_cpu_pct", sample(host_cpu=95, own_share=80), held=1200) == "add_cpu"
        assert rec_for("host_cpu_pct", sample(host_cpu=95, own_share=80), level="WATCH", held=9999) is None
        print("OK recommendations: provider quota, provider repair, simulator, background, device flood, "
              "RAM/disk/CPU only when sustained")

        # ---- bursts produce the right alerts ------------------------------
        flood = series(6, 0, device_epm=900)
        assert ("opened", "device_events_per_min", "CRITICAL") in await ca.evaluate(flood, cfg, flood[-1]["at"])
        disk = series(6, 0, disk=80)
        acts = await ca.evaluate(disk, cfg, disk[-1]["at"])
        assert ("opened", "disk_used_pct", "WATCH") in acts or ("opened", "disk_used_pct", "ACTION_NEEDED") in acts
        mem = series(6, 0, mem=83, swap_out=60)
        acts = await ca.evaluate(mem, cfg, mem[-1]["at"])
        assert ("opened", "swap_out_per_s", "CRITICAL") in acts
        bg = series(6, 0, host_cpu=96, own_share=8)
        acts = await ca.evaluate(bg, cfg, bg[-1]["at"])
        assert ("recommended", "host_cpu_pct", "reduce_background") in acts, acts
        sim = series(6, 0, sim_turns=400)
        await ca.evaluate(sim, cfg, sim[-1]["at"])
        sim_alert = await db.capacity_alerts.find_one({"metric": "voice_turns_per_min", "status": "open"})
        assert sim_alert["simulated"] is True and sim_alert["traffic_class"] == "simulator_resident"
        assert sim_alert["recommendation"]["type"] == "pause_simulator"
        print("OK device flood, disk pressure, memory pressure, background burst, simulator burst")

        # ---- headroom, bottleneck, reserve -------------------------------
        h = cm.headroom(sample(worker_cpu=70, active=20), cfg)
        assert h["bottleneck"] == "worker_cpu_pct" and h["headroom_pct"] == 30.0
        assert h["emergency_reserve"]["reserved_staff_help_slots"] == 8
        print("OK headroom, bottleneck, emergency reserve")

        # ---- projection ------------------------------------------------
        p = cm.projection([("2026-10-01", 0.40), ("2026-10-02", 0.45), ("2026-10-03", 0.50), ("2026-10-04", 0.55)])
        assert p["status"] == "rising" and p["projected_date"] == "2026-10-09", p
        assert cm.projection([("2026-10-01", 0.5), ("2026-10-02", 0.5), ("2026-10-03", 0.5)])["status"] == "flat_or_falling"
        assert cm.projection([("2026-10-01", 0.5)])["status"] == "insufficient_history"
        print("OK capacity projection")

        # ---- real host readings ------------------------------------------
        a0 = host_counters()
        await asyncio.sleep(0.3)
        h = host_reading(a0, host_counters())
        assert 0 <= h["cpu_pct"] <= 100 and h["memory"]["total_mb"] > 0 and h["disk_total_gb"] > 0
        assert len(h["cpu_per_core_pct"]) == h["cores"]
        print("OK host readings from /proc")

    asyncio.run(run())
    print("ALL CAPACITY CHECKS PASSED")


def main_api():
    """Separate process: Motor binds to one event loop per process."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    assert os.environ["DB_NAME"].startswith("caos_cap_test_")
    from deps import db
    from fastapi import APIRouter, FastAPI
    from fastapi.testclient import TestClient
    from deps import require_admin
    from routes import capacity_monitor
    app = FastAPI()
    api = APIRouter(prefix="/api")
    api.include_router(capacity_monitor.router)
    app.include_router(api)
    app.dependency_overrides[require_admin] = lambda: {"user_id": "user_admin_t", "role": "admin", "name": "T Admin"}
    with TestClient(app) as c:
        assert c.post("/api/capacity/evaluate").status_code == 200   # first host reading
        assert c.post("/api/capacity/evaluate").status_code == 200   # second: real host rates
        st = c.get("/api/capacity/status").json()
        assert st["latest"]["host"]["cpu_pct"] is not None and st["latest"]["db"]["ping_ms"] >= 0
        assert st["latest"]["headroom"]["bottleneck"] and st["status"] in ("NORMAL", "WATCH", "ACTION_NEEDED", "CRITICAL")
        assert c.put("/api/capacity/config", json={"levels": {"WATCH": 0.9, "ACTION_NEEDED": 0.8},
                                                   "reason": "bad"}).status_code == 422
        r = c.put("/api/capacity/config", json={"safe": {"db_ping_ms": 40}, "reason": "tighter DB target"})
        assert r.status_code == 200 and r.json()["safe"]["db_ping_ms"] == 40
        rc = c.portal.call(lambda: db.receipts.find_one({"action_type": "capacity_configuration_changed"}, {"_id": 0}))
        assert rc["before_state"]["safe"]["db_ping_ms"] == 50 and rc["after_state"]["safe"]["db_ping_ms"] == 40
        assert c.post("/api/capacity/alerts/nope/resolve", json={"evidence": "x"}).status_code == 404
        c.portal.call(lambda: db.client.drop_database(os.environ["DB_NAME"]))
    print("OK admin API: live sample, status, validated config change with receipt")


def test_capacity_api():
    env = {**os.environ, "DB_NAME": f"caos_cap_test_{uuid.uuid4().hex[:12]}", "OPENAI_API_KEY": ""}
    r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--api"], env=env, text=True,
                       capture_output=True, timeout=120)
    print(r.stdout)
    assert r.returncode == 0, r.stdout + r.stderr


if __name__ == "__main__" and "--isolated" in sys.argv:
    main()
if __name__ == "__main__" and "--api" in sys.argv:
    main_api()
