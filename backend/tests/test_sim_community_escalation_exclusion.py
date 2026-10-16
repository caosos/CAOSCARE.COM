"""Focused isolation tests for always-on escalation processors."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from routes import escalation_tick, task_recurrence, task_unclaimed_escalation
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE


def _matches(row, query):
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(row, clause) for clause in expected):
                return False
            continue
        if key == "$nor":
            if any(_matches(row, clause) for clause in expected):
                return False
            continue
        actual = row.get(key)
        if isinstance(expected, dict):
            for operator, operand in expected.items():
                if operator == "$in" and actual not in operand:
                    return False
                if operator == "$nin" and actual in operand:
                    return False
                if operator == "$lt" and not (actual is not None and actual < operand):
                    return False
                if operator == "$lte" and not (actual is not None and actual <= operand):
                    return False
        elif actual != expected:
            return False
    return True


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def __aiter__(self):
        async def iterate():
            for row in self.rows:
                yield dict(row)
        return iterate()

    async def to_list(self, _limit):
        return [dict(row) for row in self.rows]


class _Collection:
    def __init__(self, rows=()):
        self.rows = [dict(row) for row in rows]
        self.find_queries = []
        self.update_queries = []

    def find(self, query, _projection=None):
        self.find_queries.append(query)
        return _Cursor(row for row in self.rows if _matches(row, query))

    async def update_one(self, query, update):
        self.update_queries.append(query)
        for row in self.rows:
            if _matches(row, query):
                row.update(update.get("$set", {}))
                for field, value in update.get("$push", {}).items():
                    row.setdefault(field, []).append(value)
                return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_alert_tick_excludes_server_derived_community_residents(monkeypatch):
    now = datetime(2026, 10, 13, tzinfo=timezone.utc)
    old = (now - timedelta(seconds=100)).isoformat()
    residents = _Collection([
        {"resident_id": "protected", "synthetic": True,
         "simulation_scope": SIMULATION_SCOPE, "simulation_community_id": COMMUNITY_ID},
        {"resident_id": "demo", "synthetic": True, "simulation_scope": "demo_room"},
    ])
    alerts = _Collection([
        {"alert_id": "protected-alert", "resident_id": "protected", "status": "active",
         "acknowledged_at": None, "resolved_at": None, "created_at": old, "escalation_level": 0},
        {"alert_id": "real-alert", "resident_id": "real", "status": "active",
         "acknowledged_at": None, "resolved_at": None, "created_at": old, "escalation_level": 0},
        {"alert_id": "demo-alert", "resident_id": "demo", "status": "active",
         "acknowledged_at": None, "resolved_at": None, "created_at": old, "escalation_level": 0},
    ])
    fake_db = SimpleNamespace(
        residents=residents, alerts=alerts, escalation_rules=_Collection(),
    )

    async def no_record(*_args, **_kwargs):
        return None

    async def no_unclaimed(*_args, **_kwargs):
        return {"unclaimed_flagged": 0, "unclaimed_examined": 0}

    async def no_recurrence():
        return {"recurring_generated": 0}

    monkeypatch.setattr(escalation_tick, "db", fake_db)
    monkeypatch.setattr(escalation_tick, "_record", no_record)
    monkeypatch.setattr(task_unclaimed_escalation, "escalate_unclaimed", no_unclaimed)
    monkeypatch.setattr(task_recurrence, "generate", no_recurrence)

    result = _run(escalation_tick.run_tick(now))

    by_id = {row["alert_id"]: row for row in alerts.rows}
    assert result["examined"] == 2
    assert by_id["protected-alert"]["escalation_level"] == 0
    assert by_id["real-alert"]["escalation_level"] == 2
    assert by_id["demo-alert"]["escalation_level"] == 2
    assert alerts.find_queries[0]["resident_id"] == {"$nin": ["protected"]}
    assert all(query["resident_id"] == {"$nin": ["protected"]} for query in alerts.update_queries)


def test_unclaimed_tick_excludes_exact_marker_but_keeps_real_and_demo(monkeypatch):
    now = datetime(2026, 10, 13, tzinfo=timezone.utc)
    old = (now - timedelta(minutes=20)).isoformat()
    common = {
        "visibility_role": "nursing", "status": "pending", "assigned_to": None,
        "unclaimed_claimed_at": None, "created_at": old, "requested_for_date": None,
    }
    tasks = _Collection([
        {**common, "task_id": "protected-task", "simulated": True,
         "simulation_scope": SIMULATION_SCOPE, "simulation_community_id": COMMUNITY_ID},
        {**common, "task_id": "real-task"},
        {**common, "task_id": "demo-task", "synthetic": True, "simulation_scope": "demo_room"},
    ])
    fake_db = SimpleNamespace(staff_tasks=tasks)
    transitioned = []

    async def no_run():
        return None

    async def record_transition(task_id, *_args, **_kwargs):
        transitioned.append(task_id)

    monkeypatch.setattr(task_unclaimed_escalation, "db", fake_db)
    monkeypatch.setattr(task_unclaimed_escalation, "active_run", no_run)
    monkeypatch.setattr(task_unclaimed_escalation, "classify", lambda *_args: {"bucket": "current"})
    monkeypatch.setattr(task_unclaimed_escalation, "transition", record_transition)

    result = _run(task_unclaimed_escalation.escalate_unclaimed(now, {}))

    by_id = {row["task_id"]: row for row in tasks.rows}
    assert result == {"unclaimed_flagged": 2, "unclaimed_examined": 2}
    assert "unclaimed_claimed_at" not in by_id["protected-task"] or not by_id["protected-task"]["unclaimed_claimed_at"]
    assert by_id["real-task"]["unclaimed_claimed_at"] == now.isoformat()
    assert by_id["demo-task"]["unclaimed_claimed_at"] == now.isoformat()
    assert transitioned == ["real-task", "demo-task"]
    expected = escalation_tick.outside_living_community_filter()
    assert tasks.find_queries[0]["$nor"] == expected["$nor"]
    assert all(query["$nor"] == expected["$nor"] for query in tasks.update_queries)
