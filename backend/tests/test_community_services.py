"""Pilot 1 community-services acceptance (Lane D): dining/menu,
activities/schedule and housekeeping, driven through the real HTTP API as
kitchen, activities and housekeeping staff would.

Menu: paste intake -> draft (not public) -> publish -> Aria/room screen
read -> correction email replaces the old meal -> a replaced item cannot be
re-published -> in-place corrections. Schedule: pasted calendar -> drafts ->
publish batch -> clock order, staff-only notes hidden -> corrected calendar
replaces earlier pasted rows but never staff-typed ones. Housekeeping:
resident request -> housekeeping queue only -> acknowledge / claim / start /
note / complete -> history receipts -> resident status.

Seeds TAG-prefixed users, far-future dates and rooms; deletes them after.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_community_services.py -q
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

TAG = f"csv_{uuid.uuid4().hex[:8]}"
ROOM = f"{TAG}-214"
# Far-future dates no seed or other test uses.
D1, D2 = "2031-03-03", "2031-03-04"


def _backend_up() -> bool:
    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=5)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _public_menu(date, meal=None):
    params = {"date": date, **({"meal_period": meal} if meal else {})}
    return requests.get(f"{API}/menu/public/today", params=params, timeout=5).json()


def _public_schedule(date):
    return requests.get(f"{API}/schedule/public/today", params={"date": date}, timeout=5).json()


def _menu_checks(K, HK):
    # Only Kitchen/Administration staff (or admins) may change the menu.
    r = requests.post(f"{API}/menu/ingest/paste", headers=HK, json={"service_date": D1, "raw_text": "Lunch: x"}, timeout=5)
    assert r.status_code == 403, r.text

    body = f"Breakfast: {TAG} oatmeal, toast\nLunch: {TAG} tomato soup\nDinner: {TAG} baked chicken, green beans"
    r = requests.post(f"{API}/menu/ingest/paste", headers=K, json={"service_date": D1, "raw_text": body}, timeout=5)
    assert r.status_code == 200, r.text
    up = r.json()
    assert up["source"] == "staff_paste" and up["parse_status"] == "parsed" and len(up["item_ids"]) == 5
    assert _public_menu(D1) == [], "a draft menu must never be public"

    r = requests.post(f"{API}/menu/uploads/{up['upload_id']}/approve", headers=K, timeout=5)
    assert r.status_code == 200 and r.json()["status"] == "approved"
    dinner = _public_menu(D1, "dinner")
    assert {i["item_name"] for i in dinner} == {f"{TAG} baked chicken", "green beans"}

    # Correction email for dinner only: the old dinner is replaced, other
    # meals stay. Flagged needs_review because breakfast/lunch are absent.
    r = requests.post(f"{API}/menu/ingest/paste", headers=K, json={"service_date": D1, "raw_text": f"Dinner: {TAG} meatloaf"}, timeout=5)
    fix = r.json()
    assert fix["parse_status"] == "parsed"
    assert requests.post(f"{API}/menu/uploads/{fix['upload_id']}/approve", headers=K, timeout=5).status_code == 200
    assert [i["item_name"] for i in _public_menu(D1, "dinner")] == [f"{TAG} meatloaf"]
    assert len(_public_menu(D1, "breakfast")) == 2 and len(_public_menu(D1, "lunch")) == 1

    staff_view = requests.get(f"{API}/menu", headers=K, params={"date": D1}, timeout=5).json()
    old = next(i for i in staff_view if i["item_name"] == f"{TAG} baked chicken")
    assert old["status"] == "superseded"
    r = requests.post(f"{API}/menu/{old['menu_id']}/approve", headers=K, timeout=5)
    assert r.status_code == 409, "a replaced dish must not be re-published next to the correction"
    assert requests.patch(f"{API}/menu/{old['menu_id']}", headers=K, json={"item_name": "x"}, timeout=5).status_code == 409

    # In-place correction published in one action stays live, renamed.
    soup = next(i for i in staff_view if i["item_name"] == f"{TAG} tomato soup")
    r = requests.patch(f"{API}/menu/{soup['menu_id']}", headers=K,
                       json={"item_name": f"{TAG} minestrone", "publish": True}, timeout=5)
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert [i["item_name"] for i in _public_menu(D1, "lunch")] == [f"{TAG} minestrone"]

    # A correction saved as a draft takes the item off the residents' menu.
    r = requests.patch(f"{API}/menu/{soup['menu_id']}", headers=K, json={"description": "made with beef stock"}, timeout=5)
    assert r.json()["status"] == "draft"
    assert _public_menu(D1, "lunch") == []


def _schedule_checks(ACT, HK):
    cal = (f"Tuesday {D1}:\n10:00 AM {TAG} Chair Yoga - Sunroom\n9:30 AM {TAG} Hymn Sing\n"
           f"1:00 PM {TAG} Bingo - Main activity room\n5:00 PM {TAG} Two aides overnight [staff_hours]\n\n"
           f"Wednesday {D2}:\n2:00 PM {TAG} Movie Afternoon\n")
    assert requests.post(f"{API}/schedule/ingest/paste", headers=HK, json={"raw_text": cal}, timeout=5).status_code == 403
    r = requests.post(f"{API}/schedule/ingest/paste", headers=ACT, json={"raw_text": cal}, timeout=5)
    assert r.status_code == 200, r.text
    batch = r.json()
    assert batch["status"] == "draft" and batch["created_count"] == 5 and not batch["skipped_lines"]
    assert _public_schedule(D1) == [], "a pasted calendar must not be public before review"
    drafts = requests.get(f"{API}/schedule/drafts", headers=ACT, timeout=5).json()
    assert sum(1 for d in drafts if d.get("ingest_id") == batch["ingest_id"]) == 5

    r = requests.post(f"{API}/schedule/batches/{batch['ingest_id']}/publish", headers=ACT, timeout=5)
    assert r.status_code == 200 and r.json()["published_count"] == 5
    day1 = _public_schedule(D1)
    assert [i["title"] for i in day1] == [f"{TAG} Hymn Sing", f"{TAG} Chair Yoga", f"{TAG} Bingo"], day1
    assert all(i["category"] != "staff_hours" for i in day1)
    staff_day1 = requests.get(f"{API}/schedule", headers=ACT, params={"date": D1}, timeout=5).json()
    assert any(i["category"] == "staff_hours" for i in staff_day1), "staff notes stay on the staff view"

    # A staff-typed entry is live immediately.
    r = requests.post(f"{API}/schedule", headers=ACT, json={"date": D1, "time_label": "3:00 PM", "title": f"{TAG} Ice cream social"}, timeout=5)
    assert r.status_code == 200 and r.json()["status"] == "published"
    typed_id = r.json()["schedule_id"]

    # Corrected calendar for day 1 replaces the earlier pasted day-1 rows,
    # leaves day 2 and the staff-typed entry alone.
    r = requests.post(f"{API}/schedule/ingest/paste", headers=ACT,
                      json={"raw_text": f"{D1}:\n11:00 AM {TAG} Chair Yoga - moved to Chapel"}, timeout=5)
    fix = r.json()
    r = requests.post(f"{API}/schedule/batches/{fix['ingest_id']}/publish", headers=ACT, timeout=5)
    assert r.json()["replaced_count"] == 4
    day1 = _public_schedule(D1)
    assert [(i["time_label"], i["title"]) for i in day1] == [
        ("11:00 AM", f"{TAG} Chair Yoga"), ("3:00 PM", f"{TAG} Ice cream social")], day1
    assert day1[0]["description"] == "moved to Chapel"
    assert [i["title"] for i in _public_schedule(D2)] == [f"{TAG} Movie Afternoon"]

    replaced = next(i for i in requests.get(f"{API}/schedule", headers=ACT, params={"date": D1}, timeout=5).json()
                    if i["title"] == f"{TAG} Bingo")
    assert replaced["status"] == "superseded"
    assert requests.post(f"{API}/schedule/{replaced['schedule_id']}/publish", headers=ACT, timeout=5).status_code == 409

    # In-place correction of a published entry is visible on the next read.
    requests.patch(f"{API}/schedule/{typed_id}", headers=ACT, json={"time_label": "3:30 PM"}, timeout=5).raise_for_status()
    assert any(i["time_label"] == "3:30 PM" for i in _public_schedule(D1))


def _housekeeping_checks(HK, K, hk_user_id):
    rr = requests.post(f"{API}/tasks/resident-request", json={
        "category": "housekeeping", "room": ROOM, "resident_words": "Could someone bring fresh towels?",
        "summary": "Fresh towels", "source": "aria_voice",
    }, timeout=5)
    assert rr.status_code == 200, rr.text
    tid = rr.json()["task_id"]

    assert tid in {t["task_id"] for t in requests.get(f"{API}/tasks", headers=HK, timeout=5).json()}
    assert tid not in {t["task_id"] for t in requests.get(f"{API}/tasks", headers=K, timeout=5).json()}

    status = requests.get(f"{API}/tasks/resident-request/status", params={"room": ROOM}, timeout=5).json()
    assert status["found"] and "no one has picked it up yet" in status["spoken"]

    assert requests.post(f"{API}/tasks/{tid}/acknowledge", headers=HK, timeout=5).status_code == 200
    r = requests.post(f"{API}/tasks/{tid}/assign", headers=HK, json={"assigned_to": hk_user_id}, timeout=5)
    assert r.status_code == 200 and r.json()["assigned_to"] == hk_user_id
    assert requests.post(f"{API}/tasks/{tid}/start", headers=HK, timeout=5).json()["status"] == "in_progress"
    assert requests.patch(f"{API}/tasks/{tid}", headers=HK, json={"notes": "On my way with towels"}, timeout=5).status_code == 200
    status = requests.get(f"{API}/tasks/resident-request/status", params={"room": ROOM}, timeout=5).json()
    assert "is working on it now" in status["spoken"] and "On my way with towels" in status["spoken"]

    r = requests.post(f"{API}/tasks/{tid}/complete", headers=HK, json={"notes": "Delivered 4 towels"}, timeout=5)
    assert r.status_code == 200 and r.json()["status"] == "completed"
    detail = requests.get(f"{API}/tasks/{tid}/detail", headers=HK, timeout=5).json()
    assert detail["task"]["completed_at"] and detail["task"]["acknowledged_at"] and detail["task"]["started_at"]
    assert detail["receipts"], "a housekeeping request must leave a receipt trail"
    assert requests.get(f"{API}/tasks/resident-request/status", params={"room": ROOM}, timeout=5).json()["found"] is False
    hist = requests.get(f"{API}/tasks/resident-request/history", params={"room": ROOM}, timeout=5).json()
    assert hist["found"] and len(hist["requests"]) == 1


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    pw = "csv-pw-12345678"
    users = {
        "kitchen": {"role": "staff", "department": "kitchen"},
        "activities": {"role": "staff", "department": "activities"},
        "hk": {"role": "staff", "department": "housekeeping"},
    }
    for k, u in users.items():
        u["user_id"] = uid("user")
        u["email"] = f"{TAG}_{k}@example.com"
        await db.users.insert_one({
            "user_id": u["user_id"], "email": u["email"], "name": f"{TAG} {k}",
            "role": u["role"], "department": u["department"], "auth_provider": "jwt",
            "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
            "created_at": now_utc().isoformat(),
        })
    ids = [u["user_id"] for u in users.values()]
    try:
        K = _login(users["kitchen"]["email"], pw)
        ACT = _login(users["activities"]["email"], pw)
        HK = _login(users["hk"]["email"], pw)
        _menu_checks(K, HK)
        _schedule_checks(ACT, HK)
        _housekeeping_checks(HK, K, users["hk"]["user_id"])
    finally:
        upload_ids = await db.menu_uploads.distinct("upload_id", {"created_by": {"$in": ids}})
        await db.menu_items.delete_many({"$or": [{"created_by": {"$in": ids}}, {"upload_id": {"$in": upload_ids}}]})
        await db.menu_uploads.delete_many({"upload_id": {"$in": upload_ids}})
        await db.schedule_items.delete_many({"created_by": {"$in": ids}})
        tids = [t["task_id"] for t in await db.staff_tasks.find({"room": ROOM}, {"_id": 0, "task_id": 1}).to_list(50)]
        await db.staff_tasks.delete_many({"room": ROOM})
        if tids:
            await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.receipts.delete_many({"room": ROOM})
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})


def test_community_services():
    if not _backend_up():
        pytest.skip(f"backend not reachable at {BASE_URL}")
    asyncio.run(_run())
