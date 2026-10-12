"""careops-alerts-policy-editor-001: the escalation policy (EscalationRule,
edited at Admin -> Escalation via PUT /escalation/rule) is the one alert
policy store, and routes/escalation_tick.run_tick is its one runtime reader.

An owner/admin edit is validated, receipted with provenance (actor, authority,
before/after, parent = previous edit) and linked from the stored rule; it
changes what the existing tick does. Invalid edits and other roles are
refused and change nothing. A facility without a rule keeps the safe
defaults. Uses its own synthetic facility id; nothing else is touched.

    TEST_API_BASE=http://127.0.0.1:8131 pytest tests/test_alert_policy_editor.py -q
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
TAG = f"pol_{uuid.uuid4().hex[:8]}"
FAC = f"{TAG}_fac"
OTHER_FAC = f"{TAG}_nofac"   # never given a rule: must fall back to defaults


def _backend_up() -> bool:
    try:
        requests.get(f"{API}/health", timeout=3).raise_for_status()
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
    pw = "pol-pw-12345678"
    people = {"owner": ("owner", None), "admin": ("admin", None), "fd": ("front_desk", None),
              "nurse": ("staff", "nursing")}
    ids = {}
    for k, (role, dept) in people.items():
        ids[k] = uid("user")
        await db.users.insert_one({
            "user_id": ids[k], "email": f"{TAG}_{k}@example.com", "name": f"{TAG} {k}", "role": role,
            "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
            "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
        })
    now = datetime.now(timezone.utc)

    async def alert(name, fac, age_s):
        aid = f"{TAG}_{name}"
        await db.alerts.insert_one({"alert_id": aid, "facility_id": fac, "room": f"{TAG}-R", "severity": "assist",
                                    "status": "active", "escalation_level": 0, "event_log": [],
                                    "created_at": (now - timedelta(seconds=age_s)).isoformat()})
        return aid

    async def level(aid):
        return ((await db.alerts.find_one({"alert_id": aid}, {"_id": 0})) or {}).get("escalation_level")

    async def edits():
        return await db.receipts.find({"related_object_type": "escalation_rule", "related_object_id": FAC},
                                      {"_id": 0}).sort("created_at", 1).to_list(20)

    try:
        H = {k: _login(f"{TAG}_{k}@example.com", pw) for k in people}
        H["anon"] = {}
        good = {"facility_id": FAC, "level_2_seconds": 20, "level_3_seconds": 40, "enabled": True}

        # ---- defaults: a facility with no rule reads (and runs on) the safe defaults ----
        r = requests.get(f"{API}/escalation/rule", params={"facility_id": FAC}, headers=H["admin"], timeout=5)
        assert r.status_code == 200 and (r.json()["level_2_seconds"], r.json()["level_3_seconds"]) == (90, 150)

        # ---- unauthorized roles: refused, nothing stored, no receipt ----
        for who, want in (("anon", 401), ("nurse", 403), ("fd", 403)):
            assert requests.get(f"{API}/escalation/rule", headers=H[who], timeout=5).status_code == want, who
            assert requests.put(f"{API}/escalation/rule", json=good, headers=H[who], timeout=5).status_code == want, who
            assert requests.post(f"{API}/escalation/tick", headers=H[who], timeout=5).status_code == want, who
        assert await db.escalation_rules.find_one({"facility_id": FAC}) is None
        assert await edits() == []

        # ---- invalid edits: refused with a readable reason, nothing stored ----
        bad = [
            {**good, "level_3_seconds": 20},            # level 3 not after level 2
            {**good, "level_3_seconds": 10},            # level 3 before level 2
            {**good, "level_2_seconds": 0},             # zero
            {**good, "level_2_seconds": -5},            # negative
            {**good, "level_2_seconds": "soon"},        # not a number
            {**good, "nursing_unclaimed_seconds": 0},
            {**good, "level_3_seconds": 10 ** 9},       # absurd (> 1 day)
        ]
        for body in bad:
            r = requests.put(f"{API}/escalation/rule", json=body, headers=H["admin"], timeout=5)
            assert r.status_code == 422, (body, r.status_code, r.text)
        assert await db.escalation_rules.find_one({"facility_id": FAC}) is None
        assert await edits() == []

        # ---- an admin edit: stored, receipted with provenance, linked from the rule ----
        r = requests.put(f"{API}/escalation/rule", json=good, headers=H["admin"], timeout=5)
        assert r.status_code == 200, r.text
        rs = await edits()
        assert len(rs) == 1, rs
        e1 = rs[0]
        assert e1["action_type"] == "escalation_rule_changed"
        assert e1["actor_id"] == ids["admin"] and e1["actor_type"] == "real-human"
        assert e1["authority"] == "policy_editor:admin"
        assert e1["before_state"]["level_2_seconds"] == 90 and e1["before_state"]["source"] == "defaults"
        assert e1["after_state"]["level_2_seconds"] == 20 and e1["after_state"]["level_3_seconds"] == 40
        assert not e1.get("parent_receipt_id")
        stored = await db.escalation_rules.find_one({"facility_id": FAC}, {"_id": 0})
        assert stored["receipt_id"] == e1["receipt_id"] and stored["updated_by"] == ids["admin"]
        assert r.json()["receipt_id"] == e1["receipt_id"]

        # ---- runtime effect through the existing tick ----
        a_fac = await alert("fac", FAC, 30)          # 30 s: past the edited 20 s, short of the 90 s default
        a_def = await alert("def", OTHER_FAC, 30)    # same age, no rule -> defaults -> untouched
        r = requests.post(f"{API}/escalation/tick", headers=H["admin"], timeout=10)
        assert r.status_code == 200, r.text
        assert await level(a_fac) == 2
        assert await level(a_def) == 0
        esc = await db.receipts.find_one({"related_object_id": a_fac, "action_type": "alert_escalated"}, {"_id": 0})
        assert esc["authority"] == f"escalation_rule:{FAC}"
        assert esc["after_state"]["thresholds"] == {"level_2_seconds": 20, "level_3_seconds": 40}

        # ---- a second edit (owner) chains to the first; disabling stops the tick for that facility ----
        r = requests.put(f"{API}/escalation/rule", json={**good, "enabled": False}, headers=H["owner"], timeout=5)
        assert r.status_code == 200, r.text
        rs = await edits()
        assert len(rs) == 2 and rs[0] == e1, "an earlier edit receipt is never rewritten"
        e2 = rs[1]
        assert e2["authority"] == "policy_editor:owner" and e2["parent_receipt_id"] == e1["receipt_id"]
        assert e2["before_state"]["enabled"] is True and e2["after_state"]["enabled"] is False
        await db.alerts.update_one({"alert_id": a_fac}, {"$set": {"created_at": (now - timedelta(seconds=60)).isoformat()}})
        requests.post(f"{API}/escalation/tick", headers=H["owner"], timeout=10)
        assert await level(a_fac) == 2, "a disabled policy must not escalate further"
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.escalation_rules.delete_many({"facility_id": {"$in": [FAC, OTHER_FAC]}})
        await db.alerts.delete_many({"alert_id": {"$regex": f"^{TAG}_"}})
        await db.receipts.delete_many({"$or": [{"related_object_id": {"$regex": f"^{TAG}_"}},
                                               {"related_object_id": FAC}]})


def test_alert_policy_edit_is_validated_receipted_and_drives_the_tick():
    if os.environ.get("DB_NAME") in ("caoscare", "", None):
        pytest.skip("writes synthetic users/rules; point DB_NAME at a scratch database")
    if not _backend_up():
        pytest.skip(f"backend not reachable at {API}")
    asyncio.new_event_loop().run_until_complete(_run())
