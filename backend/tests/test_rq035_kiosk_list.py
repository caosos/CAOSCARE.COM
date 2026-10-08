"""RQ-035 (packet P2): GET /api/kiosks is trimmed unless an owner/admin asks.

Real HTTP against the gate backend; synthetic kiosks only. Anonymous and
non-admin callers get kiosk_id + room; owner/admin get full rows. The demo
resolver and the by-kiosk lookup are unchanged.
"""
import asyncio
import os
import sys
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _backend_up():
    try:
        requests.get(f"{API}/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def tokens():
    if not _backend_up():
        pytest.skip("backend not reachable")
    from motor.motor_asyncio import AsyncIOMotorClient
    from routes.auth import _issue_jwt

    async def _go():
        c = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = c[os.environ["DB_NAME"]]
        out = {}
        for role in ("owner", "staff"):
            u = await db.users.find_one({"role": role}, {"_id": 0, "user_id": 1})
            if not u:
                uid = f"user_t035{role}{uuid.uuid4().hex[:6]}"
                await db.users.insert_one({"user_id": uid, "email": f"{uid}@t.dev", "name": uid, "role": role, "created_at": "2026-01-01T00:00:00+00:00"})
                u = {"user_id": uid}
            out[role] = _issue_jwt(u["user_id"])
        c.close()
        return out

    return asyncio.run(_go())


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


def test_anonymous_and_staff_get_only_id_and_room(tokens):
    owner = tokens["owner"]
    room = f"T035-{uuid.uuid4().hex[:5]}"
    kid = requests.post(f"{API}/kiosks", json={"name": "n", "room": room, "zone": "secret-zone", "is_central": True}, headers=_h(owner), timeout=5).json()["kiosk_id"]
    try:
        for hdr in ({}, _h(tokens["staff"])):
            rows = requests.get(f"{API}/kiosks", headers=hdr, timeout=5).json()
            mine = next(k for k in rows if k["kiosk_id"] == kid)
            assert set(mine) == {"kiosk_id", "room"} and mine["room"] == room
            assert all(set(k) == {"kiosk_id", "room"} for k in rows)
        full = next(k for k in requests.get(f"{API}/kiosks", headers=_h(owner), timeout=5).json() if k["kiosk_id"] == kid)
        assert full["zone"] == "secret-zone" and full["is_central"] is True and "created_at" in full
        # a bad token is treated as anonymous, not an error
        assert requests.get(f"{API}/kiosks", headers={"Authorization": "Bearer nope"}, timeout=5).status_code == 200
        # unchanged: by-kiosk lookup and the kiosk's active-emergency poll stay public
        assert requests.get(f"{API}/residents/public/by-kiosk/{kid}", timeout=5).status_code == 200
        assert requests.get(f"{API}/kiosks/{kid}/active-emergency", timeout=5).status_code == 200
    finally:
        requests.delete(f"{API}/kiosks/{kid}", headers=_h(owner), timeout=5)


def test_public_demo_resolver_unchanged(tokens):
    owner = tokens["owner"]
    kid = requests.post(f"{API}/kiosks", json={"name": "d", "room": "T035-demo", "zone": ""}, headers=_h(owner), timeout=5).json()["kiosk_id"]
    try:
        prev = [k["kiosk_id"] for k in requests.get(f"{API}/kiosks", headers=_h(owner), timeout=5).json() if k.get("public_demo")]
        requests.patch(f"{API}/kiosks/{kid}", json={"public_demo": True}, headers=_h(owner), timeout=5)
        r = requests.get(f"{API}/kiosks/public-demo", timeout=5)
        assert r.status_code == 200 and r.json()["kiosk_id"] == kid
        for p in prev:
            requests.patch(f"{API}/kiosks/{p}", json={"public_demo": True}, headers=_h(owner), timeout=5)
    finally:
        requests.delete(f"{API}/kiosks/{kid}", headers=_h(owner), timeout=5)
