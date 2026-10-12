"""careops-alerts-ingress-receipts-001: wearable, pendant-scaffold and geofence
signals go through the canonical resident activation: one open event per
resident, one provenance-complete creation receipt, device signals recorded in
signals[] (never press_count), severity only ever raised.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_alert_ingress_receipts.py -q
"""
import asyncio
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests

BASE_URL = os.environ.get("TEST_API_BASE", os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TAG = f"ing_{uuid.uuid4().hex[:8]}"


def _backend_up() -> bool:
    try:
        requests.get(f"{API}/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    rids = [uid("res") for _ in range(3)]
    for i, r in enumerate(rids):
        await db.residents.insert_one({"resident_id": r, "name": f"{TAG} R{i}", "room": f"{TAG}-{i}",
                                       "participation_level": "full", "created_at": now_utc().isoformat()})
    wid, freq = f"{TAG}_w", 9000 + (uuid.uuid4().int % 1000) / 7.0
    await db.wearables.insert_one({"wearable_id": wid, "device_label": TAG, "resident_id": rids[0], "status": "active"})
    await db.pendants.insert_one({"pendant_device_id": f"{TAG}_pd", "pendant_id": f"{TAG}_p", "frequency_mhz": freq,
                                  "resident_id": rids[1], "status": "active"})
    await db.zones.insert_one({"zone_id": f"{TAG}_z", "name": f"{TAG} Stairwell", "is_restricted": True, "allowed_levels": []})

    async def alerts(rid):
        return await db.alerts.find({"resident_id": rid}, {"_id": 0}).to_list(20)

    async def creation(aid):
        return await db.receipts.find({"related_object_id": aid, "action_type": "resident_assistance_event"},
                                      {"_id": 0}).to_list(20)
    try:
        # ---- wearable: signals coalesce, severity only rises, button press counts ----
        post = lambda body: requests.post(f"{API}/wearables/event", json={"wearable_id": wid, **body}, timeout=5)
        assert post({"event_type": "inactivity"}).status_code == 200
        with ThreadPoolExecutor(6) as ex:
            rs = list(ex.map(lambda _: post({"event_type": "fall"}), range(6)))
        assert all(r.status_code == 200 for r in rs)
        assert post({"event_type": "press"}).status_code == 200
        assert post({"event_type": "inactivity"}).status_code == 200      # cannot lower severity
        a = await alerts(rids[0])
        assert len(a) == 1, len(a)
        a = a[0]
        assert a["severity"] == "emergency" and a["press_count"] == 1 and len(a["presses"]) == 1
        assert len(a["signals"]) == 8 and all(s["source"] == "wearable" and s["device_id"] == wid for s in a["signals"])
        assert any(e.get("field") == "severity" and e.get("to") == "emergency" for e in a.get("event_log", []))
        rc = await creation(a["alert_id"])
        assert len(rc) == 1 and rc[0]["authority"] == "resident_ingress:wearable"
        assert rc[0]["actor_id"] == f"wearable:{wid}" and rc[0]["after_state"]["semantic_class"] == "device_signal"

        # ---- pendant scaffold: two presses in 60 s -> one event, press_count 2, emergency ----
        pp = lambda: requests.post(f"{API}/pendants/event", json={"frequency_mhz": freq, "event_type": "press"}, timeout=5)
        assert pp().status_code == 200 and pp().status_code == 200
        b = await alerts(rids[1])
        assert len(b) == 1 and b[0]["press_count"] == 2 and b[0]["severity"] == "emergency", b
        assert len(await creation(b[0]["alert_id"])) == 1

        # ---- geofence: breaches coalesce as signals, zone kept, no press ----
        loc = lambda z: requests.post(f"{API}/locations", json={"resident_id": rids[2], "zone": z, "source": "mock"}, timeout=5)
        assert loc("Lobby").status_code == 200 and loc(f"{TAG} Stairwell").status_code == 200
        assert loc("Lobby").status_code == 200 and loc(f"{TAG} Stairwell").status_code == 200
        c = await alerts(rids[2])
        assert len(c) == 1 and c[0]["press_count"] == 0 and len(c[0]["signals"]) == 2, c
        assert c[0]["zone"] == f"{TAG} Stairwell" and c[0]["triggered_by"] == "geofence"
        rc = await creation(c[0]["alert_id"])
        assert len(rc) == 1 and rc[0]["zone"] == f"{TAG} Stairwell"
        # public status stays minimal
        pub = requests.get(f"{API}/alerts/public/{c[0]['alert_id']}/status", timeout=5).json()
        assert set(pub) == {"alert_id", "status", "severity"}
    finally:
        ids = [x["alert_id"] for r in rids for x in await alerts(r)]
        await db.alerts.delete_many({"resident_id": {"$in": rids}})
        await db.receipts.delete_many({"related_object_id": {"$in": ids}})
        await db.residents.delete_many({"resident_id": {"$in": rids}})
        await db.wearables.delete_many({"wearable_id": wid})
        await db.pendants.delete_many({"pendant_id": f"{TAG}_p"})
        await db.zones.delete_many({"zone_id": f"{TAG}_z"})
        await db.locations.delete_many({"resident_id": {"$in": rids}})


@pytest.mark.skipif(not _backend_up(), reason="backend not running")
def test_device_ingress_uses_the_canonical_event():
    asyncio.run(_run())
