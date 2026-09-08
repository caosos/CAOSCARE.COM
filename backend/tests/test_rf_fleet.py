"""Pendant/RF fleet views (GET /rf/fleet/summary, /rf/fleet/devices).

Read-only over db.rf_devices - proves the Staff Dashboard card can get a
real count for any role, that the summary omits RF engineering detail, and
that the admin drill-down carries the full truth. Does NOT touch RF
decoding / press semantics / ResidentEvent code.

Own Motor client; TAG fixtures deleted after.

    TEST_API_BASE=http://127.0.0.1:8001 pytest tests/test_rf_fleet.py -q
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
import requests

BASE_URL = os.environ.get("TEST_API_BASE", os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TAG = f"rff_{uuid.uuid4().hex[:8]}"


def _backend_up():
    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=5)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    now = datetime.now(timezone.utc)
    pw = "rff-pw-12345678"
    admin_id, staff_id, res_id = uid("user"), uid("user"), uid("res")
    await db.users.insert_many([
        {"user_id": admin_id, "email": f"{TAG}_admin@example.com", "name": f"{TAG} admin", "role": "admin",
         "auth_provider": "jwt", "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
         "created_at": now_utc().isoformat()},
        {"user_id": staff_id, "email": f"{TAG}_staff@example.com", "name": f"{TAG} staff", "role": "staff",
         "department": "nursing", "auth_provider": "jwt",
         "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(), "created_at": now_utc().isoformat()},
    ])
    await db.residents.insert_one({"resident_id": res_id, "name": f"{TAG} Rez", "room": f"{TAG}-1", "pendant_id": "x"})

    fp = {"frequency_hz": 319_500_000, "modulation": "OOK", "bit_pattern_hex": "aabbccdd11", "bit_length": 40, "rssi": -55}
    devices = [
        # active: enabled, seen 10 min ago
        {"rf_device_id": f"{TAG}_d_ok", "label": f"{TAG} bedside", "resident_id": res_id, "room": f"{TAG}-1",
         "fingerprint": fp, "severity": "help", "match_threshold": 0.9, "enabled": True,
         "last_seen_at": (now - timedelta(minutes=10)).isoformat(), "last_rssi": -55, "press_count": 7, "low_battery": False,
         "created_at": now.isoformat()},
        # need attention: low battery
        {"rf_device_id": f"{TAG}_d_bat", "label": f"{TAG} lanyard", "resident_id": None, "room": None,
         "fingerprint": fp, "severity": "help", "match_threshold": 0.9, "enabled": True,
         "last_seen_at": (now - timedelta(hours=1)).isoformat(), "press_count": 2, "low_battery": True,
         "created_at": now.isoformat()},
        # need attention: assigned but not seen in > 24h
        {"rf_device_id": f"{TAG}_d_old", "label": f"{TAG} spare", "resident_id": res_id, "room": f"{TAG}-1",
         "fingerprint": fp, "severity": "help", "match_threshold": 0.9, "enabled": True,
         "last_seen_at": (now - timedelta(days=3)).isoformat(), "press_count": 0, "low_battery": False,
         "created_at": now.isoformat()},
    ]
    await db.rf_devices.insert_many(devices)

    try:
        A = _login(f"{TAG}_admin@example.com", pw)
        S = _login(f"{TAG}_staff@example.com", pw)

        # --- summary: any role, role-safe fields only ---
        for H in (A, S):
            s = requests.get(f"{API}/rf/fleet/summary", headers=H, timeout=10).json()
            mine = [d for d in s["devices"] if d["rf_device_id"].startswith(TAG)]
            assert len(mine) == 3
            assert s["total"] >= 3
            by_id = {d["rf_device_id"]: d for d in mine}
            assert by_id[f"{TAG}_d_ok"]["status"] == "active"
            assert by_id[f"{TAG}_d_bat"]["status"] == "low_battery"
            assert by_id[f"{TAG}_d_old"]["status"] == "offline"
            assert by_id[f"{TAG}_d_ok"]["resident_name"] == f"{TAG} Rez"
            assert by_id[f"{TAG}_d_ok"]["press_count"] == 7
            # a plain-English "why does this need attention" reason accompanies
            # every non-active device; a healthy one has none
            assert by_id[f"{TAG}_d_ok"]["reason"] is None
            assert by_id[f"{TAG}_d_bat"]["reason"] == "Not assigned to a resident"
            assert "No signal in over" in by_id[f"{TAG}_d_old"]["reason"]
            # engineering detail must NOT leak into the role-safe summary
            for d in mine:
                assert "last_rssi" not in d and "match_threshold" not in d and "fingerprint" not in d

        # counts: my 2 non-active devices count as need_attention
        s = requests.get(f"{API}/rf/fleet/summary", headers=S, timeout=10).json()
        assert s["in_service"] + s["need_attention"] == s["total"]

        # --- devices drill-down: admin only, full truth ---
        assert requests.get(f"{API}/rf/fleet/devices", headers=S, timeout=10).status_code == 403
        fd = requests.get(f"{API}/rf/fleet/devices", headers=A, timeout=10).json()
        d_ok = next(d for d in fd["devices"] if d["rf_device_id"] == f"{TAG}_d_ok")
        assert d_ok["frequency_mhz"] == 319.5
        assert d_ok["match_threshold"] == 0.9
        assert d_ok["resident_name"] == f"{TAG} Rez"
        assert "recent_events" in d_ok and isinstance(d_ok["recent_events"], list)
    finally:
        await db.rf_devices.delete_many({"rf_device_id": {"$regex": f"^{TAG}"}})
        await db.residents.delete_many({"resident_id": res_id})
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})


def test_rf_fleet():
    if not _backend_up():
        pytest.skip(f"backend not reachable at {BASE_URL}")
    asyncio.run(_run())
