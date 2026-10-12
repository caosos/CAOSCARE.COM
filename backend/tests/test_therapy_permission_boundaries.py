"""careops-therapy-permission-boundaries-001: who may create / read / plan /
work a Therapy request, and what a resident (or Aria) can see of it.

The boundary the product supports: a Therapy request is OPERATIONAL (when,
with whom, where, status). There is no clinical store - no diagnosis, chart or
therapy-note field - and an unknown field is refused. Staff notes are an
operational update channel that the resident sees and Aria reads aloud.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_therapy_permission_boundaries.py -q
"""
import asyncio
import os
import sys
import uuid
from datetime import date, timedelta

import bcrypt
import pytest
import requests

BASE_URL = os.environ.get("TEST_API_BASE", os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TAG = f"tpb_{uuid.uuid4().hex[:8]}"

# The resident-safe projection (routes/resident_requests._resident_safe_view):
# anything outside this set reaching a resident or Aria is a leak.
RESIDENT_KEYS = {
    "task_id", "category", "what_for", "items", "status", "is_open", "acknowledged",
    "assigned_to_name", "completed_by_name", "scheduled_date", "scheduled_time_label",
    "provider_name", "discipline", "location", "latest_update", "latest_update_at",
    "re_request_count", "times_asked", "created_at", "created", "acknowledged_at",
    "started_at", "completed_at", "last_re_requested_at", "lifecycle", "opened_age", "spoken",
}
INTERNAL_KEYS = {"assigned_to", "acknowledged_by", "completed_by", "source", "visibility_role",
                 "event_log", "receipt_id", "requested_by", "needs_review", "escalation_reason"}


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


def _code(r):
    return r.status_code


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    pw = "tpb-pw-12345678"
    people = {"admin": ("admin", None), "fd": ("front_desk", None), "pt": ("staff", "therapy"),
              "nurse": ("staff", "nursing"), "hk": ("staff", "housekeeping")}
    ids = {}
    for k, (role, dept) in people.items():
        ids[k] = uid("user")
        await db.users.insert_one({
            "user_id": ids[k], "email": f"{TAG}_{k}@example.com", "name": f"{TAG} {k}", "role": role,
            "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
            "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
        })
    if not await db.departments.find_one({"slug": "therapy"}):
        await db.departments.insert_one({"department_id": uid("dept"), "slug": "therapy", "label": "Therapy",
                                         "active": True, "created_at": now_utc().isoformat(), "_tag": TAG})
    room = f"{TAG}-R"
    rid = uid("res")
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident", "preferred_name": "Lee",
                                   "room": room, "created_at": now_utc().isoformat()})
    matrix = []
    try:
        H = {k: _login(f"{TAG}_{k}@example.com", pw) for k in people}
        H["anon"] = {}
        day = (date.today() + timedelta(days=2)).isoformat()

        def rec(role, action, got, want):
            matrix.append((role, action, got, want))
            assert got == want, (role, action, got, want)

        # ---- create ----
        # front desk enters it for the resident (canonical resident-request path)
        r = requests.post(f"{API}/tasks/resident-request", headers=H["fd"], json={
            "category": "therapy", "resident_id": rid, "source": "front_desk",
            "summary": "Physical therapy session", "resident_words": "PT on my knee"}, timeout=5)
        rec("front_desk", "create (resident-request)", _code(r), 200)
        t = r.json()["task_id"]
        # the resident asks on the room bus (unverified room claim, no login)
        r = requests.post(f"{API}/tasks/resident-request", json={
            "category": "therapy", "resident_id": rid, "room": room, "source": "kiosk_button",
            "summary": "Help with my exercises"}, timeout=5)
        rec("resident", "create (room bus)", _code(r), 200)
        t_res = r.json()["task_id"]
        # therapy staff create a work order: it is pinned to Therapy
        r = requests.post(f"{API}/tasks", headers=H["pt"], json={
            "title": f"{TAG} gym set-up", "category": "therapy", "visibility_role": "therapy"}, timeout=5)
        rec("therapy", "create (work order)", _code(r), 200)
        assert r.json()["visibility_role"] == "therapy"
        # another department cannot create Therapy work: pinned to its own department
        r = requests.post(f"{API}/tasks", headers=H["nurse"], json={
            "title": f"{TAG} nurse try", "category": "therapy", "visibility_role": "therapy"}, timeout=5)
        rec("nursing", "create therapy work order", _code(r), 200)
        assert r.json()["visibility_role"] == "nursing", "another department's create must not land in Therapy"
        rec("anonymous", "create (work order)", _code(requests.post(f"{API}/tasks", json={"title": "x"}, timeout=5)), 401)
        # a body may not claim the front-desk identity without a login
        r = requests.post(f"{API}/tasks/resident-request", json={
            "category": "therapy", "resident_id": rid, "source": "front_desk", "summary": "x"}, timeout=5)
        rec("anonymous", "create claiming front_desk", _code(r), 401)

        # ---- read ----
        for who, want in (("admin", True), ("fd", True), ("pt", True), ("nurse", False), ("hk", False)):
            seen = {x["task_id"] for x in requests.get(f"{API}/tasks", headers=H[who], timeout=5).json()}
            rec(who, "list includes therapy request", t in seen, want)
            rec(who, "detail", _code(requests.get(f"{API}/tasks/{t}/detail", headers=H[who], timeout=5)), 200 if want else 404)
        rec("anonymous", "list", _code(requests.get(f"{API}/tasks", timeout=5)), 401)
        up = requests.get(f"{API}/tasks/upcoming", params={"department": "therapy"}, headers=H["nurse"], timeout=5)
        assert up.status_code == 200 and t not in {x["task_id"] for x in up.json().get("items", [])}

        # ---- plan / details (PATCH) ----
        plan = {"requested_for_date": day, "requested_for_time_label": "10:00 AM",
                "provider_name": "Tess Ortiz PT", "discipline": "physical therapy", "location": "Therapy gym"}
        for who in ("fd", "nurse", "hk"):
            rec(who, "plan/details", _code(requests.patch(f"{API}/tasks/{t}", headers=H[who], json=plan, timeout=5)), 403)
        rec("anonymous", "plan/details", _code(requests.patch(f"{API}/tasks/{t}", json=plan, timeout=5)), 401)
        rec("therapy", "plan/details", _code(requests.patch(f"{API}/tasks/{t}", headers=H["pt"], json=plan, timeout=5)), 200)
        rec("admin", "edit details", _code(requests.patch(f"{API}/tasks/{t}", headers=H["admin"],
                                                          json={"location": "Therapy gym, 2nd floor"}, timeout=5)), 200)
        # no clinical store: an unknown field is refused, nothing written
        for field in ("diagnosis", "therapy_note", "chart", "clinical_notes"):
            rec("therapy", f"PATCH {field}", _code(requests.patch(f"{API}/tasks/{t}", headers=H["pt"],
                                                                  json={field: "x"}, timeout=5)), 422)
        doc = await db.staff_tasks.find_one({"task_id": t}, {"_id": 0})
        assert not {"diagnosis", "therapy_note", "chart", "clinical_notes"} & set(doc)

        # ---- lifecycle ----
        for who in ("fd", "nurse", "hk"):
            rec(who, "acknowledge", _code(requests.post(f"{API}/tasks/{t}/acknowledge", headers=H[who], timeout=5)), 403)
            rec(who, "start", _code(requests.post(f"{API}/tasks/{t}/start", headers=H[who], timeout=5)), 403)
            rec(who, "note", _code(requests.patch(f"{API}/tasks/{t}", headers=H[who], json={"notes": "x"}, timeout=5)), 403)
            rec(who, "assign self", _code(requests.post(f"{API}/tasks/{t}/assign", headers=H[who],
                                                        json={"user_id": ids[who]}, timeout=5)), 403)
        rec("therapy", "claim", _code(requests.post(f"{API}/tasks/{t}/assign", headers=H["pt"],
                                                    json={"user_id": ids["pt"]}, timeout=5)), 200)
        rec("therapy", "start", _code(requests.post(f"{API}/tasks/{t}/start", headers=H["pt"], timeout=5)), 200)
        note = "Session moved to the gym; bring walking shoes."
        rec("therapy", "note", _code(requests.patch(f"{API}/tasks/{t}", headers=H["pt"], json={"notes": note}, timeout=5)), 200)
        rec("nursing", "complete", _code(requests.post(f"{API}/tasks/{t}/complete", headers=H["nurse"], json={}, timeout=5)), 403)
        rec("therapy", "complete", _code(requests.post(f"{API}/tasks/{t}/complete", headers=H["pt"],
                                                       json={"notes": "Session done."}, timeout=5)), 200)
        rec("therapy", "inspect (owner/admin only)", _code(requests.post(f"{API}/tasks/{t}/inspect", headers=H["pt"],
                                                                         json={"result": "pass"}, timeout=5)), 403)
        rec("nursing", "reopen", _code(requests.post(f"{API}/tasks/{t}/reopen", headers=H["nurse"],
                                                     json={"reason": "x"}, timeout=5)), 403)
        rec("admin", "reopen", _code(requests.post(f"{API}/tasks/{t}/reopen", headers=H["admin"],
                                                   json={"reason": "Rescheduled by the family"}, timeout=5)), 200)
        rec("anonymous", "cancel", _code(requests.post(f"{API}/tasks/{t}/skip", json={"notes": "x"}, timeout=5)), 401)
        rec("therapy", "cancel", _code(requests.post(f"{API}/tasks/{t_res}/skip", headers=H["pt"],
                                                     json={"notes": "Resident declined today"}, timeout=5)), 200)

        # ---- resident / Aria: allow-list only ----
        mine = requests.get(f"{API}/tasks/resident-request/mine", params={"resident_id": rid}, timeout=5)
        assert mine.status_code == 200
        rows = mine.json() if isinstance(mine.json(), list) else mine.json().get("requests", [])
        assert rows, "the resident must see their own therapy requests"
        for row in rows:
            assert set(row) <= RESIDENT_KEYS, set(row) - RESIDENT_KEYS
            assert not set(row) & INTERNAL_KEYS
        row = next(x for x in rows if x["task_id"] == t)
        assert row["provider_name"] == "Tess Ortiz PT" and row["location"] == "Therapy gym, 2nd floor"
        # staff notes ARE resident-visible: the latest note is shown and spoken (the boundary staff must know)
        assert row["latest_update"] == "Reopened: Rescheduled by the family" or row["latest_update"]
        status = requests.get(f"{API}/tasks/resident-request/status",
                              params={"resident_id": rid, "category": "therapy"}, timeout=5).json()
        assert set(status) - {"found", "scope", "request"} <= RESIDENT_KEYS | {"found", "scope"}
        req = status.get("request") or status
        assert not set(req) & INTERNAL_KEYS
        # a staff-only work order never reaches the resident
        assert all(x["what_for"] != f"{TAG} gym set-up" for x in rows)
        # another resident's room sees nothing of this one
        other = requests.get(f"{API}/tasks/resident-request/mine", params={"room": f"{TAG}-OTHER"}, timeout=5)
        assert not [x for x in (other.json() if isinstance(other.json(), list) else other.json().get("requests", []))
                    if x["task_id"] in (t, t_res)]
        return matrix
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.residents.delete_many({"resident_id": rid})
        await db.departments.delete_many({"_tag": TAG})
        await db.staff_tasks.delete_many({"$or": [{"resident_id": rid}, {"title": {"$regex": f"^{TAG}"}}]})


@pytest.mark.skipif(not _backend_up(), reason="backend not running")
def test_therapy_permission_matrix():
    matrix = asyncio.run(_run())
    assert len(matrix) >= 40


async def _run_internal_reasons():
    """A "can't complete" reason and a supervisor review note are internal
    (supervisor channel). They must reach staff (badge, history) but never the
    resident's screen or Aria's spoken status."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    tag = f"{TAG}i"
    pw = "tpb-pw-12345678"
    ids = {}
    for k, role, dept in (("pt", "staff", "therapy"), ("admin", "admin", None), ("fd", "front_desk", None)):
        ids[k] = uid("user")
        await db.users.insert_one({
            "user_id": ids[k], "email": f"{tag}_{k}@example.com", "name": f"{tag} {k}", "role": role,
            "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
            "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
        })
    if not await db.departments.find_one({"slug": "therapy"}):
        await db.departments.insert_one({"department_id": uid("dept"), "slug": "therapy", "label": "Therapy",
                                         "active": True, "created_at": now_utc().isoformat(), "_tag": tag})
    rid = uid("res")
    await db.residents.insert_one({"resident_id": rid, "name": f"{tag} Resident", "preferred_name": "Lee",
                                   "room": f"{tag}-R", "created_at": now_utc().isoformat()})
    try:
        H = {k: _login(f"{tag}_{k}@example.com", pw) for k in ids}
        t = requests.post(f"{API}/tasks/resident-request", headers=H["fd"], json={
            "category": "therapy", "resident_id": rid, "source": "front_desk",
            "summary": "Physical therapy session"}, timeout=5).json()["task_id"]
        assert requests.post(f"{API}/tasks/{t}/assign", headers=H["pt"], json={"user_id": ids["pt"]}, timeout=5).ok
        assert requests.post(f"{API}/tasks/{t}/start", headers=H["pt"], timeout=5).ok
        public = "Session moved to the gym."
        assert requests.patch(f"{API}/tasks/{t}", headers=H["pt"], json={"notes": public}, timeout=5).ok
        reason = "INTERNAL: resident became agitated, needs a two-person assist"
        r = requests.post(f"{API}/tasks/{t}/escalate", headers=H["pt"], json={"reason": reason}, timeout=5)
        assert r.status_code == 200, r.text

        def resident_texts():
            mine = requests.get(f"{API}/tasks/resident-request/mine", params={"resident_id": rid}, timeout=5).json()
            rows = mine if isinstance(mine, list) else mine.get("requests", [])
            st = requests.get(f"{API}/tasks/resident-request/status",
                              params={"resident_id": rid, "category": "therapy"}, timeout=5).json()
            return repr(rows) + repr(st)

        seen = resident_texts()
        assert "INTERNAL" not in seen, "the can't-complete reason reached the resident"
        assert public in seen, "the operational note stays the resident's latest update"
        # staff still have it: the badge field and the history
        detail = requests.get(f"{API}/tasks/{t}/detail", headers=H["admin"], timeout=5).json()
        task = detail.get("task", detail)
        assert task["escalation_reason"] == reason
        assert any(e.get("field") == "escalated" and e.get("text") == reason for e in task["event_log"])

        decided = "INTERNAL: review - schedule with two staff"
        r = requests.post(f"{API}/tasks/{t}/review", headers=H["admin"], json={"reason": decided}, timeout=5)
        assert r.status_code == 200, r.text
        seen = resident_texts()
        assert "INTERNAL" not in seen, "the supervisor review note reached the resident"
        detail = requests.get(f"{API}/tasks/{t}/detail", headers=H["admin"], timeout=5).json()
        task = detail.get("task", detail)
        assert task["review_note"] == decided
        assert any(e.get("field") == "reviewed" and e.get("text") == decided for e in task["event_log"])
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{tag}_"}})
        await db.residents.delete_many({"resident_id": rid})
        await db.departments.delete_many({"_tag": tag})
        await db.staff_tasks.delete_many({"resident_id": rid})


@pytest.mark.skipif(not _backend_up(), reason="backend not running")
def test_internal_exception_reasons_stay_internal():
    asyncio.run(_run_internal_reasons())
