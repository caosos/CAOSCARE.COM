"""GET /tasks/{id}/detail enforces the same visibility as the task list (routes.tasks.staff_visibility_query) plus
the list's own mine_only path (a task assigned to the caller). Denied = the same 404 as a missing task, with no task or
receipt data and nothing mutated. In-process ASGI, scratch DB, local-owner bypass off."""
import asyncio, os, sys, uuid
import httpx, pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test data; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import tasks, task_detail  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402

TAG = f"tdv_{uuid.uuid4().hex[:6]}"
REAL = httpx.AsyncClient
USERS = {"owner": ("owner", None), "admin": ("admin", None), "front": ("front_desk", None),
         "nurse": ("staff", "nursing"), "maint": ("staff", "maintenance"), "nodept": ("staff", None)}
TASKS = {"nurs": ("nursing", None), "maint": ("maintenance", None), "all": ("all_staff", None),
         "assigned": ("maintenance", f"{TAG}_nurse")}   # a maintenance task assigned to the nurse
SECRET = lambda k: f"SECRET-{k}"


def run(c): return asyncio.get_event_loop().run_until_complete(c)


def call(path, who=None, params=None):
    app = FastAPI(); app.include_router(tasks.router, prefix="/api"); app.include_router(task_detail.router, prefix="/api")
    h = {"Authorization": f"Bearer {_issue_jwt(f'{TAG}_{who}')}"} if who else {}

    async def go():
        async with REAL(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(path, headers=h, params=params)
    return run(go())


@pytest.fixture(autouse=True)
def seed(monkeypatch):
    monkeypatch.delenv("CAOSCARE_LOCAL_OWNER_BYPASS", raising=False)
    run(db.users.insert_many([{"user_id": f"{TAG}_{k}", "email": f"{k}@x.t", "name": k, "role": r, "department": d} for k, (r, d) in USERS.items()]))
    run(db.staff_tasks.insert_many([{"task_id": f"{TAG}_{k}", "title": f"T-{k}", "resident_words": SECRET(k), "notes": SECRET(k), "status": "pending",
                                     "visibility_role": v, "assigned_to": a, "created_at": "2026-10-10T10:00:00+00:00"} for k, (v, a) in TASKS.items()]))
    run(db.receipts.insert_many([{"receipt_id": f"{TAG}_r{i}_{k}", "related_object_type": "task", "related_object_id": f"{TAG}_{k}", "action_type": SECRET(k),
                                  "created_at": f"2026-10-10T10:0{i}:00+00:00"} for k in TASKS for i in (1, 2)]))
    yield
    run(db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}}))
    run(db.staff_tasks.delete_many({"task_id": {"$regex": f"^{TAG}"}}))
    run(db.receipts.delete_many({"receipt_id": {"$regex": f"^{TAG}"}}))


def listed(who, **params):
    return {t["task_id"].removeprefix(f"{TAG}_") for t in call("/api/tasks", who, params).json() if t["task_id"].startswith(TAG)}


def allowed(who):
    return {k for k in TASKS if call(f"/api/tasks/{TAG}_{k}/detail", who).status_code == 200}


EXPECT = {"owner": set(TASKS), "admin": set(TASKS), "front": set(TASKS),
          "nurse": {"nurs", "all", "assigned"}, "maint": {"maint", "all", "assigned"}, "nodept": {"all"}}


@pytest.mark.parametrize("who", list(USERS))
def test_detail_matrix_matches_policy(who):
    assert allowed(who) == EXPECT[who]


@pytest.mark.parametrize("who", list(USERS))
def test_detail_is_never_broader_than_list_plus_assigned(who):
    visible_in_list = listed(who) | listed(who, mine_only="true")
    assert allowed(who) == visible_in_list


@pytest.mark.parametrize("who,task", [("nurse", "maint"), ("maint", "nurs"), ("nodept", "nurs"), ("nodept", "maint")])
def test_denied_is_a_plain_404_with_no_task_or_receipt_data_and_no_mutation(who, task):
    tb, rb = run(db.staff_tasks.count_documents({})), run(db.receipts.count_documents({}))
    r = call(f"/api/tasks/{TAG}_{task}/detail", who)
    gone = call(f"/api/tasks/{TAG}_nonexistent/detail", who)
    assert r.status_code == 404 and r.json() == gone.json()
    assert "SECRET" not in r.text and f"T-{task}" not in r.text
    assert (run(db.staff_tasks.count_documents({})), run(db.receipts.count_documents({}))) == (tb, rb)


def test_allowed_detail_keeps_task_and_ordered_receipts():
    r = call(f"/api/tasks/{TAG}_nurs/detail", "nurse").json()
    assert r["task"]["task_id"] == f"{TAG}_nurs"
    assert [x["receipt_id"] for x in r["receipts"]] == [f"{TAG}_r1_nurs", f"{TAG}_r2_nurs"]
    assert call(f"/api/tasks/{TAG}_assigned/detail", "nurse").json()["task"]["assigned_to"] == f"{TAG}_nurse"


def test_anonymous_and_missing():
    assert call(f"/api/tasks/{TAG}_nurs/detail").status_code == 401
    assert call(f"/api/tasks/{TAG}_nonexistent/detail", "owner").status_code == 404
