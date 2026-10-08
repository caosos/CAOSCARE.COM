"""RQ-001 demo data continuity, proven against the canonical request /
lifecycle / receipt services.

Acceptance (one test each, in order):
  1 initial continuity timestamp        7 generated work plausible + deterministic
  2 no elapsed time, no progression     8 real resident data unchanged
  3 elapsed time, deterministic catch-up 9 real facility data unchanged
  4 the same window never twice        10 every change explicitly simulated
  5 completed old work goes to history 11 receipts and provenance exist
  6 unresolved work stays bounded
plus: SC-17 run id on generated work, no provider side effects (SC-16) with a
live-looking email key set for the whole module, startup/sign-in hooks off by
default.

In-process and DB-direct (no backend server). Windows are driven by an
explicit `now`, so the run is reproducible. Refuses the live `caoscare` DB.

    cd backend && MONGO_URL=mongodb://localhost:27017 DB_NAME=caoscare_rq001_test \
      JWT_SECRET=x pytest tests/test_demo_continuity.py -q
"""
import asyncio
import os
import httpx
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("RQ-001 tests write demo records; point DB_NAME at a scratch database",
                allow_module_level=True)

from deps import db  # noqa: E402
from routes import notifications  # noqa: E402
from routes.demo_kiosk import DEMO_ROOM, ensure_demo_room  # noqa: E402
from routes.departments import seed_default_departments  # noqa: E402
from routes.resident_requests import ResidentRequestInput, create_resident_request  # noqa: E402
import demo_continuity as continuity  # noqa: E402

TAG = f"rq001_{uuid.uuid4().hex[:8]}"
REAL_ROOM = f"R-{TAG}"
REAL_RES = f"res_{TAG}"
ANCHOR = datetime(2031, 3, 4, 0, 0, tzinfo=timezone.utc)   # fixed: reproducible windows
CTX = {"provider_calls": 0}
EMAIL_DEPTS = ("maintenance", "housekeeping", "kitchen")


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _demo_tasks(**extra) -> list:
    return await db.staff_tasks.find({"room": DEMO_ROOM, **extra}, {"_id": 0}).to_list(500)


async def _fresh():
    """Scratch-DB reset of RQ-001 state only: the continuity record and
    the demo room's tasks (plus their receipts). Real-room data is kept."""
    ids = [t["task_id"] for t in await _demo_tasks()]
    await db.notifications.delete_many({"task_id": {"$in": ids}})
    await db.staff_tasks.delete_many({"room": DEMO_ROOM})
    await db.receipts.delete_many({"related_object_id": {"$in": ids + [continuity.STATE_KEY]}})
    await db.demo_continuity.delete_many({})


async def _snapshot_real() -> dict:
    """Everything outside the demo room that catch-up must never change."""
    return {
        "residents": await db.residents.find({"room": {"$ne": DEMO_ROOM}}, {"_id": 0}).sort("resident_id", 1).to_list(1000),
        "tasks": await db.staff_tasks.find({"room": {"$ne": DEMO_ROOM}}, {"_id": 0}).sort("task_id", 1).to_list(1000),
        "facilities": await db.facilities.find({}, {"_id": 0}).sort("facility_id", 1).to_list(100),
        "kiosks": await db.kiosks.find({"room": {"$ne": DEMO_ROOM}}, {"_id": 0}).sort("kiosk_id", 1).to_list(1000),
    }


async def _window_receipts() -> list:
    return await db.receipts.find({"related_object_type": "demo_continuity", "action_type": "demo_continuity_window"},
                                  {"_id": 0}).sort("created_at", 1).to_list(1000)


async def _fake_post(self, url, *a, **k):   # a provider call is a test failure
    CTX["provider_calls"] += 1
    raise AssertionError(f"provider called: {url}")


async def _setup():
    # Live-looking provider key for the whole module: SC-16 must keep every
    # simulated notification away from the provider.
    CTX["orig_key"], CTX["orig_post"] = os.environ.get("RESEND_API_KEY"), httpx.AsyncClient.post
    os.environ["RESEND_API_KEY"] = "re_fake_live_key_for_test"
    httpx.AsyncClient.post = _fake_post
    await seed_default_departments()
    for slug in EMAIL_DEPTS:
        await db.departments.update_one({"slug": slug}, {"$set": {"contact_email": f"{slug}@{TAG}.invalid"}})
    await ensure_demo_room()
    demo = await db.residents.find_one({"room": DEMO_ROOM}, {"_id": 0})
    CTX["demo_resident"] = demo["resident_id"]
    # A real (non-synthetic) resident, a real facility record and a real open request.
    await db.residents.update_one({"resident_id": REAL_RES}, {"$setOnInsert": {
        "resident_id": REAL_RES, "name": f"{TAG} Real Resident", "room": REAL_ROOM,
        "created_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    await db.facilities.update_one({"facility_id": f"fac_{TAG}"}, {"$setOnInsert": {
        "facility_id": f"fac_{TAG}", "name": f"{TAG} Facility", "timezone": "America/Chicago"}}, upsert=True)
    await create_resident_request(ResidentRequestInput(
        category="maintenance", resident_id=REAL_RES, room=REAL_ROOM,
        resident_words="The heater in my room is making a noise.", summary="Heater noise"))
    # Control: the real request DID go to the (patched) provider, so the patch
    # detects a real send. Count only what happens after this point.
    CTX["control_calls"], CTX["provider_calls"] = CTX["provider_calls"], 0
    await _fresh()


async def _demo_request(category: str, words: str) -> str:
    made = await create_resident_request(ResidentRequestInput(
        category=category, resident_id=CTX["demo_resident"], room=DEMO_ROOM, resident_words=words, summary=words))
    return made["task_id"]


def setup_module(_):
    run(_setup())
    CTX["real_before"] = run(_snapshot_real())


def teardown_module(_):
    async def _clean():
        await _fresh()
        await db.residents.delete_many({"resident_id": REAL_RES})
        await db.facilities.delete_many({"facility_id": f"fac_{TAG}"})
        real = [t["task_id"] for t in await db.staff_tasks.find({"room": REAL_ROOM}, {"task_id": 1}).to_list(50)]
        await db.staff_tasks.delete_many({"room": REAL_ROOM})
        await db.receipts.delete_many({"related_object_id": {"$in": real}})
        await db.departments.delete_many({"slug": {"$regex": f"^{TAG}"}})
        await db.departments.update_many({"slug": {"$in": list(EMAIL_DEPTS)}}, {"$unset": {"contact_email": ""}})
        await db.sim_runs.delete_many({"scenario": continuity.RUN_SCENARIO})
    run(_clean())
    if CTX["orig_key"] is None:
        os.environ.pop("RESEND_API_KEY", None)
    else:
        os.environ["RESEND_API_KEY"] = CTX["orig_key"]
    httpx.AsyncClient.post = CTX["orig_post"]


def test_1_initial_continuity_timestamp():
    out = run(continuity.catch_up(now=ANCHOR + timedelta(minutes=17)))
    assert out["status"] == "up_to_date" and out["windows"] == 0
    st = run(continuity.get_state())
    assert st["last_simulated_at"] == ANCHOR.isoformat()
    assert st["simulated"] is True and st["windows_processed"] == 0
    origin = run(db.receipts.find_one({"receipt_id": st["origin_receipt_id"]}, {"_id": 0}))
    assert origin["action_type"] == "demo_continuity_started" and origin["simulated"] is True


def test_2_no_elapsed_time_no_progression():
    tid = run(_demo_request("maintenance", "My sink is dripping."))
    before = run(_demo_tasks())
    receipts_before = run(db.receipts.count_documents({}))
    out = run(continuity.catch_up(now=ANCHOR + timedelta(minutes=59)))
    assert out["status"] == "up_to_date" and out["windows"] == 0
    assert run(_demo_tasks()) == before
    assert run(db.receipts.count_documents({})) == receipts_before
    CTX["sink"] = tid


def test_3_elapsed_time_deterministic_catch_up():
    out = run(continuity.catch_up(now=ANCHOR + timedelta(hours=6, minutes=5)))
    assert out["status"] == "caught_up" and out["windows"] == 6
    assert run(continuity.get_state())["last_simulated_at"] == (ANCHOR + timedelta(hours=6)).isoformat()
    # The same starting point and the same elapsed time give the same story.
    def signature(o):
        return [(w["window_start"], (w["generated"] or {}).get("category"),
                 [a["step"] for a in w["advanced"]], len(w["closed_backlog"])) for w in o["detail"]]
    first = signature(out)
    run(_fresh())
    run(continuity.catch_up(now=ANCHOR))
    run(_demo_request("maintenance", "My sink is dripping."))
    again = run(continuity.catch_up(now=ANCHOR + timedelta(hours=6, minutes=5)))
    assert signature(again) == first


def test_4_same_window_never_processed_twice():
    now = ANCHOR + timedelta(hours=9)
    a, b = run(asyncio.gather(continuity.catch_up(now=now), continuity.catch_up(now=now)))
    assert sorted([a["status"], b["status"]]) == ["caught_up", "up_to_date"]
    assert run(continuity.catch_up(now=now))["windows"] == 0
    starts = [r["before_state"]["window_start"] for r in run(_window_receipts())]
    assert len(starts) == len(set(starts)) == 9
    assert run(continuity.get_state())["windows_processed"] == 9


def test_5_completed_old_work_goes_to_history():
    run(_fresh())
    run(continuity.catch_up(now=ANCHOR))
    tid = run(_demo_request("housekeeping", "Could someone bring fresh towels?"))
    run(continuity.catch_up(now=ANCHOR + timedelta(hours=3)))   # acknowledge, start, complete
    t = run(db.staff_tasks.find_one({"task_id": tid}, {"_id": 0}))
    assert t["status"] == "completed" and t["completed_at"]
    assert t["acknowledged_at"] and t["started_at"]
    assert tid not in [x["task_id"] for x in run(continuity._open_tasks())]
    steps = [e for e in t.get("event_log", []) if e.get("field") == "status"]
    assert [e["to"] for e in steps] == ["in_progress", "completed"]


def test_6_unresolved_work_stays_bounded():
    run(_fresh())
    run(continuity.catch_up(now=ANCHOR))
    for i in range(2):   # scratch departments so more categories than the cap can be open
        run(db.departments.update_one({"slug": f"{TAG}_d{i}"}, {"$setOnInsert": {
            "slug": f"{TAG}_d{i}", "label": f"{TAG} Dept {i}", "active": True}}, upsert=True))
    cats = ["maintenance", "housekeeping", "kitchen", "nursing", "transportation", "administration",
            f"{TAG}_d0", f"{TAG}_d1"]
    oldest = [run(_demo_request(c, f"Please check on something ({c}).")) for c in cats]
    assert len(run(continuity._open_tasks())) == 8 > continuity.OPEN_CAP
    out = run(continuity.catch_up(now=ANCHOR + timedelta(hours=1)))
    assert out["detail"][0]["closed_backlog"] == oldest[:2]           # oldest first
    assert out["open"] <= continuity.OPEN_CAP
    for tid in oldest[:2]:
        t = run(db.staff_tasks.find_one({"task_id": tid}, {"_id": 0}))
        assert t["status"] == "skipped" and continuity.BACKLOG_NOTE in (t.get("notes") or "")
    run(continuity.catch_up(now=ANCHOR + timedelta(hours=30)))
    assert len(run(continuity._open_tasks())) <= continuity.OPEN_CAP


def test_7_generated_work_plausible_and_deterministic():
    made = [t for t in run(_demo_tasks()) if t.get("resident_words") in {w for _, w in continuity.CATALOGUE}]
    assert made, "30 simulated hours should have produced at least one new request"
    catalogue = dict((w, c) for c, w in continuity.CATALOGUE)
    run_id = run(continuity.get_state())["simulation_run_id"]
    for t in made:
        assert t["category"] == catalogue[t["resident_words"]]
        assert t["source"] == "simulator" and t["simulation_run_id"] == run_id   # SC-17
        assert t["room"] == DEMO_ROOM and t["resident_id"] == CTX["demo_resident"]
        assert t["simulated"] is True and t["simulation_scope"] == "demo_room"
    # Which windows raise a request is a fixed rule of the window start.
    assert continuity.window_hash(ANCHOR) == continuity.window_hash(ANCHOR)
    assert continuity.window_hash(ANCHOR) != continuity.window_hash(ANCHOR + continuity.WINDOW)


def test_8_and_9_real_resident_and_facility_unchanged():
    after = run(_snapshot_real())
    assert after == CTX["real_before"]


def test_10_every_change_explicitly_simulated():
    for t in run(_demo_tasks()):
        assert t.get("simulated") is True and t.get("simulation_scope") == "demo_room"
        for e in t.get("event_log", []):
            assert e.get("by", "").startswith("sim:") or e.get("field") == "re_request", e
    for r in run(db.receipts.find({"related_object_type": "demo_continuity"}, {"_id": 0}).to_list(1000)):
        assert r["simulated"] is True and r["actor_type"] == "simulated-agent"
        assert r["identity_basis"] == "synthetic"


def test_11_receipts_and_provenance():
    st = run(continuity.get_state())
    windows = run(_window_receipts())
    assert windows
    chain = run(db.receipts.find({"correlation_id": st["origin_receipt_id"]}, {"_id": 0}).to_list(2000))
    ids = {r["receipt_id"] for r in chain}
    for r in windows:
        assert r["correlation_id"] == st["origin_receipt_id"]
        assert r["parent_receipt_id"] in ids
        assert r["result_label"] == "simulated" and r["authority"] == "simulator:demo_continuity"
        assert "open" in r["before_state"] and "open" in r["after_state"]
        for ref in r["provider_refs"]:   # each points at a canonical receipt of simulated demo work
            canon = run(db.receipts.find_one({"receipt_id": ref}, {"_id": 0}))
            assert canon and canon["related_object_type"] == "task"
            task = run(db.staff_tasks.find_one({"task_id": canon["related_object_id"]}, {"_id": 0}))
            assert task["simulated"] is True and task["room"] == DEMO_ROOM
    assert st["last_receipt_id"] == windows[-1]["receipt_id"]


def test_12_simulation_run_registered_and_linked():
    st = run(continuity.get_state())
    run_doc = run(db.sim_runs.find_one({"run_id": st["simulation_run_id"]}, {"_id": 0}))
    assert run_doc["scenario"] == continuity.RUN_SCENARIO and run_doc["state"] == "STOPPED"
    assert run_doc["origin_receipt_id"] == st["origin_receipt_id"]
    assert run(db.sim_runs.find_one({"state": {"$in": ["RUNNING", "PAUSED"]}})) is None   # never schedulable
    for r in run(_window_receipts()):
        assert r["simulation_run_id"] == st["simulation_run_id"]
    for t in run(_demo_tasks(simulation_run_id=st["simulation_run_id"])):   # receipts on generated work
        for r in run(db.receipts.find({"related_object_type": "task", "related_object_id": t["task_id"]},
                                      {"_id": 0}).to_list(50)):
            assert r["simulation_run_id"] == st["simulation_run_id"]


def test_13_no_real_provider_side_effects():
    assert CTX["control_calls"] >= 1      # the real request reached the provider path
    assert CTX["provider_calls"] == 0     # no simulated request did
    ids = {t["task_id"]: t for t in run(_demo_tasks())}
    sent = run(db.notifications.find({"task_id": {"$in": list(ids)}}, {"_id": 0}).to_list(500))
    assert sent, "department emails were configured, so simulated notifications must be recorded"
    for n in sent:
        assert n["status"] == "simulated" and n["simulated"] is True
        assert n["simulation_run_id"] == ids[n["task_id"]].get("simulation_run_id")
    assert run(db.notifications.count_documents({"task_id": {"$in": list(ids)},
                                                 "status": {"$in": ["sent", "failed", "queued"]}})) == 0


def test_14_startup_and_sign_in_hooks_off_by_default():
    os.environ.pop(continuity.AUTO_ENV, None)
    assert continuity.auto_enabled() is False
    before = run(continuity.get_state())
    async def _hook():
        continuity.catch_up_in_background("sign_in")   # would catch up a long gap if it ran
        await asyncio.sleep(0.3)
    run(_hook())
    assert run(continuity.get_state()) == before


def test_15_sim1_run_defers_and_records():
    last = run(continuity.get_state())["last_simulated_at"]
    rid = f"simrun_{TAG}"
    run(db.sim_runs.insert_one({"run_id": rid, "scenario": "sink_leak", "state": "RUNNING",
                                "created_at": "2000-01-01T00:00:00+00:00",
                                "cast": {"resident": {"filled_by": None},
                                         "maintenance_tech": {"filled_by": {"mode": "real", "name": "Carl (test)"}}}}))
    try:
        out = run(continuity.catch_up(now=ANCHOR + timedelta(hours=40)))
    finally:
        run(db.sim_runs.delete_many({"run_id": rid}))
    # The deferral names the blocking run and who holds it.
    assert out["status"] == "deferred" and out["blocking_run_id"] == rid
    assert rid in out["reason"] and "maintenance_tech held by Carl (test)" in out["reason"]
    assert run(continuity.get_state())["last_simulated_at"] == last
    rec = run(db.receipts.find_one({"action_type": "demo_continuity_deferred"}, {"_id": 0}))
    assert rec and rec["status"] == "failed" and rec["simulated"] is True
    assert rid in rec["failure_reason"]
