"""Menu / activity coverage uses the residents-and-Aria visibility rules: approved menu items; schedule rows
that are not draft/superseded and not staff-only. In-process, scratch DB."""
import asyncio, os, sys, uuid
from datetime import date, timedelta
import httpx, pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test data; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import content_coverage  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402
from routes.realtime_facility import today_facility_date  # noqa: E402

TAG = f"ccv_{uuid.uuid4().hex[:6]}"
def run(c): return asyncio.get_event_loop().run_until_complete(c)


def get(who, path):
    app = FastAPI(); app.include_router(content_coverage.router, prefix="/api")
    h = {"Authorization": f"Bearer {_issue_jwt(who)}"} if who else {}
    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(f"/api{path}", headers=h)
    return run(go())


@pytest.fixture(autouse=True)
def seed():
    run(db.users.insert_one({"user_id": f"{TAG}_k", "email": "k@x.t", "name": "K", "role": "staff", "department": "kitchen", "auth_provider": "jwt"}))
    saved = {c: run(getattr(db, c).find({}).to_list(100000)) for c in ("menu_items", "schedule_items")}   # coverage is collection-wide
    for c in saved: run(getattr(db, c).delete_many({}))
    yield
    run(db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}}))
    for c, docs in saved.items():
        run(getattr(db, c).delete_many({}))
        if docs: run(getattr(db, c).insert_many(docs))


def test_menu_and_schedule_coverage():
    t = date.fromisoformat(today_facility_date()); d = lambda n: (t + timedelta(days=n)).isoformat()
    run(db.menu_items.insert_many([{"menu_id": "m1", "date": d(-9), "status": "approved"}, {"menu_id": "m2", "date": d(1), "status": "draft"},
                                   {"menu_id": "m3", "date": d(2), "status": "superseded"}]))
    m = get(f"{TAG}_k", "/menu/coverage").json()
    assert m == {"today": d(0), "covers_today": False, "last_date": d(-9), "days_ago": 9, "days_ahead": 0}
    run(db.schedule_items.insert_many([{"schedule_id": "s1", "date": d(0), "category": "activity"},          # no status = published
                                       {"schedule_id": "s2", "date": d(3), "category": "staff_hours", "status": "published"},
                                       {"schedule_id": "s3", "date": d(4), "category": "activity", "status": "draft"}]))
    s = get(f"{TAG}_k", "/schedule/coverage").json()
    assert s["covers_today"] is True and s["last_date"] == d(0) and s["days_ahead"] == 1
    assert get(None, "/menu/coverage").status_code == 401
