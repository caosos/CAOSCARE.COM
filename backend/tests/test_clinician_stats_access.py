"""careops-clinician-workspace-001: resident care-pattern stats are for owner/admin and nursing staff;
unresolved splits out open records older than 72 h. In-process, scratch DB, no external calls."""
import asyncio, os, sys, uuid
from datetime import datetime, timedelta, timezone
import httpx, pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test data; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import resident_analytics  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402

TAG = f"csa_{uuid.uuid4().hex[:6]}"
RID = f"{TAG}_res"
def run(c): return asyncio.get_event_loop().run_until_complete(c)


def get(who, path):
    app = FastAPI(); app.include_router(resident_analytics.router, prefix="/api")
    h = {"Authorization": f"Bearer {_issue_jwt(who)}"} if who else {}
    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(f"/api{path}", headers=h)
    return run(go())


@pytest.fixture(autouse=True)
def seed():
    roles = {"admin": ("admin", None), "owner": ("owner", None), "nurse": ("staff", "nursing"),
             "kitchen": ("staff", "kitchen"), "desk": ("front_desk", None)}
    run(db.users.insert_many([{"user_id": f"{TAG}_{k}", "email": f"{k}@x.t", "name": k, "role": r, "department": d, "auth_provider": "jwt"}
                              for k, (r, d) in roles.items()]))
    run(db.residents.insert_one({"resident_id": RID, "name": "Pat", "room": "T1"}))
    now = datetime.now(timezone.utc)
    run(db.alerts.insert_many([
        {"alert_id": f"{TAG}_a1", "resident_id": RID, "status": "active", "created_at": (now - timedelta(hours=2)).isoformat(), "category": "bathroom"},
        {"alert_id": f"{TAG}_a2", "resident_id": RID, "status": "active", "created_at": (now - timedelta(days=10)).isoformat(), "category": "fall"},
        {"alert_id": f"{TAG}_a3", "resident_id": RID, "status": "resolved", "created_at": (now - timedelta(days=12)).isoformat(), "category": "pain"},
    ]))
    yield
    run(db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}})); run(db.residents.delete_many({"resident_id": RID}))
    run(db.alerts.delete_many({"alert_id": {"$regex": f"^{TAG}"}}))


@pytest.mark.parametrize("who,code", [("admin", 200), ("owner", 200), ("nurse", 200), ("kitchen", 403), ("desk", 403), (None, 401)])
def test_stats_access_matrix(who, code):
    assert get(f"{TAG}_{who}" if who else None, f"/residents/{RID}/stats?days=30").status_code == code


def test_unresolved_splits_out_older_open_records():
    cur = get(f"{TAG}_nurse", f"/residents/{RID}/stats?days=30").json()["current_window"]
    assert cur["total_calls"] == 3 and cur["unresolved"] == 2 and cur["unresolved_older"] == 1
