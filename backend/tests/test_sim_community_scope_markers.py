"""Server-derived simulation scope is preserved across canonical evidence."""
import asyncio

from models import Notification, Receipt
from routes import notifications, task_lifecycle
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE


class Residents:
    def __init__(self, row):
        self.row = row

    async def find_one(self, query, projection=None):
        return dict(self.row) if self.row.get("resident_id") == query.get("resident_id") else None


class Store:
    def __init__(self, resident):
        self.residents = Residents(resident)


def marker_for(monkeypatch, resident):
    monkeypatch.setattr(task_lifecycle, "db", Store(resident))
    return asyncio.run(task_lifecycle.simulation_marker(resident["resident_id"], "simrun-1"))


def test_living_community_marker_is_server_derived_and_complete(monkeypatch):
    marker = marker_for(monkeypatch, {
        "resident_id": "sim:resident:001",
        "synthetic": True,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    })
    assert marker == {
        "simulated": True,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "simulation_run_id": "simrun-1",
    }
    assert task_lifecycle._run_link(marker) == {
        "simulation_run_id": "simrun-1",
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    }


def test_legacy_demo_marker_remains_compatible(monkeypatch):
    marker = marker_for(monkeypatch, {"resident_id": "demo", "synthetic": True})
    assert marker == {
        "simulated": True,
        "simulation_scope": "demo_room",
        "simulation_run_id": "simrun-1",
    }


def test_task_scope_reaches_receipt_and_provider_suppression_context():
    task = {
        "task_id": "task-1", "simulated": True,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "simulation_run_id": "simrun-1",
    }
    context = notifications.simulation_of(task, "rcpt-1")
    assert context == {
        "simulated": True,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "simulation_run_id": "simrun-1",
        "task_id": "task-1",
        "receipt_id": "rcpt-1",
    }
    note = Notification(channel="email", to="nobody@example.test", body="test", **context)
    receipt = Receipt(
        action_type="resident_request_created", related_object_type="task",
        related_object_id="task-1", **task_lifecycle._run_link(task),
    )
    assert note.simulation_community_id == COMMUNITY_ID
    assert receipt.simulation_scope == SIMULATION_SCOPE
    assert receipt.simulation_community_id == COMMUNITY_ID
