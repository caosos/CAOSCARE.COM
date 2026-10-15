"""Explainable operations metrics (issue #153): origin split, live vs
simulated, wall date vs simulated day, tile total == drill-down rows (incl.
more than the old 4,000-row cap), department scoping. Runs the route
functions in-process against the gate's test database."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from deps import db
from routes import ops_metrics as om
from routes.task_origin import kind_of

TAG = f"om_{uuid.uuid4().hex[:8]}"
OWNER = {"role": "owner", "user_id": f"{TAG}_owner"}
DEPT, OTHER = f"{TAG}_care", f"{TAG}_kitchen"
RUN = f"simrun:{TAG}"
DAY = "2026-10-14"


def _task(i, **kw):
    base = {"task_id": f"{TAG}_{i}", "title": f"{TAG} task {i}", "status": "completed",
            "visibility_role": DEPT, "created_at": "2026-10-14T15:00:00+00:00",
            "completed_at": "2026-10-14T16:00:00+00:00"}
    return {**base, **kw}


def _sim(i, day, **kw):
    return _task(i, source="simulator", simulated=True, simulation_run_id=RUN,
                 conversation_session_id=f"simulator:event:day-{day:03d}:resident-001:morning_room_check", **kw)


@pytest.fixture(scope="module")
def seeded():
    late = (datetime(2026, 10, 15, 4, 30, tzinfo=timezone.utc)).isoformat()   # 23:30 Chicago, still the 14th
    next_day = (datetime(2026, 10, 15, 6, 0, tzinfo=timezone.utc)).isoformat()  # 01:00 Chicago on the 15th
    docs = [
        _task("voice", source="aria_voice", completed_at=late),
        _task("kiosk", source="kiosk_button"),
        _task("staff", source="staff"),
        _task("tmpl", source="system", template_id="tpl_1"),
        _task("legacy"),                                                     # no source: unknown origin
        _task("tomorrow", source="aria_voice", completed_at=next_day),
        _task("waiting", source="aria_voice", status="pending", completed_at=None),
        _task("other", source="aria_voice", visibility_role=OTHER),
        *[_sim(f"s{i}", 3) for i in range(4100)],
        _sim("s_day4", 4),
        _sim("s_open", 3, status="in_progress", completed_at=None),
    ]

    async def setup():
        await db.departments.insert_many([{"slug": DEPT, "label": f"{TAG} Care", "active": True},
                                          {"slug": OTHER, "label": f"{TAG} Kitchen", "active": True}])
        await db.sim_runs.insert_one({"run_id": RUN, "state": "PAUSED", "sim_minute": 3 * 1440 + 600,
                                      "last_event_id": "day-003:resident-001:x", "updated_at": "2099-01-01"})
        await db.staff_tasks.insert_many(docs)
    asyncio.run(setup())
    yield
    async def teardown():
        await db.staff_tasks.delete_many({"task_id": {"$regex": f"^{TAG}_"}})
        await db.departments.delete_many({"slug": {"$in": [DEPT, OTHER]}})
        await db.sim_runs.delete_many({"run_id": RUN})
    asyncio.run(teardown())


def _dept(result, slug):
    return next(d for d in result["departments"] if d["slug"] == slug)["metrics"]


def run(coro):
    return asyncio.run(coro)


def test_live_counts_split_by_origin_on_the_facility_date(seeded):
    r = run(om.metrics(world="live", date=DAY, run_id=None, sim_day=None, user=OWNER))
    done = _dept(r, DEPT)["done"]
    # voice (late evening still the 14th in Chicago) + kiosk + staff + template + legacy; not tomorrow, not simulated
    assert done["total"] == 5
    assert done["by_origin"] == {"scheduled_routine": 1, "resident_request": 2, "staff_generated": 1, "unknown": 1}
    assert _dept(r, DEPT)["waiting"]["total"] == 1
    assert r["period"] == {"kind": "wall_date", "date": DAY, "timezone": r["period"]["timezone"],
                           "label": f"{DAY} ({r['period']['timezone']})"}


def test_simulated_day_counts_are_run_scoped_and_reconcile_past_4000(seeded):
    r = run(om.metrics(world="simulated", date=None, run_id=RUN, sim_day=None, user=OWNER))
    assert r["period"]["sim_day"] == 3 and r["run"]["executed_through_day"] == 4
    done = _dept(r, DEPT)["done"]
    assert done["total"] == 4100 and done["by_origin"]["scheduled_routine"] == 4100
    assert _dept(r, DEPT)["in_progress"]["total"] == 1
    seen, page = set(), 1
    while True:
        rec = run(om.metric_records(metric="done", world="simulated", department=DEPT, origin=None, date=None,
                                    run_id=RUN, sim_day=None, q=None, page=page, page_size=200, user=OWNER))
        assert rec["total"] == 4100
        seen.update(row["task_id"] for row in rec["rows"])
        if len(rec["rows"]) < 200:
            break
        page += 1
    assert len(seen) == 4100
    assert all(row.startswith(f"{TAG}_s") for row in seen)


def test_each_origin_bucket_drills_to_exactly_its_rows(seeded):
    r = run(om.metrics(world="live", date=DAY, run_id=None, sim_day=None, user=OWNER))
    for kind, n in _dept(r, DEPT)["done"]["by_origin"].items():
        rec = run(om.metric_records(metric="done", world="live", department=DEPT, origin=kind, date=DAY,
                                    run_id=None, sim_day=None, q=None, page=1, page_size=200, user=OWNER))
        assert rec["total"] == n == len(rec["rows"])
        assert all(row["origin"] == kind and row["world"] == "live" for row in rec["rows"])
        assert rec["explanation"].startswith("Tasks in")


def test_search_narrows_rows_but_reports_the_tile_total(seeded):
    rec = run(om.metric_records(metric="done", world="live", department=DEPT, origin=None, date=DAY,
                                run_id=None, sim_day=None, q="task kiosk", page=1, page_size=50, user=OWNER))
    assert rec["total"] == 5 and rec["matched"] == 1 and rec["rows"][0]["task_id"] == f"{TAG}_kiosk"


def test_staff_see_only_their_department(seeded):
    staff = {"role": "staff", "department": OTHER}
    r = run(om.metrics(world="live", date=DAY, run_id=None, sim_day=None, user=staff))
    assert {d["slug"] for d in r["departments"]} == {OTHER}
    with pytest.raises(HTTPException) as e:
        run(om.metric_records(metric="done", world="live", department=DEPT, origin=None, date=DAY, run_id=None,
                              sim_day=None, q=None, page=1, page_size=10, user=staff))
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as e:
        run(om.metrics(world="live", date=DAY, run_id=None, sim_day=None, user={"role": "resident"}))
    assert e.value.status_code == 403


def test_python_and_mongo_origin_rules_agree():
    cases = [({"template_id": "t"}, "scheduled_routine"),
             ({"source": "simulator", "conversation_session_id": "simulator:event:day-001:r:x"}, "scheduled_routine"),
             ({"source": "simulator"}, "resident_request"), ({"source": "front_desk"}, "resident_request"),
             ({"source": "aria_admin"}, "staff_generated"), ({}, "unknown"), ({"source": "family"}, "unknown")]
    for doc, kind in cases:
        assert kind_of(doc) == kind


def test_staff_on_duty_box_is_for_administrators_only(seeded):
    from routes import ops_widgets
    for user in ({"role": "staff", "department": OTHER}, {"role": "resident"}):
        with pytest.raises(HTTPException) as e:
            run(ops_widgets.widget("staff_on_duty", world="simulated", date=None, run_id=None, sim_day=None, user=user))
        assert e.value.status_code == 403
