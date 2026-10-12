"""careops-menu-paste-001: a whole week can be pasted at once with dated headers; each day becomes its own
draft upload (with its receipt); bad dates refused; a paste without headers still needs service_date.
In-process, scratch DB."""
import asyncio, os, sys, uuid
import httpx, pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test data; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import menu_ingest  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402

TAG = f"mpm_{uuid.uuid4().hex[:6]}"
def run(c): return asyncio.get_event_loop().run_until_complete(c)


def post(who, body):
    app = FastAPI(); app.include_router(menu_ingest.router, prefix="/api")
    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.post("/api/menu/ingest/paste", headers={"Authorization": f"Bearer {_issue_jwt(who)}"}, json=body)
    return run(go())


@pytest.fixture(autouse=True)
def seed():
    run(db.users.insert_many([{"user_id": f"{TAG}_k", "email": "k@x.t", "name": "K", "role": "staff", "department": "kitchen", "auth_provider": "jwt"},
                              {"user_id": f"{TAG}_n", "email": "n@x.t", "name": "N", "role": "staff", "department": "nursing", "auth_provider": "jwt"}]))
    yield
    ups = run(db.menu_uploads.find({"created_by": f"{TAG}_k"}).to_list(100))
    ids = [u["upload_id"] for u in ups] + [i for u in ups for i in u.get("item_ids", [])]
    run(db.receipts.delete_many({"related_object_id": {"$in": ids}})); run(db.menu_items.delete_many({"menu_id": {"$in": ids}}))
    run(db.menu_uploads.delete_many({"created_by": f"{TAG}_k"})); run(db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}}))


def test_week_paste_creates_one_draft_per_day():
    text = (f"Monday 2031-03-03:\nBreakfast: Oatmeal {TAG}\nDinner: Salmon {TAG}\n\n"
            f"Tuesday 2031-03-04:\nLunch: Soup {TAG}\n")
    r = post(f"{TAG}_k", {"raw_text": text})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["multi_day"] is True and body["dates"] == ["2031-03-03", "2031-03-04"]
    ups = {u["service_date"]: u for u in run(db.menu_uploads.find({"created_by": f"{TAG}_k"}).to_list(10))}
    assert set(ups) == {"2031-03-03", "2031-03-04"}
    items = run(db.menu_items.find({"menu_id": {"$in": ups["2031-03-03"]["item_ids"]}}).to_list(10))
    assert {i["meal_period"] for i in items} == {"breakfast", "dinner"} and all(i["status"] == "draft" for i in items)
    for u in ups.values():
        assert run(db.receipts.count_documents({"related_object_id": u["upload_id"], "action_type": "menu_content_uploaded"})) == 1


def test_bad_date_refused_and_single_day_still_needs_service_date():
    assert post(f"{TAG}_k", {"raw_text": "Monday 2031-02-30:\nBreakfast: X"}).status_code == 400
    assert post(f"{TAG}_k", {"raw_text": "Breakfast: X"}).status_code == 400
    r = post(f"{TAG}_k", {"raw_text": f"Breakfast: Eggs {TAG}", "service_date": "2031-03-05"})
    assert r.status_code == 200 and r.json().get("multi_day") is None


def test_nursing_cannot_paste_menus():
    assert post(f"{TAG}_n", {"raw_text": "Monday 2031-03-03:\nBreakfast: X"}).status_code == 403
