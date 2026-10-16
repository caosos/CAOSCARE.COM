"""'It's 6:03 and I was supposed to get my medicine at six. Is someone coming?'
(aria-room-runtime-fixes-001). A reminder is not proof anyone is coming:
the check reports only what staff confirmed, otherwise files a HIGH-priority
Nursing request through the canonical request service, with a receipt, and
never says someone is on the way.

DB-direct through deps.db (MONGO_URL / DB_NAME); a throwaway resident/room.
"""
import asyncio
import os
import re
import sys
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deps import db  # noqa: E402
from routes.medication_status import MedicationStatusInput, check_medication_status  # noqa: E402
from routes.facility_local_time import facility_tz  # noqa: E402

ON_THE_WAY = re.compile(r"\b(someone|they|a nurse|staff)( is|'s| are)? (coming|on (the|their) way)\b", re.I)
run = asyncio.get_event_loop().run_until_complete


@pytest.fixture()
def resident():
    rid, room = f"res_med_{uuid.uuid4().hex[:8]}", f"T-MED-{uuid.uuid4().hex[:5]}"
    if not run(db.departments.find_one({"slug": "nursing", "active": True})):
        pytest.skip("nursing department not seeded in this database")
    tz = run(facility_tz())
    due = (datetime.now(ZoneInfo(tz)) - timedelta(minutes=3)).strftime("%H:%M")
    run(db.residents.insert_one({"resident_id": rid, "name": "Med Test Resident", "room": room}))
    run(db.med_reminders.insert_one({"reminder_id": f"med_{rid}", "resident_id": rid, "room": room, "title": "Evening pills",
                                     "time_hhmm": due, "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                                     "active": True}))
    yield rid, room, due
    tasks = run(db.staff_tasks.find({"resident_id": rid}, {"task_id": 1}).to_list(50))
    ids = [t["task_id"] for t in tasks]
    run(db.receipts.delete_many({"related_object_id": {"$in": ids}}))
    run(db.notifications.delete_many({"related_object_id": {"$in": ids}}))
    run(db.staff_tasks.delete_many({"resident_id": rid}))
    run(db.med_reminders.delete_many({"resident_id": rid}))
    run(db.residents.delete_one({"resident_id": rid}))


def _ask(rid, room, words="It's 6:03 and I was supposed to get my medicine at six. Is someone coming?"):
    return run(check_medication_status(MedicationStatusInput(resident_id=rid, room=room, resident_words=words,
                                                             conversation_session_id="rt_medtest")))


def test_unconfirmed_routes_high_priority_nursing_with_receipt(resident):
    rid, room, due = resident
    r = _ask(rid, room)
    assert r["staff_confirmed"] is False and r["someone_confirmed_on_the_way"] is False
    assert r["spoken"].startswith("I don't have confirmation that anyone is on the way yet.")
    assert "high-priority request to nursing" in r["spoken"]
    assert not ON_THE_WAY.search(r["spoken"].replace("anyone is on the way", ""))
    assert [s["time_hhmm"] for s in r["scheduled_today"]] == [due] and r["scheduled_today"][0]["due"] is True
    task = run(db.staff_tasks.find_one({"task_id": r["task_id"]}))
    assert task["category"] == "nursing" and task["priority"] == "high" and task["source"] == "aria_voice"
    assert task["status"] == "pending"
    assert run(db.receipts.find_one({"receipt_id": r["receipt_id"]})) is not None

    again = _ask(rid, room, "Is anyone coming with my pills?")
    assert again["task_id"] == r["task_id"] and again["duplicate"] is True        # re-asked, not a second ticket
    assert "asked nursing again" in again["spoken"]


def test_reports_only_what_staff_confirmed(resident):
    rid, room, _ = resident
    first = _ask(rid, room)
    run(db.staff_tasks.update_one({"task_id": first["task_id"]},
                                  {"$set": {"acknowledged_at": datetime.utcnow().isoformat(), "assigned_name": "Nurse Joy"}}))
    r = _ask(rid, room)
    assert r["staff_confirmed"] is True and r["task_id"] == first["task_id"]
    assert r["spoken"].startswith("Nursing has acknowledged your request and Nurse Joy has it.")
    assert not ON_THE_WAY.search(r["spoken"].replace("anyone is on the way", ""))
    run(db.staff_tasks.update_one({"task_id": first["task_id"]}, {"$set": {"status": "in_progress"}}))
    assert _ask(rid, room)["spoken"].startswith("Nurse Joy has started on your nursing request.")


def test_an_unrelated_open_nursing_request_confirms_nothing(resident):
    rid, room, _ = resident
    run(db.staff_tasks.insert_one({"task_id": f"task_{rid}_toilet", "resident_id": rid, "room": room,
                                   "category": "nursing", "status": "in_progress", "title": "Help to the bathroom",
                                   "resident_words": "I need help to the bathroom", "assigned_name": "Aide Sam"}))
    r = _ask(rid, room)
    assert r["staff_confirmed"] is False and r["task_id"] != f"task_{rid}_toilet"
