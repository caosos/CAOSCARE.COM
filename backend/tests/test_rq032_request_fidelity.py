"""RQ-032 request fidelity: content-aware dedup (D2), past dates asked about
(D5), the resident's literal words stored beside the summary (D6), and one
status read across every open category. In-process, no provider calls.

    cd backend && DB_NAME=caoscare_rq032_test pytest tests/test_rq032_request_fidelity.py -q
"""
import asyncio
import os
import sys
import uuid

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from operational_provenance import reject_past_date  # noqa: E402
from request_similarity import content_words, similarity  # noqa: E402
from routes.departments import seed_default_departments  # noqa: E402
from routes.resident_request_overview import resident_requests_open  # noqa: E402
from routes.resident_requests import ResidentRequestInput, create_resident_request  # noqa: E402
from routes.transportation import TransportRequestInput, create_transport_request  # noqa: E402
from routes.transportation_voice_context import TransportChangeByContextInput, change_my_transport_request  # noqa: E402

from datetime import date as _d, timedelta as _td  # noqa: E402
NEAR = (_d.today() + _td(days=10)).isoformat()
TAG = f"rq032_{uuid.uuid4().hex[:8]}"
RID = f"{TAG}_res"


def run(c):
    return asyncio.get_event_loop().run_until_complete(c)


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "")
    async def setup():
        await seed_default_departments()
        await db.residents.insert_one({"resident_id": RID, "name": f"{TAG} Resident", "room": "R-32"})
    run(setup())
    yield
    async def tear():
        await db.residents.delete_many({"resident_id": RID})
        await db.staff_tasks.delete_many({"resident_id": RID})
        await db.receipts.delete_many({"resident_id": RID})
        await db.notifications.delete_many({"resident_id": RID})
    run(tear())


def _req(summary, words=None, category="maintenance"):
    return run(create_resident_request(ResidentRequestInput(
        category=category, resident_id=RID, summary=summary, resident_words=words)))


def _task(task_id):
    return run(db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0}))


# ---- D2 ----
def test_similarity_rules():
    assert similarity(content_words("my sink is leaking"), content_words("the sink keeps leaking in the kitchen"))["same"]
    assert not similarity(content_words("strange smell in the bathroom"), content_words("bathroom sink leaking"))["same"]
    assert not similarity(content_words(""), content_words("sink leaking"))["same"]
    assert similarity(content_words("AC is not cooling"), content_words("the air conditioner AC not cooling"))["same"]


def test_different_issue_same_category_is_its_own_request():
    sink = _req("sink leaking in the bathroom", "my bathroom sink is leaking")
    smell = _req("strange smell in the bathroom", "Something smells strange in my bathroom.")
    assert sink["duplicate"] is False and smell["duplicate"] is False
    assert smell["task_id"] != sink["task_id"]
    t = _task(smell["task_id"])
    assert t["resident_words"] == "Something smells strange in my bathroom."
    assert _task(sink["task_id"]).get("re_request_count", 0) == 0


def test_same_issue_merges_and_keeps_new_wording():
    first = _req("sink leaking", "my sink is leaking")
    again = _req("kitchen sink keeps leaking", "the sink is leaking again, water on the floor")
    assert again["duplicate"] is True and again["task_id"] == first["task_id"] and again["same_issue"] is True
    assert again["re_request_count"] == 1 and again["times_asked"] == 2
    t = _task(first["task_id"])
    entry = [e for e in t["event_log"] if e["field"] == "re_request"][-1]
    assert "water on the floor" in entry["text"]


def test_merge_picks_the_matching_request_not_just_the_newest():
    sink = _req("sink leaking", "my sink is leaking")
    smell = _req("strange smell", "something smells strange")
    again = _req("sink leaking again", "the sink is leaking")
    assert again["duplicate"] and again["task_id"] == sink["task_id"] != smell["task_id"]


# ---- D5 ----
def test_past_date_is_asked_about():
    assert reject_past_date(NEAR) is None
    assert reject_past_date("not a date") is None
    past = reject_past_date("2000-01-05")
    assert past["needs_clarification"] and past["field"] == "requested_for_date" and "already passed" in past["ask"]
    assert "January 5" in past["ask"]


def test_transport_request_with_past_date_is_refused_and_nothing_filed():
    with pytest.raises(HTTPException) as e:
        run(create_transport_request(TransportRequestInput(
            resident_id=RID, purpose="doctor", requested_for_date="2000-01-05")))
    assert e.value.status_code == 422 and e.value.detail["field"] == "requested_for_date"
    assert run(db.staff_tasks.count_documents({"resident_id": RID, "category": "transportation"})) == 0
    ok = run(create_transport_request(TransportRequestInput(
        resident_id=RID, purpose="doctor", requested_for_date=NEAR)))
    assert ok["duplicate"] is False


def test_changing_a_ride_to_a_past_date_is_refused():
    with pytest.raises(HTTPException) as e:
        run(change_my_transport_request(TransportChangeByContextInput(resident_id=RID, requested_for_date="2000-01-05")))
    assert e.value.status_code == 422 and e.value.detail["ask"]


# ---- D6 ----
def test_literal_words_and_summary_are_stored_separately():
    out = _req("bathroom smell", "Something smells strange in my bathroom.")
    t = _task(out["task_id"])
    assert t["resident_words"] == "Something smells strange in my bathroom."
    assert t["description"] == "bathroom smell"


def test_no_literal_words_means_model_summary_is_not_stored_as_resident_words():
    out = _req("bathroom smell")
    t = _task(out["task_id"])
    assert t["resident_words"] is None and t["description"] == "bathroom smell"


# ---- status breadth ----
def test_open_status_covers_every_category_and_excludes_closed_and_excluded():
    a = _req("sink leaking", "my sink is leaking")
    b = _req("needs help to the bathroom", "I need help getting to the bathroom", category="nursing")
    c = _req("call about my bill", "I want to ask about my bill", category="front_desk")
    run(db.staff_tasks.update_one({"task_id": c["task_id"]}, {"$set": {"status": "completed"}}))
    ride = run(create_transport_request(TransportRequestInput(
        resident_id=RID, purpose="pharmacy", requested_for_date=NEAR)))
    got = run(resident_requests_open(resident_id=RID))
    cats = {r["category"]: r for r in got["requests"]}
    assert set(cats) == {"maintenance", "nursing", "transportation"}
    assert cats["maintenance"]["task_id"] == a["task_id"] and cats["nursing"]["task_id"] == b["task_id"]
    assert all(r["spoken"] for r in got["requests"])
    only = run(resident_requests_open(resident_id=RID, exclude_category="transportation"))
    assert {r["category"] for r in only["requests"]} == {"maintenance", "nursing"}
    assert ride["task_id"] not in [r["task_id"] for r in only["requests"]]


def test_open_status_keeps_each_requests_own_state():
    a = _req("sink leaking", "my sink is leaking")
    b = _req("needs help", "I need help getting up", category="nursing")
    run(db.staff_tasks.update_one({"task_id": b["task_id"]}, {"$set": {"status": "in_progress", "assigned_name": "Nora"}}))
    got = {r["category"]: r for r in run(resident_requests_open(resident_id=RID))["requests"]}
    assert got["maintenance"]["lifecycle"] == "open" and got["nursing"]["lifecycle"] != "open"
    assert got["maintenance"]["task_id"] == a["task_id"]
