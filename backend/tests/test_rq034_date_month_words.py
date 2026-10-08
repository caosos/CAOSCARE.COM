"""RQ-034: a day-of-month alone must not pick the month (N2); the transport
request stores the resident's literal words apart from the purpose (N3); a
resident-described hazard keeps the resident's words (D3). In-process, no
model calls.

    cd backend && DB_NAME=caoscare_rq034_test pytest tests/test_rq034_date_month_words.py -q
"""
import asyncio
import os
import sys
import uuid
from datetime import date, timedelta

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from operational_provenance import FAR_DATE_DAYS, reject_far_date  # noqa: E402
from routes.departments import seed_default_departments  # noqa: E402
from routes.realtime_tools_operations import _build_operations_tools  # noqa: E402
from routes.resident_requests import ResidentRequestInput, create_resident_request  # noqa: E402
from routes.transportation import TransportRequestInput, create_transport_request  # noqa: E402
from routes.transportation_voice_context import TransportChangeByContextInput, change_my_transport_request  # noqa: E402

TAG = f"rq034_{uuid.uuid4().hex[:8]}"
RID = f"{TAG}_res"


def run(c):
    return asyncio.get_event_loop().run_until_complete(c)


def _in(days):
    return (date.today() + timedelta(days=days)).isoformat()


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "")
    async def setup():
        await seed_default_departments()
        await db.residents.insert_one({"resident_id": RID, "name": f"{TAG} Resident", "room": "R-34"})
    run(setup())
    yield
    async def tear():
        await db.residents.delete_many({"resident_id": RID})
        await db.staff_tasks.delete_many({"resident_id": RID})
        await db.receipts.delete_many({"resident_id": RID})
        await db.notifications.delete_many({"resident_id": RID})
    run(tear())


def _tools():
    return {t["name"]: t for t in _build_operations_tools()}


# ---- N2 ----
def test_far_date_guard_boundary():
    assert reject_far_date(_in(0)) is None
    assert reject_far_date(_in(FAR_DATE_DAYS)) is None
    assert reject_far_date("not a date") is None
    far = reject_far_date(_in(FAR_DATE_DAYS + 1))
    assert far["needs_clarification"] and far["field"] == "requested_for_date"
    assert "Which month" in far["ask"] and "?" in far["ask"]


def test_transport_request_far_date_refused_nothing_filed():
    with pytest.raises(HTTPException) as e:
        run(create_transport_request(TransportRequestInput(
            resident_id=RID, purpose="doctor appointment", requested_for_date=_in(80))))
    assert e.value.status_code == 422 and e.value.detail["ask"]
    assert run(db.staff_tasks.count_documents({"resident_id": RID})) == 0


def test_change_ride_far_date_refused():
    with pytest.raises(HTTPException) as e:
        run(change_my_transport_request(TransportChangeByContextInput(resident_id=RID, requested_for_date=_in(80))))
    assert e.value.status_code == 422


def test_tool_text_requires_full_date_confirmation():
    tools = _tools()
    d = tools["request_transportation"]["description"]
    assert "day of the month" in d and "weekday and month" in d and "Never silently choose the month" in d
    assert "weekday and month" in tools["request_transportation"]["parameters"]["properties"]["requested_for_date"]["description"]


def test_persona_has_the_day_of_month_rule():
    from routes.realtime_companion_prompt import _build_companion_instructions
    text = run(_build_companion_instructions(None))
    assert "only a day of the month" in text and "never silently choose the month" in text


# ---- N3 ----
def test_transport_stores_literal_words_apart_from_purpose():
    out = run(create_transport_request(TransportRequestInput(
        resident_id=RID, purpose="appointment", requested_for_date=_in(10),
        resident_words="I need a ride to my eye doctor on the fifth.")))
    t = run(db.staff_tasks.find_one({"task_id": out["task_id"]}, {"_id": 0}))
    assert t["resident_words"] == "I need a ride to my eye doctor on the fifth."
    assert t["description"] == "appointment"


def test_transport_without_literal_words_does_not_reuse_purpose():
    out = run(create_transport_request(TransportRequestInput(
        resident_id=RID, purpose="appointment", requested_for_date=_in(11))))
    t = run(db.staff_tasks.find_one({"task_id": out["task_id"]}, {"_id": 0}))
    assert t["resident_words"] is None and t["description"] == "appointment"


# ---- D3 ----
def test_hazard_schema_and_filing_keep_resident_words():
    tools = _tools()
    cats = tools["request_staff_help"]["parameters"]["properties"]["category"]["enum"]
    assert "maintenance" in cats and "nursing" in cats
    assert "spill" in tools["request_staff_help"]["description"]
    said = "There is water on the floor by my bed."
    out = run(create_resident_request(ResidentRequestInput(
        category="maintenance", resident_id=RID, summary="water on the floor", resident_words=said)))
    t = run(db.staff_tasks.find_one({"task_id": out["task_id"]}, {"_id": 0}))
    assert t["resident_words"] == said and t["visibility_role"] == "maintenance"
