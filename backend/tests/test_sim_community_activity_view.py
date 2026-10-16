"""Exact-scope and uncertainty tests for the community activity read model."""

import asyncio
from copy import deepcopy

from simulation.community_activity_view import activity_snapshot
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from tests.community_runtime_fake import Collection, RuntimeStore


RUN_ID = "living-run-activity"


def marked(**extra):
    return {
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        **extra,
    }


def task(**extra):
    return marked(**{
        "task_id": "task-1", "simulation_run_id": RUN_ID, "simulated": True,
        "resident_id": "sim:resident:001", "resident_name": "UNTRUSTED DENORM",
        "title": "Scheduled simulated room check.", "description": "Room check due.",
        "category": "nursing", "visibility_role": "nursing", "priority": "normal",
        "status": "in_progress", "assigned_to": "sim:staff:nursing:01",
        "assigned_name": "SIM Nurse 01", "created_at": "2026-10-13T17:00:00+00:00",
        "started_at": "2026-10-13T17:01:00+00:00",
        "event_log": [{"at": "2026-10-13T17:01:00+00:00", "field": "status"}],
        **extra,
    })


def receipt(**extra):
    return marked(**{
        "receipt_id": "rcpt-1", "simulation_run_id": RUN_ID,
        "related_object_type": "task", "related_object_id": "task-1",
        "action_type": "task_started", "status": "in_progress",
        "actor_id": "sim:staff:nursing:01", "actor_type": "simulated-agent",
        "actor_name": "SIM Nurse 01", "actor_role": "staff",
        "actor_department": "nursing", "identity_basis": "synthetic",
        "simulated": True, "authority": "acts_for:nursing",
        "parent_receipt_id": "rcpt-origin", "correlation_id": "rcpt-origin",
        "before_state": {"status": "pending"}, "after_state": {"status": "in_progress"},
        "next_state": "in_progress", "created_at": "2026-10-13T17:01:00+00:00",
        **extra,
    })


def store():
    value = RuntimeStore()
    value.sim_runs.docs.append(marked(run_id=RUN_ID))
    return value


def run(coro):
    return asyncio.run(coro)


def test_activity_is_bounded_to_exact_run_and_synthetic_resident_identity():
    value = store()
    value.residents.docs.extend([
        marked(resident_id="sim:resident:001", name="SIM Resident 001", synthetic=True),
        {"resident_id": "real-resident", "name": "Private Person", "synthetic": False},
    ])
    value.staff_tasks.docs.extend([
        task(),
        task(task_id="wrong-run", simulation_run_id="other", resident_id="real-resident"),
        task(task_id="wrong-scope", simulation_scope="demo_room", resident_id="real-resident"),
        {"task_id": "real-task", "simulation_run_id": RUN_ID, "simulated": False,
         "resident_id": "real-resident", "resident_name": "Private Person"},
    ])
    value.receipts.docs.extend([
        receipt(),
        receipt(
            receipt_id="rcpt-human", actor_id="owner-1", actor_type="real-human",
            actor_name="Owner", identity_basis="authenticated", simulated=False,
            authority="admin_override:owner", action_type="task_completed",
            before_state={"status": "in_progress"}, after_state={"status": "completed"},
        ),
        receipt(receipt_id="wrong-run", simulation_run_id="other"),
    ])
    before = deepcopy(value.snapshot())

    out = run(activity_snapshot(run_id=RUN_ID, store=value))

    assert out["status"] == "loaded" and out["read_only"] is True
    assert [row["task_id"] for row in out["tasks"]["items"]] == ["task-1"]
    assert out["tasks"]["items"][0]["resident"] == {
        "id": "sim:resident:001", "name": "SIM Resident 001",
    }
    assert {row["receipt_id"] for row in out["transitions"]["items"]} == {
        "rcpt-1", "rcpt-human",
    }
    human = next(row for row in out["transitions"]["items"] if row["receipt_id"] == "rcpt-human")
    assert human["actor"]["type"] == "real-human"
    assert human["provenance_status"] == "complete"
    assert value.snapshot() == before


class FailedRead(Collection):
    def find(self, query, projection=None, session=None):
        raise RuntimeError("injected read failure")


def test_task_read_failure_is_unknown_not_false_empty():
    value = store()
    value.staff_tasks = FailedRead(value, "staff_tasks")

    out = run(activity_snapshot(run_id=RUN_ID, store=value))

    assert out["status"] == "error"
    assert out["tasks"] == {"status": "error", "items": None}
    assert out["transitions"] == {"status": "loaded", "items": []}
    assert out["sources"]["tasks"] == {"status": "error", "error": "RuntimeError"}


def test_missing_exact_run_refuses_all_activity_reads():
    value = RuntimeStore()
    value.staff_tasks.docs.append(task())
    value.receipts.docs.append(receipt())

    out = run(activity_snapshot(run_id=RUN_ID, store=value))

    assert out["status"] == "error"
    assert out["tasks"]["items"] is None
    assert out["transitions"]["items"] is None
    assert out["errors"] == [{"source": "run", "code": "run_not_exact"}]


def test_no_selected_run_is_not_started_and_never_claims_empty():
    out = run(activity_snapshot(run_id=None, store=RuntimeStore()))

    assert out["status"] == "not_started"
    assert out["tasks"]["items"] is None
    assert out["transitions"]["items"] is None
