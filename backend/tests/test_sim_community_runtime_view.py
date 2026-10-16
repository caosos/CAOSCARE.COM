"""Focused truth tests for the read-only Live Operations projection."""

import asyncio
from copy import deepcopy

from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_executor import ExecutorEvent
from simulation.community_runtime_view import runtime_snapshot
from tests.community_runtime_fake import Collection, RuntimeStore, _matches


RUN_ID = "living-run-1"


def event(number: int, minute: int) -> ExecutorEvent:
    return ExecutorEvent(
        event_id=f"event-{number}", stream_kind="routine_dispatch",
        action_type="housekeeping_round", day_index=0, minute=minute,
        actor_id="sim:staff:housekeeping:housekeeper:01", actor_name="SIM Worker",
        actor_type="simulated-agent", identity_basis="synthetic",
        department="housekeeping", target_type="resident",
        target_id="sim:resident:01", adapter="canonical_staff_task",
    )


def marked(**extra):
    return {
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        **extra,
    }


def run_row(**extra):
    return marked(**{
        "run_id": RUN_ID, "state": "RUNNING", "cursor": 1, "sim_minute": 400, "resident_count": 10,
        "last_event_id": "event-0", "last_evidence_receipt_id": "receipt-0",
        "residents_provisioned": False,
        "created_at": "2026-10-13T12:00:00+00:00", **extra,
    })


def receipt(**extra):
    return marked(**{
        "receipt_id": "receipt-0", "simulation_run_id": RUN_ID,
        "simulation_event_id": "event-0", "execution_cursor": 0, "execution_fence": 2,
        "status": "completed", "action_type": "housekeeping_round",
        "actor_id": "sim:staff:housekeeping:housekeeper:01",
        "actor_name": "SIM Worker", "actor_type": "simulated-agent",
        "identity_basis": "synthetic", "simulated": True,
        "authority": "living_community_executor",
        "actor_department": "housekeeping",
        "related_object_type": "resident", "related_object_id": "sim:resident:01",
        "created_at": "2026-10-13T12:01:00+00:00", **extra,
    })


def task(status: str, task_id: str, **extra):
    return marked(
        task_id=task_id, simulation_run_id=RUN_ID, simulated=True,
        status=status, **extra,
    )


class CountCollection(Collection):
    async def count_documents(self, query):
        return sum(1 for row in self.documents if _matches(row, query))


def make_store():
    value = RuntimeStore()
    value.staff_tasks = CountCollection(value, "staff_tasks")
    return value


def run(coro):
    return asyncio.run(coro)


def test_loaded_snapshot_is_exact_run_scoped_runtime_truth():
    store = make_store()
    store.sim_runs.docs.extend([
        marked(run_id="old", state="STOPPED", cursor=2, sim_minute=20,
               created_at="2026-10-01T00:00:00+00:00"),
        run_row(),
    ])
    store.receipts.docs.extend([receipt(), marked(
        receipt_id="other", simulation_run_id="other-run",
        simulation_event_id="event-0",
    )])
    store.staff_tasks.docs.extend([
        task("pending", "task-open"), task("in_progress", "task-working"),
        task("completed", "task-done"), task("skipped", "task-skipped"),
        task("new-status", "task-other"),
        marked(task_id="other", simulation_run_id="other-run", simulated=True,
               status="pending"),
    ])

    out = run(runtime_snapshot(store=store, events=(event(0, 300), event(1, 500))))

    assert out["status"] == "loaded" and out["read_only"] is True
    assert out["run"]["run_id"] == RUN_ID and out["run"]["state"] == "RUNNING"
    assert out["run"]["simulated_time"] == {
        "absolute_minute": 400, "day_index": 0, "minute": 400, "hh_mm": "06:40",
    }
    assert out["run"]["progress"] == {
        "completed_events": 1, "total_events": 2, "percent": 50.0,
    }
    assert out["run"]["next_event"]["event_id"] == "event-1"
    assert out["run"]["last_evidence"]["receipt_id"] == "receipt-0"
    assert out["tickets"]["counts"] == {
        "open": 1, "in_progress": 1, "completed": 1,
        "skipped": 1, "other": 1, "total": 5,
    }
    assert out["staffing"]["workers"]
    assert out["staffing"]["coverage"]["nursing"]["on_shift"] > 0
    assert out["staffing"]["basis"] == "deterministic_schedule_at_persisted_simulated_time"
    assert out["run"]["resident_readiness"] == {
        "status": "not_provisioned", "residents_provisioned": False,
        "expected_resident_count": 10, "receipt_id": None, "reason": None,
    }


def readiness_receipt(run_id=RUN_ID, receipt_id="ready-1"):
    resident_receipts = [f"resident-receipt-{index}" for index in range(10)]
    return marked(
        receipt_id=receipt_id, simulation_run_id=run_id,
        action_type="simulation_community_resident_provisioning_completed",
        related_object_type="simulation_run", related_object_id=run_id,
        status="completed", actor_type="real-human", actor_id="owner-1",
        requested_by="owner-1", identity_basis="authenticated", simulated=False,
        actor_role="owner", source="staff", authority="admin_override:owner",
        parent_receipt_id="origin-1", correlation_id="origin-1",
        after_state={
            "run_id": run_id, "residents_provisioned": True,
            "provisioning_receipt_id": receipt_id,
            "provisioning_resident_receipt_ids": resident_receipts,
        },
    )


def test_ready_requires_exact_run_bound_receipt_and_exposes_receipt_id():
    store = make_store()
    resident_receipts = [f"resident-receipt-{index}" for index in range(10)]
    store.sim_runs.docs.append(run_row(
        residents_provisioned=True, provisioning_receipt_id="ready-1",
        provisioning_resident_receipt_ids=resident_receipts,
        origin_receipt_id="origin-1",
    ))
    store.receipts.docs.extend([receipt(), readiness_receipt()])

    out = run(runtime_snapshot(store=store, events=(event(0, 300), event(1, 500))))

    assert out["status"] == "loaded"
    assert out["run"]["resident_readiness"] == {
        "status": "ready", "residents_provisioned": True,
        "expected_resident_count": 10, "receipt_id": "ready-1", "reason": None,
    }
    assert out["sources"]["readiness"] == {"status": "loaded", "error": None}


def test_missing_readiness_receipt_is_error_and_never_looks_unprovisioned():
    store = make_store()
    store.sim_runs.docs.append(run_row(
        residents_provisioned=True, provisioning_receipt_id="missing",
        provisioning_resident_receipt_ids=[f"resident-receipt-{index}" for index in range(10)],
        origin_receipt_id="origin-1",
    ))
    store.receipts.docs.append(receipt())

    out = run(runtime_snapshot(store=store, events=(event(0, 300), event(1, 500))))

    assert out["status"] == "error" and out["run"]["status"] == "error"
    assert out["run"]["resident_readiness"]["status"] == "error"
    assert out["run"]["resident_readiness"]["residents_provisioned"] is None
    assert out["sources"]["readiness"]["error"] == "readiness_receipt_not_exact"


def test_no_run_is_not_started_and_never_invents_zero_counts():
    out = run(runtime_snapshot(store=make_store(), events=(event(0, 300),)))

    assert out["status"] == "unknown"
    assert out["run"]["status"] == "not_started"
    assert out["run"]["state"] is None
    assert all(value is None for value in out["tickets"]["counts"].values())
    assert out["staffing"]["status"] == "not_started"
    assert out["sources"]["tasks"]["status"] == "unknown"


class FailedRead(Collection):
    def find(self, query, projection=None, session=None):
        raise RuntimeError("injected read failure")

    async def count_documents(self, query):
        raise RuntimeError("injected read failure")


def test_failed_task_read_remains_null_not_verified_empty():
    store = make_store()
    store.sim_runs.docs.append(run_row(cursor=0, last_event_id=None,
                                       last_evidence_receipt_id=None))
    store.staff_tasks = FailedRead(store, "staff_tasks")

    out = run(runtime_snapshot(store=store, events=(event(0, 300),)))

    assert out["status"] == "error"
    assert out["sources"]["tasks"] == {"status": "error", "error": "RuntimeError"}
    assert out["tickets"]["status"] == "error"
    assert all(value is None for value in out["tickets"]["counts"].values())
    assert out["run"]["status"] == "loaded"


def test_mismatched_last_receipt_is_an_error_not_evidence():
    store = make_store()
    store.sim_runs.docs.append(run_row())
    store.receipts.docs.append(receipt(execution_cursor=9))

    out = run(runtime_snapshot(store=store, events=(event(0, 300), event(1, 500))))

    assert out["status"] == "error"
    assert out["run"]["status"] == "error"
    assert out["run"]["last_evidence"] is None
    assert {row["code"] for row in out["errors"]} == {
        "last_evidence_provenance_mismatch"
    }


def test_multiple_active_runs_are_refused_as_ambiguous():
    store = make_store()
    store.sim_runs.docs.extend([run_row(), run_row(run_id="living-run-2")])

    out = run(runtime_snapshot(store=store, events=(event(0, 300),)))

    assert out["status"] == "error"
    assert out["run"]["run_id"] is None
    assert out["sources"]["runs"] == {
        "status": "error", "error": "multiple_active_runs",
    }


def test_inputs_are_read_only():
    store = make_store()
    store.sim_runs.docs.append(run_row())
    store.receipts.docs.append(receipt())
    store.staff_tasks.docs.append(task("pending", "task-1"))
    before = store.snapshot()

    run(runtime_snapshot(store=store, events=(event(0, 300), event(1, 500))))

    assert store.snapshot() == deepcopy(before)


def test_exact_90_day_terminal_boundary_is_valid_and_has_no_active_workers():
    store = make_store()
    store.sim_runs.docs.append(run_row(
        state="STOPPED", cursor=1, sim_minute=90 * 1440,
        last_event_id="event-0", last_evidence_receipt_id="receipt-0",
    ))
    store.receipts.docs.append(receipt())

    out = run(runtime_snapshot(store=store, events=(event(0, 300),)))

    assert out["status"] == "loaded"
    assert out["run"]["simulated_time"]["day_index"] == 90
    assert out["run"]["progress"]["percent"] == 100.0
    assert out["staffing"]["workers"] == []
    assert all(row["on_shift"] == 0 for row in out["staffing"]["coverage"].values())
