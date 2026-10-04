"""Voice-bridge reply filter: "on the way" only with movement evidence
(Michael, 2026-10-04). Acknowledged, claimed/assigned and started requests
get their own true wording; only a departed transportation run with an
authenticated departure receipt may be described as on the way.

Runs against a throwaway database (DB_NAME must start with caos_guard_test).
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytestmark = pytest.mark.skipif(not os.environ.get("DB_NAME", "").startswith("caos_guard_test"),
                                reason="needs a throwaway caos_guard_test* database")
LOOP = asyncio.new_event_loop()
CLAIM = "I've sent that to maintenance. It's on its way!"


def run(c):
    return LOOP.run_until_complete(c)


def task(tid, **kw):
    base = {"task_id": tid, "resident_id": "r1", "room": "G1", "category": "maintenance",
            "status": "pending"}
    base.update(kw)
    return base


def receipt(tid, action, basis="authenticated", status="in_progress"):
    return {"receipt_id": f"rc_{tid}_{action}", "related_object_type": "task", "related_object_id": tid,
            "action_type": action, "identity_basis": basis, "status": status}


@pytest.fixture(scope="module", autouse=True)
def seed():
    from deps import db

    async def go():
        await db.client.drop_database(os.environ["DB_NAME"])
        await db.staff_tasks.insert_many([
            task("t_created"),
            task("t_ack", acknowledged_by="u1"),
            task("t_assigned", assigned_to="u1", acknowledged_by="u1"),
            task("t_started", status="in_progress", assigned_to="u1"),
            task("t_ride_departed", category="transportation", status="in_progress", assigned_to="d1",
                 transport_run_id="run_dep"),
            task("t_ride_no_receipt", category="transportation", status="in_progress", assigned_to="d1",
                 transport_run_id="run_dep"),
            task("t_ride_booked", category="transportation", status="pending", assigned_to="d1",
                 transport_run_id="run_booked"),
            task("t_ride_unverified", category="transportation", status="in_progress", assigned_to="d1",
                 transport_run_id="run_dep"),
            task("t_done", status="completed"),
        ])
        await db.receipts.insert_many([
            receipt("t_ack", "task_acknowledged"), receipt("t_assigned", "task_assigned"),
            receipt("t_started", "task_in_progress"), receipt("t_ride_departed", "transportation_departed"),
            receipt("t_ride_unverified", "transportation_departed", basis="unverified_room_claim")])
        await db.transport_runs.insert_many([
            {"run_id": "run_dep", "status": "in_progress", "departed_at": "2026-10-04T14:00:00+00:00"},
            {"run_id": "run_booked", "status": "scheduled"}])
    run(go())
    yield
    from deps import db as d
    run(d.client.drop_database(os.environ["DB_NAME"]))


def guard(reply, ids):
    from routes.arrival_claim_guard import guard_reply
    return run(guard_reply(reply, ids))


@pytest.mark.parametrize("tid,expected", [
    ("t_created", "I've requested help."),
    ("t_ack", "Your request has been acknowledged."),
    ("t_assigned", "A staff member has accepted your request."),
    ("t_started", "Work on your request has started."),
])
def test_no_on_the_way_before_movement(tid, expected):
    text, removed = guard(CLAIM, [tid])
    assert removed == ["It's on its way!"]
    assert text == f"I've sent that to maintenance. {expected}"


@pytest.mark.parametrize("phrase", [
    "Someone is on the way.", "They're coming now.", "A nurse will be right there.",
    "Maintenance is headed to your room.", "Help is en route.", "They'll be over shortly.",
])
def test_every_movement_phrasing_is_caught_for_started_work(phrase):
    text, removed = guard(f"Okay. {phrase}", ["t_started"])
    assert removed == [phrase] and text == "Okay. Work on your request has started."


def test_departed_transport_with_receipt_may_say_on_the_way():
    reply = "Your driver has left and is on the way."
    assert guard(reply, ["t_ride_departed"]) == (reply, [])


@pytest.mark.parametrize("tid,expected", [
    ("t_ride_no_receipt", "Work on your request has started."),    # state but no receipt
    ("t_ride_unverified", "Work on your request has started."),    # receipt not authenticated
    ("t_ride_booked", "A staff member has accepted your request."),  # booked, not departed
])
def test_transport_without_full_movement_evidence_is_not_on_the_way(tid, expected):
    text, removed = guard("Your driver is on the way.", [tid])
    assert removed == ["Your driver is on the way."] and text == expected


def test_mixed_requests_use_the_least_advanced_true_stage():
    text, removed = guard("It's on its way!", ["t_ride_departed", "t_ack"])
    assert removed and text == "Your request has been acknowledged."


def test_no_open_request_and_untouched_replies():
    assert guard("It's on its way!", ["t_done"])[0] == "I don't have anyone confirmed for that yet."
    assert guard("It's on its way!", [])[0] == "I don't have anyone confirmed for that yet."
    plain = "I've requested help. Your request has been acknowledged."
    assert guard(plain, ["t_created"]) == (plain, [])
