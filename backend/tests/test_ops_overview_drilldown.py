"""#153 slice 2: the Operations overview's department Open and Done today
numbers equal the records they open (GET /ops/metrics/records), with no
4,000-row cap, live-only, and the overview says plainly when its other
columns cannot be trusted. Runs the route functions in-process against the
gate's test database, like test_ops_metrics.py."""
import asyncio
import inspect
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from deps import db, require_admin
from routes import ops_metrics as om
from routes import ops_overview as ov

TAG = f"odt_{uuid.uuid4().hex[:8]}"
OWNER = {"role": "owner", "user_id": f"{TAG}_owner"}
CARE, KITCHEN = f"{TAG}_nursing", f"{TAG}_kitchen"
RUN = f"simrun:{TAG}"
LIVE_DONE, KITCHEN_DONE = 4050, 7          # more live rows than the overview's old 4,000-row list


def run(coro):
    return asyncio.run(coro)


def _task(tid, dept, status, **kw):
    now = datetime.now(timezone.utc).isoformat()
    doc = {"task_id": f"{TAG}_{tid}", "title": f"{TAG} {tid}", "status": status, "visibility_role": dept,
           "source": "aria_voice", "created_at": now}
    if status == "completed":
        doc["completed_at"] = now
    return {**doc, **kw}


@pytest.fixture(scope="module")
def seeded():
    docs = [
        *[_task(f"done{i}", CARE, "completed", assigned_to=f"user_{TAG}", assigned_name="Real Nurse")
          for i in range(LIVE_DONE)],
        _task("waiting", CARE, "pending"),
        _task("working", CARE, "in_progress", assigned_to=f"user_{TAG}", assigned_name="Real Nurse"),
        *[_task(f"k{i}", KITCHEN, "completed") for i in range(KITCHEN_DONE)],
        # simulated rows in the same departments: never in the live overview numbers
        _task("sim_done", CARE, "completed", source="simulator", simulated=True, simulation_run_id=RUN,
              assigned_to="sim:staff:nursing:care_aide:01"),
        _task("sim_open", CARE, "in_progress", source="simulator", simulated=True, simulation_run_id=RUN,
              assigned_to="sim:staff:nursing:care_aide:02"),
    ]

    async def setup():
        await db.departments.insert_many([{"slug": CARE, "label": f"{TAG} Nursing", "active": True},
                                          {"slug": KITCHEN, "label": f"{TAG} Kitchen", "active": True}])
        # an old updated_at keeps this run from becoming any other test's "latest run"
        await db.sim_runs.insert_one({"run_id": RUN, "state": "STOPPED", "updated_at": "2000-01-01"})
        await db.staff_tasks.insert_many(docs)
    run(setup())
    yield

    async def teardown():
        await db.staff_tasks.delete_many({"task_id": {"$regex": f"^{TAG}_"}})
        await db.departments.delete_many({"slug": {"$in": [CARE, KITCHEN]}})
        await db.sim_runs.delete_many({"run_id": RUN})
    run(teardown())


def _overview():
    return run(ov.operations_overview(attention_limit=1, user=OWNER))


def _row(overview, slug):
    return next(d for d in overview["departments"] if d["slug"] == slug)


def _records(metric, dept, page=1, page_size=200, user=OWNER, **kw):
    scope = _overview_scope()
    return run(om.metric_records(metric=metric, world="live", department=dept, origin=kw.get("origin"),
                                 date=scope["date"], run_id=None, sim_day=None, q=kw.get("q"), page=page,
                                 page_size=page_size, user=user))


_SCOPE = {}


def _overview_scope():
    if not _SCOPE:
        _SCOPE.update(_overview()["department_scope"])
    return _SCOPE


def _all_ids(metric, dept):
    seen, page = [], 1
    while True:
        rec = _records(metric, dept, page=page)
        seen += [r["task_id"] for r in rec["rows"]]
        if len(rec["rows"]) < 200:
            return rec["total"], seen
        page += 1


def test_nursing_done_today_equals_every_record_it_opens_past_4000(seeded):
    o = _overview()
    shown = _row(o, CARE)["completed_today"]
    total, ids = _all_ids("done", CARE)
    assert shown == total == len(ids) == len(set(ids)) == LIVE_DONE
    assert f"{TAG}_sim_done" not in ids                     # simulated work is not "today" in the live overview


def test_nursing_open_equals_its_records_and_excludes_simulated(seeded):
    shown = _row(_overview(), CARE)["open"]
    total, ids = _all_ids("open", CARE)
    assert shown == total == 2 and set(ids) == {f"{TAG}_waiting", f"{TAG}_working"}


def test_kitchen_done_today_equals_its_records(seeded):
    shown = _row(_overview(), KITCHEN)["completed_today"]
    total, ids = _all_ids("done", KITCHEN)
    assert shown == total == len(ids) == KITCHEN_DONE
    assert all(i.startswith(f"{TAG}_k") for i in ids)


def test_overview_discloses_scope_and_marks_list_columns_unverified(seeded):
    s = _overview()["department_scope"]
    assert s["world"] == "live" and s["run"] is None and s["timezone"] and s["date"]
    assert s["exact_columns"] == ["open", "completed_today"]
    assert s["facility"]["basis"]                            # says which facility, and that tasks carry no facility_id
    assert s["simulated_excluded"] >= 2
    # more than 4,000 task rows exist, and simulated rows are mixed in: the list-based columns say so
    assert s["unverified_columns"] == ["overdue", "unassigned", "in_progress"]
    assert "first 4,000" in s["unverified_reason"] and "simulated" in s["unverified_reason"]


def test_records_disclose_facility_timezone_status_and_actor(seeded):
    rec = _records("open", CARE)
    assert rec["status_filter"] == ["pending", "in_progress"] and rec["timezone"] and rec["facility"]["basis"]
    kinds = {r["task_id"]: r["actor_kind"] for r in rec["rows"]}
    assert kinds == {f"{TAG}_waiting": "none", f"{TAG}_working": "real"}
    sim = run(om.metric_records(metric="open", world="simulated", department=CARE, origin=None, date=None,
                                run_id=RUN, sim_day=None, q=None, page=1, page_size=50, user=OWNER))
    assert [(r["task_id"], r["actor_kind"], r["world"]) for r in sim["rows"]] == \
        [(f"{TAG}_sim_open", "simulated", "simulated")]


def test_filters_narrow_rows_but_keep_the_tile_total(seeded):
    rec = _records("done", CARE, q=f"{TAG} done4049", page_size=50)
    assert rec["total"] == LIVE_DONE and rec["matched"] == 1 and rec["rows"][0]["task_id"] == f"{TAG}_done4049"
    assert _records("done", CARE, origin="staff_generated")["total"] == 0   # every seeded row is a resident request


def test_permissions(seeded):
    nurse = {"role": "staff", "department": CARE}
    assert _records("open", CARE, user=nurse)["total"] == 2
    with pytest.raises(HTTPException) as e:
        _records("done", KITCHEN, user=nurse)
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as e:
        _records("done", CARE, user={"role": "resident"})
    assert e.value.status_code == 403
    # the overview itself is owner/admin only
    assert inspect.signature(ov.operations_overview).parameters["user"].default.dependency is require_admin
