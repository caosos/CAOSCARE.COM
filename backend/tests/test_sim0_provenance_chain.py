"""SIM-0 / SC-13: one resident request traced from origin through every
step, with no orphan state change and no self-report accepted as evidence.

Workflow: "My sink is leaking" (Aria voice, room claim) -> maintenance tech
claims -> starts -> adds a note -> completes. Proves:
- every step is one receipt; parent links run back to the origin and every
  receipt carries the origin's id as its workflow (correlation) id;
- each receipt names the actor, how its identity is known, and the
  authority it acted under; before/after state chain without gaps;
- every history entry links to an existing receipt and vice versa;
- a housekeeper cannot start/complete a maintenance request (403, nothing
  written); PATCH cannot set status (422, nothing written);
- body fields claiming an actor, a verification result or a simulated
  flag are ignored;
- a legacy request with no recorded origin is refused and the refusal is
  recorded; a repeat ask on it is filed as a new request, not lost;
- an admin acts under an explicit override authority;
- SC-14: start/complete/acknowledge/skip/note on a completed request are
  refused (409), nothing changes, and each refusal is recorded.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_sim0_provenance_chain.py -q
"""
import asyncio
import os
import sys
import uuid

import bcrypt
import pytest
import requests

BASE_URL = os.environ.get("TEST_API_BASE", os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TAG = f"sim0_{uuid.uuid4().hex[:8]}"
PW = "sim0-pw-12345678"


def _backend_up() -> bool:
    try:
        requests.get(f"{API}/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


def _login(email):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": PW}, timeout=5)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _ok(r):
    assert r.status_code == 200, (r.status_code, r.text)
    return r.json()


def _ask(room, words, **extra):
    return _ok(requests.post(f"{API}/tasks/resident-request", json={
        "category": "maintenance", "room": room, "source": "aria_voice",
        "summary": words, "resident_words": words, **extra}, timeout=5))


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    people = {"admin": ("admin", None), "tech": ("staff", "maintenance"), "hk": ("staff", "housekeeping")}
    ids = {}
    for k, (role, dept) in people.items():
        ids[k] = uid("user")
        await db.users.insert_one({
            "user_id": ids[k], "email": f"{TAG}_{k}@example.com", "name": f"{TAG} {k}", "role": role,
            "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
            "password_hash": bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()})

    async def task(tid):
        return await db.staff_tasks.find_one({"task_id": tid}, {"_id": 0})

    async def receipts(tid):
        return await db.receipts.find({"related_object_id": tid}, {"_id": 0}).sort("created_at", 1).to_list(50)

    try:
        H = {k: _login(f"{TAG}_{k}@example.com") for k in people}
        tech = H["tech"]
        room = f"{TAG}-M"

        # ---------- origin: a room claim, identity unverified (D3) ----------
        created = _ask(room, "My sink is leaking", simulated=True, actor="admin", verified=True)
        tid, origin_id = created["task_id"], created["receipt_id"]
        t = await task(tid)
        assert t["simulated"] is False and t.get("simulation_scope") is None   # body flag ignored
        [origin] = await receipts(tid)
        assert origin["receipt_id"] == origin_id == origin["correlation_id"]
        assert origin["parent_receipt_id"] is None
        assert origin["actor_type"] == "real-human" and origin["identity_basis"] == "unverified_room_claim"
        assert origin["authority"] == "public_resident_bus" and origin["channel"] == "aria_voice"
        assert origin["room"] == room and origin["after_state"]["status"] == "pending"
        assert origin["next_state"] == "awaiting_claim"

        # ---------- the canonical workflow ----------
        _ok(requests.post(f"{API}/tasks/{tid}/assign", headers=tech, json={"assigned_to": ids["tech"]}, timeout=5))
        _ok(requests.post(f"{API}/tasks/{tid}/start", headers=tech, timeout=5))
        _ok(requests.patch(f"{API}/tasks/{tid}", headers=tech, json={"notes": "Loose supply line"}, timeout=5))
        # self-report in the body: an actor, a result label, a verification claim
        _ok(requests.post(f"{API}/tasks/{tid}/complete", headers=tech, timeout=5, json={
            "notes": "Tightened fitting, no leak", "actor": ids["admin"], "requested_by": "someone",
            "verified": True, "result_label": "simulated", "authority": "admin_override:owner"}))

        chain = await receipts(tid)
        assert [r["action_type"] for r in chain] == [
            "resident_request_created", "task_assigned", "task_in_progress", "task_note_added", "task_completed"]
        via_api = _ok(requests.get(f"{API}/receipts", headers=H["admin"],
                                   params={"correlation_id": origin_id}, timeout=5))
        assert {r["receipt_id"] for r in via_api} == {r["receipt_id"] for r in chain}
        for prev, r in zip(chain, chain[1:]):
            assert r["parent_receipt_id"] == prev["receipt_id"]              # unbroken back to origin
            assert r["correlation_id"] == origin_id
            assert r["actor_id"] == ids["tech"] and r["requested_by"] == ids["tech"]   # not the body's claim
            assert r["actor_type"] == "real-human" and r["identity_basis"] == "authenticated"
            assert r["actor_department"] == "maintenance" and r["channel"] == "staff_ui"
            assert r["authority"] in ("acts_for:maintenance", "assignee")
            assert r["authority"] != "admin_override:owner"
            assert r["before_state"] == prev["after_state"]                  # no unrecorded change between
            assert r["result_label"] == "verified" and r["simulated"] is False
        assert chain[-1]["after_state"]["status"] == "completed" and chain[-1]["next_state"] == "closed"

        # ---------- no orphan state change: history <-> receipts ----------
        t = await task(tid)
        assert t["status"] == "completed" and t["completed_by"] == ids["tech"]
        logged = {e.get("receipt_id") for e in t["event_log"]}
        assert None not in logged                                            # every entry is receipted
        assert logged == {r["receipt_id"] for r in chain[1:]}                # and every receipt has its entry

        # ---------- SC-14: a completed request is closed; changes are refused and recorded ----------
        closed_before, n_before = await task(tid), len(await receipts(tid))
        for path in ("start", "complete", "acknowledge", "skip"):
            assert requests.post(f"{API}/tasks/{tid}/{path}", headers=tech, timeout=5).status_code == 409
        assert requests.patch(f"{API}/tasks/{tid}", headers=tech, json={"notes": "late note"}, timeout=5).status_code == 409
        assert await task(tid) == closed_before                              # still completed, started_at kept
        refusals = (await receipts(tid))[n_before:]
        assert [r["action_type"] for r in refusals] == [
            "task_start_refused", "task_complete_refused", "task_acknowledge_refused",
            "task_skip_refused", "task_note_refused"]
        assert all(r["status"] == "failed" and "already completed" in r["failure_reason"] for r in refusals)
        # refusals are evidence, not part of the chain: the workflow is unchanged
        via_api = _ok(requests.get(f"{API}/receipts", headers=H["admin"],
                                   params={"correlation_id": origin_id}, timeout=5))
        assert {r["receipt_id"] for r in via_api} == {r["receipt_id"] for r in chain}

        # ---------- unauthorized: housekeeper on a maintenance request ----------
        other = _ask(f"{TAG}-H", "The bathroom fan is rattling")["task_id"]
        before_t, before_r = await task(other), await receipts(other)
        for path in ("start", "complete", "acknowledge", "skip"):
            assert requests.post(f"{API}/tasks/{other}/{path}", headers=H["hk"], timeout=5).status_code == 403
        assert requests.patch(f"{API}/tasks/{other}", headers=H["hk"], json={"notes": "x"}, timeout=5).status_code == 403
        assert await task(other) == before_t and await receipts(other) == before_r

        # ---------- PATCH cannot set status / assignment / self-reported fields ----------
        _ok(requests.post(f"{API}/tasks/{other}/assign", headers=tech, json={"assigned_to": ids["tech"]}, timeout=5))
        before_t, before_r = await task(other), await receipts(other)
        for body in ({"status": "completed"}, {"assigned_to": ids["admin"]}, {"verified": True},
                     {"notes": "x", "status": "completed"}):
            assert requests.patch(f"{API}/tasks/{other}", headers=tech, json=body, timeout=5).status_code == 422
        assert await task(other) == before_t and await receipts(other) == before_r

        # ---------- admin acts under an explicit override ----------
        _ok(requests.post(f"{API}/tasks/{other}/skip", headers=H["admin"], json={"notes": "duplicate"}, timeout=5))
        last = (await receipts(other))[-1]
        assert last["action_type"] == "task_cancelled" and last["authority"] == "admin_override:admin"

        # ---------- legacy request (no recorded origin): refused + recorded (D5) ----------
        lroom = f"{TAG}-L"
        lt = uid("task")
        await db.staff_tasks.insert_one({
            "task_id": lt, "title": "sink in the kitchenette leaking", "category": "maintenance", "status": "pending",
            "visibility_role": "maintenance", "room": lroom, "priority": "normal", "source": "aria_voice",
            "notes": "", "re_request_count": 0, "created_at": now_utc().isoformat()})
        before_t = await task(lt)
        r = requests.post(f"{API}/tasks/{lt}/start", headers=tech, timeout=5)
        assert r.status_code == 409
        assert await task(lt) == before_t                                    # nothing changed
        [refusal] = await receipts(lt)
        assert refusal["action_type"] == "task_start_refused" and refusal["status"] == "failed"
        assert refusal["actor_id"] == ids["tech"] and "legacy" in refusal["failure_reason"]

        # a repeat ask on that legacy request is filed as a new request, not lost
        again = _ask(lroom, "The sink in the kitchenette is leaking")
        assert again["duplicate"] is False and again["task_id"] != lt
        assert (await task(lt))["re_request_count"] == 0
        assert [x["action_type"] for x in await receipts(lt)] == ["task_start_refused", "task_re_request_refused"]
    finally:
        tids = [x["task_id"] for x in await db.staff_tasks.find(
            {"room": {"$regex": f"^{TAG}"}}, {"_id": 0, "task_id": 1}).to_list(50)]
        await db.staff_tasks.delete_many({"room": {"$regex": f"^{TAG}"}})
        if tids:
            await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})


def test_sim0_provenance_chain():
    if not _backend_up():
        pytest.skip(f"backend not reachable at {BASE_URL}")
    asyncio.run(_run())
