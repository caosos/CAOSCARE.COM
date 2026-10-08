"""RQ-014: every menu / activities content change writes one provenance-linked
receipt (actor, authority, before/after, ingest id); reads write none.

Drives the real HTTP API as kitchen and activities staff. Far-future dates
and TAG-named users; cleaned up afterwards.

    TEST_API_BASE=http://127.0.0.1:8087 pytest tests/test_content_receipts.py -q
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

TAG = f"cr_{uuid.uuid4().hex[:8]}"
D = "2032-04-05"


def _up():
    try:
        requests.get(f"{API}/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _up(), reason="needs a running backend (TEST_API_BASE)")


def _user(dept, role="staff"):
    from models import uid
    email, pw = f"{TAG}.{dept}@example.com", "pw-" + uuid.uuid4().hex[:8]
    doc = {"user_id": uid("user"), "email": email, "name": f"{TAG} {dept}", "role": role, "department": dept,
           "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
           "created_at": "2026-01-01T00:00:00+00:00", "auth_provider": "jwt"}
    return doc, email, pw


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=5)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_content_changes_write_receipts():
    # Own Motor client + loop (not deps.db), so this file never binds the
    # shared client to a loop that other test files then find closed.
    from motor.motor_asyncio import AsyncIOMotorClient
    loop = asyncio.new_event_loop()
    db = AsyncIOMotorClient(os.environ["MONGO_URL"], io_loop=loop)[os.environ["DB_NAME"]]
    kitchen, k_email, k_pw = _user("kitchen")
    acts, a_email, a_pw = _user("activities")
    loop.run_until_complete(db.users.insert_many([dict(kitchen), dict(acts)]))
    try:
        K, A = _login(k_email, k_pw), _login(a_email, a_pw)
        like = {"action_type": {"$regex": "_content_"}}

        def n():
            return loop.run_until_complete(db.receipts.count_documents(like))

        def rc(t, i):
            return loop.run_until_complete(
                db.receipts.find({"related_object_type": t, "related_object_id": i}, {"_id": 0}).sort("created_at", 1).to_list(50))

        # Reads write nothing.
        before = n()
        requests.get(f"{API}/menu", params={"date": D}, headers=K, timeout=5)
        requests.get(f"{API}/menu/public/today", params={"date": D}, timeout=5)
        requests.get(f"{API}/menu/uploads", headers=K, timeout=5)
        requests.get(f"{API}/schedule", params={"date": D}, headers=A, timeout=5)
        requests.get(f"{API}/schedule/drafts", headers=A, timeout=5)
        requests.get(f"{API}/schedule/public/today", params={"date": D}, timeout=5)
        assert n() == before

        # Menu: paste -> one batch receipt; the upload's items are drafts.
        r = requests.post(f"{API}/menu/ingest/paste", headers=K, timeout=5,
                          json={"service_date": D, "raw_text": f"Lunch: {TAG} soup\nDinner: {TAG} stew"})
        up = r.json()
        got = rc("menu_upload", up["upload_id"])
        assert len(got) == 1 and got[0]["action_type"] == "menu_content_uploaded"
        assert got[0]["actor_id"] == kitchen["user_id"] and got[0]["identity_basis"] == "authenticated"
        assert got[0]["authority"] == "acts_for:kitchen" and got[0]["channel"] == "staff_ui"
        assert got[0]["after_state"]["item_count"] == 2 and got[0]["after_state"]["ingest_id"] == up["upload_id"]
        assert got[0]["correlation_id"] == got[0]["receipt_id"]

        # Edit + publish one dish: before/after summary, linked to the upload.
        mid = up["item_ids"][0]
        r = requests.patch(f"{API}/menu/{mid}", headers=K, json={"item_name": f"{TAG} soup v2", "publish": True}, timeout=5)
        assert r.status_code == 200
        e = rc("menu_item", mid)
        assert [x["action_type"] for x in e] == ["menu_content_published"]
        assert e[0]["before_state"]["status"] == "draft" and e[0]["after_state"]["status"] == "approved"
        assert e[0]["after_state"]["item_name"].endswith("soup v2") and e[0]["after_state"]["ingest_id"] == up["upload_id"]

        # Approve the batch -> batch receipt chained to the upload's origin.
        requests.post(f"{API}/menu/uploads/{up['upload_id']}/approve", headers=K, timeout=5)
        chain = rc("menu_upload", up["upload_id"])
        assert [x["action_type"] for x in chain] == ["menu_content_uploaded", "menu_content_published"]
        assert chain[1]["parent_receipt_id"] == chain[0]["receipt_id"] and chain[1]["correlation_id"] == chain[0]["receipt_id"]

        # A second menu for the same meals supersedes the first: one receipt per replaced dish.
        up2 = requests.post(f"{API}/menu/ingest/paste", headers=K, timeout=5,
                            json={"service_date": D, "raw_text": f"Lunch: {TAG} chili"}).json()
        requests.post(f"{API}/menu/uploads/{up2['upload_id']}/approve", headers=K, timeout=5)
        old_lunch = [i for i in up["item_ids"] if i != up["item_ids"][1]][0]
        sup = rc("menu_item", old_lunch)
        assert sup[-1]["action_type"] == "menu_content_superseded" and sup[-1]["after_state"]["status"] == "superseded"
        assert sup[-1]["after_state"]["ingest_id"] == up2["upload_id"]

        # Manual create + delete.
        item = requests.post(f"{API}/menu", headers=K, timeout=5,
                             json={"date": D, "meal_period": "breakfast", "item_name": f"{TAG} toast"}).json()
        assert [x["action_type"] for x in rc("menu_item", item["menu_id"])] == ["menu_content_created"]
        assert requests.delete(f"{API}/menu/{item['menu_id']}", headers=K, timeout=5).status_code == 200
        d = rc("menu_item", item["menu_id"])
        assert d[-1]["action_type"] == "menu_content_deleted" and d[-1]["before_state"]["item_name"].endswith("toast")

        # A refused change (wrong department) and a missing item write nothing.
        c0 = n()
        assert requests.post(f"{API}/menu", headers=A, timeout=5,
                             json={"date": D, "meal_period": "lunch", "item_name": "x"}).status_code == 403
        assert requests.delete(f"{API}/menu/nope", headers=K, timeout=5).status_code == 404
        assert n() == c0

        # Schedule: paste -> batch receipt (draft); publish batch; edit; delete.
        cal = f"Monday {D}:\n10:00 AM {TAG} Yoga - Sunroom\n2:00 PM {TAG} Bingo [activity]\n"
        r = requests.post(f"{API}/schedule/ingest/paste", headers=A, json={"raw_text": cal}, timeout=5).json()
        ing = r["ingest_id"]
        b = rc("schedule_batch", ing)
        assert len(b) == 1 and b[0]["action_type"] == "schedule_content_uploaded" and b[0]["actor_id"] == acts["user_id"]
        assert b[0]["after_state"]["item_count"] == 2 and b[0]["after_state"]["ingest_id"] == ing
        pub = requests.post(f"{API}/schedule/batches/{ing}/publish", headers=A, timeout=5)
        assert pub.status_code == 200
        b = rc("schedule_batch", ing)
        assert [x["action_type"] for x in b] == ["schedule_content_uploaded", "schedule_content_published"]
        assert b[1]["after_state"]["published_count"] == 2 and b[1]["parent_receipt_id"] == b[0]["receipt_id"]

        sid = r["created"][0]["schedule_id"]
        requests.patch(f"{API}/schedule/{sid}", headers=A, json={"title": f"{TAG} Yoga 2"}, timeout=5)
        ed = rc("schedule_item", sid)[-1]
        assert ed["action_type"] == "schedule_content_edited" and ed["after_state"]["title"].endswith("Yoga 2")
        assert ed["before_state"]["title"].endswith("Yoga") and ed["after_state"]["ingest_id"] == ing

        # A newer calendar for the same date supersedes: a receipt per replaced row.
        r2 = requests.post(f"{API}/schedule/ingest/paste", headers=A, timeout=5,
                           json={"raw_text": f"Monday {D}:\n9:00 AM {TAG} Walk\n"}).json()
        requests.post(f"{API}/schedule/batches/{r2['ingest_id']}/publish", headers=A, timeout=5)
        s = rc("schedule_item", sid)[-1]
        assert s["action_type"] == "schedule_content_superseded" and s["after_state"]["ingest_id"] == r2["ingest_id"]

        one = requests.post(f"{API}/schedule", headers=A, timeout=5,
                            json={"date": D, "time_label": "4:00 PM", "title": f"{TAG} Cards"}).json()
        pid = one["schedule_id"]
        requests.delete(f"{API}/schedule/{pid}", headers=A, timeout=5)
        assert [x["action_type"] for x in rc("schedule_item", pid)] == ["schedule_content_created", "schedule_content_deleted"]
    finally:
        loop.run_until_complete(db.users.delete_many({"email": {"$regex": f"^{TAG}"}}))
        loop.run_until_complete(db.menu_items.delete_many({"date": D}))
        loop.run_until_complete(db.menu_uploads.delete_many({"service_date": D}))
        loop.run_until_complete(db.schedule_items.delete_many({"date": D}))
        loop.run_until_complete(db.receipts.delete_many({"action_type": {"$regex": "_content_"}, "actor_id": {"$in": [kitchen['user_id'], acts['user_id']]}}))
        loop.close()
