"""RQ-037: a kiosk pinned to a test resident keeps Room 214's real room key
(devices, lease) but never writes to the room's registered resident.

Real HTTP against the gate backend; synthetic rooms/residents only (the real
Room 214 / Helen Torres are never touched). The setup script is exercised on a
synthetic kiosk through its own functions.
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


def _up():
    try:
        requests.get(f"{API}/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


def _dbrun(fn):
    from motor.motor_asyncio import AsyncIOMotorClient

    async def _go():
        c = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            return await fn(c[os.environ["DB_NAME"]])
        finally:
            c.close()
    return asyncio.run(_go())


@pytest.fixture(scope="module")
def env():
    if not _up():
        pytest.skip("backend not reachable")
    from routes.auth import _issue_jwt
    tag = uuid.uuid4().hex[:6]
    room = f"T037-{tag}"
    ids = {"helen": f"res_t037h{tag}", "mike": f"res_t037m{tag}", "tag": tag, "room": room}

    async def seed(db):
        toks = {}
        for role in ("owner", "staff"):
            uid = f"user_t037{role}{tag}"
            await db.users.insert_one({"user_id": uid, "email": f"{uid}@t.dev", "name": uid, "role": role,
                                       "created_at": "2026-01-01T00:00:00+00:00"})
            toks[role] = _issue_jwt(uid)
        for rid, name, r in ((ids["helen"], "T037 Helen", room), (ids["mike"], "T037 Michael (home test)", room + "-HOME")):
            await db.residents.insert_one({"resident_id": rid, "name": name, "preferred_name": name.split()[1],
                                           "room": r, "pendant_id": "x", "medical_notes": "secret",
                                           "created_at": "2026-01-01T00:00:00+00:00"})
        return toks

    ids["tok"] = _dbrun(seed)
    yield ids

    async def tear(db):
        await db.users.delete_many({"user_id": {"$regex": f"t037.*{tag}$"}})
        await db.residents.delete_many({"resident_id": {"$in": [ids["helen"], ids["mike"]]}})
        await db.kiosks.delete_many({"room": room})
        for coll in ("staff_tasks", "alerts", "smart_devices", "device_commands", "receipts", "resident_aria_leases"):
            await db[coll].delete_many({"$or": [{"room": room}, {"resident_id": {"$in": [ids["helen"], ids["mike"]]}}]})
    _dbrun(tear)


def _kiosk(env, pin=None):
    r = requests.post(f"{API}/kiosks", json={"name": "k", "room": env["room"], "zone": "z", "resident_id": pin},
                      headers=_h(env["tok"]["owner"]), timeout=5)
    assert r.status_code == 200, r.text
    return r.json()["kiosk_id"]


def _resident_for(kid):
    return requests.get(f"{API}/residents/public/by-kiosk/{kid}", timeout=5).json()["resident"]


def test_pin_resolves_pinned_resident_with_four_fields(env):
    unpinned = _kiosk(env)
    assert _resident_for(unpinned)["resident_id"] == env["helen"]  # room match, unchanged
    pinned = _kiosk(env, env["mike"])
    r = _resident_for(pinned)
    assert r["resident_id"] == env["mike"]
    assert set(r) == {"resident_id", "name", "preferred_name", "room"}
    assert "medical_notes" not in r
    for k in (unpinned, pinned):
        requests.delete(f"{API}/kiosks/{k}", headers=_h(env["tok"]["owner"]), timeout=5)


def test_pin_is_admin_only_and_must_name_a_real_resident(env):
    body = {"name": "k", "room": env["room"] + "x", "zone": "z", "resident_id": env["mike"]}
    assert requests.post(f"{API}/kiosks", json=body, headers=_h(env["tok"]["staff"]), timeout=5).status_code == 403
    assert requests.post(f"{API}/kiosks", json=body, timeout=5).status_code in (401, 403)
    body["resident_id"] = "res_nope"
    assert requests.post(f"{API}/kiosks", json=body, headers=_h(env["tok"]["owner"]), timeout=5).status_code == 404
    kid = _kiosk(env)
    assert requests.patch(f"{API}/kiosks/{kid}", json={"resident_id": "res_nope"},
                          headers=_h(env["tok"]["owner"]), timeout=5).status_code == 404
    requests.delete(f"{API}/kiosks/{kid}", headers=_h(env["tok"]["owner"]), timeout=5)


def test_pinned_kiosk_writes_go_to_pinned_resident_not_room_resident(env):
    kid = _kiosk(env, env["mike"])
    owner = _h(env["tok"]["owner"])
    # Alert from the kiosk button with only kiosk_id: identity is the pin.
    a = requests.post(f"{API}/alerts", json={"kiosk_id": kid, "severity": "assist"}, timeout=5)
    assert a.status_code == 200, a.text
    assert a.json()["resident_id"] == env["mike"]
    # A resident-scoped request for the pinned resident does not touch Helen.
    t = requests.post(f"{API}/tasks/resident-request", json={
        "category": "maintenance", "resident_id": env["mike"], "room": env["room"],
        "summary": "T037 lamp flickers", "resident_words": "the lamp flickers"}, timeout=5)
    assert t.status_code == 200, t.text

    async def counts(db):
        return {
            "helen_tasks": await db.staff_tasks.count_documents({"resident_id": env["helen"]}),
            "helen_alerts": await db.alerts.count_documents({"resident_id": env["helen"]}),
            "mike_tasks": await db.staff_tasks.count_documents({"resident_id": env["mike"]}),
            "mike_alerts": await db.alerts.count_documents({"resident_id": env["mike"]}),
        }
    c = _dbrun(counts)
    assert c["helen_tasks"] == 0 and c["helen_alerts"] == 0
    assert c["mike_tasks"] == 1 and c["mike_alerts"] >= 1
    # Request/status scoping by resident: Helen sees none of it.
    st = requests.get(f"{API}/tasks/resident-request/open", params={"resident_id": env["helen"]}, timeout=5).json()
    assert not st.get("requests") and not st.get("found")
    # Active-emergency on the pinned kiosk shows the pinned resident's alert only.
    ae = requests.get(f"{API}/kiosks/{kid}/active-emergency", timeout=5).json()["alert"]
    assert ae is None or ae["resident_id"] == env["mike"]
    requests.delete(f"{API}/kiosks/{kid}", headers=owner, timeout=5)


def test_other_residents_alert_does_not_launch_pinned_kiosk(env):
    kid = _kiosk(env, env["mike"])

    async def seed(db):
        await db.alerts.insert_one({
            "alert_id": f"alert_t037{env['tag']}", "resident_id": env["helen"], "room": env["room"],
            "auto_voice": True, "status": "active", "activation_consumed_at": None,
            "created_at": "2026-10-08T00:00:00+00:00"})
    _dbrun(seed)
    assert requests.get(f"{API}/kiosks/{kid}/active-emergency", timeout=5).json()["alert"] is None
    unpinned = _kiosk(env)
    got = requests.get(f"{API}/kiosks/{unpinned}/active-emergency", timeout=5).json()["alert"]
    assert got and got["resident_id"] == env["helen"]  # unpinned behaviour unchanged
    for k in (kid, unpinned):
        requests.delete(f"{API}/kiosks/{k}", headers=_h(env["tok"]["owner"]), timeout=5)


def test_room_keyed_device_commands_and_lease_still_use_the_room(env):
    kid = _kiosk(env, env["mike"])
    d = requests.post(f"{API}/devices", json={"label": "T037 lamp", "kind": "light", "protocol": "mock",
                                              "room": env["room"], "capabilities": ["power"]},
                      headers=_h(env["tok"]["owner"]), timeout=5)
    assert d.status_code == 200, d.text
    r = requests.post(f"{API}/devices/public/room/{env['room']}/command",
                      json={"action": "power", "value": "on", "kind": "light"}, timeout=5)
    assert r.status_code == 200, r.text
    lease = requests.post(f"{API}/realtime/room/{env['room']}/activate",
                          json={"resident_id": env["mike"], "kiosk_id": kid, "session_id": "s037"}, timeout=5)
    assert lease.status_code == 200, lease.text
    st = requests.get(f"{API}/realtime/room/{env['room']}/status", timeout=5).json()
    assert st["lease"]["resident_id"] == env["mike"]
    requests.post(f"{API}/realtime/room/{env['room']}/release", json={"session_id": "s037"}, timeout=5)
    requests.delete(f"{API}/kiosks/{kid}", headers=_h(env["tok"]["owner"]), timeout=5)


def test_setup_script_pins_is_idempotent_and_revert_restores(env):
    import importlib
    scr = None
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
    scr = importlib.import_module("setup_home_test_identity")
    assert "home test" in scr.TEST_NAME.lower()  # clearly a test identity
    scr.TEST_NAME = f"T037 Script Michael {env['tag']}"
    kid = _kiosk(env)

    async def go(db):
        before = await db.residents.count_documents({})
        helen_before = await db.residents.find_one({"resident_id": env["helen"]}, {"_id": 0})
        first = await scr.setup(db, kid)
        second = await scr.setup(db, kid)
        after = await db.residents.count_documents({})
        k = await db.kiosks.find_one({"kiosk_id": kid}, {"_id": 0})
        mike = await db.residents.find_one({"resident_id": first["resident_id"]}, {"_id": 0})
        rev = await scr.revert(db, kid)
        k2 = await db.kiosks.find_one({"kiosk_id": kid}, {"_id": 0})
        helen_after = await db.residents.find_one({"resident_id": env["helen"]}, {"_id": 0})
        rcpts = await db.receipts.count_documents({"related_object_id": kid})
        await db.residents.delete_many({"resident_id": first["resident_id"]})
        return first, second, before, after, k, mike, rev, k2, helen_before, helen_after, rcpts

    first, second, before, after, k, mike, rev, k2, hb, ha, rcpts = _dbrun(go)
    assert first["resident_created"] is True and second["resident_created"] is False
    assert after == before + 1 and k["resident_id"] == first["resident_id"]
    assert mike["room"] == "214-HOME" and mike.get("synthetic") is not True
    assert rev["unpinned_from"] == first["resident_id"] and not k2.get("resident_id")
    assert hb == ha  # the room's registered resident was never edited
    assert rcpts == 2  # one pin receipt, one unpin receipt; the idempotent rerun wrote none
    requests.delete(f"{API}/kiosks/{kid}", headers=_h(env["tok"]["owner"]), timeout=5)
