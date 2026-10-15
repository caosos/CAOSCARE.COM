"""Simulated escalation: thresholds, levels, leads, idempotency, loop hook."""
import asyncio
import json
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from tests.community_runtime_fake import _matches, _set
from simulation import community_escalation as esc
from simulation import community_loop as loop
from simulation import community_response_thresholds as thr
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_escalation_monitor import EscalationMonitor
from simulation.community_runner import TickResult

NOW = datetime(2026, 10, 14, 15, 0, tzinfo=timezone.utc)
RUN = "simrun-esc"
SCOPE = {"simulation_run_id": RUN, "simulation_scope": SIMULATION_SCOPE,
         "simulation_community_id": COMMUNITY_ID}


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, _limit):
        return deepcopy(self.rows)


class _Collection:
    def __init__(self):
        self.docs = []

    def find(self, query, _projection=None):
        return _Cursor([row for row in self.docs if _matches(row, query)])

    async def find_one(self, query, _projection=None):
        return next((deepcopy(row) for row in self.docs if _matches(row, query)), None)


class Store:
    def __init__(self):
        self.staff_tasks, self.receipts, self.notifications = _Collection(), _Collection(), _Collection()

    def writers(self):
        async def receipt(**kwargs):
            doc = {**kwargs.pop("provenance"), **kwargs}
            self.receipts.docs.append(doc)
            return doc

        async def update(task_id, set_fields, entries):
            row = next(t for t in self.staff_tasks.docs if t["task_id"] == task_id)
            for path, value in set_fields.items():
                _set(row, path, value)
            row.setdefault("event_log", []).extend(deepcopy(entries))

        async def notify(doc):
            self.notifications.docs.append(deepcopy(doc))
            return doc

        return esc.EscalationWriters(receipt, update, notify)

    def ticket(self, wf, *, status="pending", category="nursing", priority="normal",
               requested=600, routine="resident_call_help_up", waited=None,
               assigned_to=None):
        self.staff_tasks.docs.append({
            **SCOPE, "task_id": f"task-{wf}", "status": status, "category": category,
            "priority": priority, "simulated": True, "resident_id": "sim-res-1",
            "conversation_session_id": f"simulator:event:{wf}", "assigned_to": assigned_to,
        })
        self.receipts.docs.append({
            **SCOPE, "receipt_id": f"open-{wf}", "simulation_event_id": f"{wf}:ticket_open",
            "authority": "living_community_executor", "action_type": routine, "status": "completed",
            "after_state": {"requested_at_minute": requested},
        })
        if waited is not None:
            self.receipts.docs.append({
                **SCOPE, "receipt_id": f"claim-{wf}", "simulation_event_id": f"{wf}:ticket_claim",
                "authority": "living_community_executor", "action_type": routine,
                "status": "completed",
                "after_state": {"requested_at_minute": requested, "waited_minutes": waited},
            })
        return f"task-{wf}"

    def escalations(self):
        return [r for r in self.receipts.docs if r.get("action_type") == esc.ESCALATION_ACTION]


def run(store, minute, **kwargs):
    return asyncio.run(esc.escalate_overdue(store, RUN, minute, now=NOW,
                                            writers=store.writers(), **kwargs))


# ---- thresholds -------------------------------------------------------

def test_default_thresholds_follow_the_documented_rule():
    cell = lambda d, p: (thr.thresholds_for(d, p, thr.default_table())["pickup_minutes"],
                         thr.thresholds_for(d, p, thr.default_table())["complete_minutes"])
    assert cell("nursing", "high") == (10, 30) and cell("nursing", "normal") == (20, 60)
    assert cell("nursing", "low") == (40, 120) and cell("nursing", "urgent") == (5, 15)
    assert cell("maintenance", "normal") == (120, 480) and cell("kitchen", "normal") == (15, 45)
    assert cell("administration", "normal") == (240, 1440)
    assert cell("nursing", None) == cell("nursing", "normal")  # unknown is never urgent
    assert thr.thresholds_for("spa", "normal", thr.default_table()) is None
    assert thr.thresholds_for("maintenance", "normal", thr.default_table())["clock"] == "on_site"
    assert thr.thresholds_for("maintenance", "urgent", thr.default_table())["clock"] == "continuous"


def test_override_file_merges_and_bad_values_are_refused(tmp_path, monkeypatch):
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"maintenance": {"normal": {"pickup_minutes": 90}}}))
    monkeypatch.setenv(thr.THRESHOLDS_ENV, str(good))
    assert thr.thresholds_for("maintenance", "normal")["pickup_minutes"] == 90
    assert thr.thresholds_for("maintenance", "normal")["complete_minutes"] == 480
    for bad in ({"spa": {"normal": {"pickup_minutes": 5}}},
                {"nursing": {"stat": {"pickup_minutes": 5}}},
                {"nursing": {"normal": {"pickup_minutes": 0}}},
                {"nursing": {"normal": {"pickup_minutes": True}}},
                {"nursing": {"normal": {"pickup_minutes": 99999}}},
                {"nursing": {"normal": {"timeout": 5}}},
                {"nursing": {"normal": {"clock": "wall"}}}, []):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(bad))
        with pytest.raises(thr.ResponseThresholdError):
            thr.load_table(str(path))
    (tmp_path / "broken.json").write_text("{")
    with pytest.raises(thr.ResponseThresholdError):
        thr.load_table(str(tmp_path / "broken.json"))


# ---- escalation -------------------------------------------------------

def test_pending_past_pickup_escalates_once_to_the_on_duty_lead():
    store = Store()
    task_id = store.ticket("wf1", requested=600)  # day 0 10:00, nursing normal pickup 20
    assert run(store, 619)["escalated"] == []
    summary = run(store, 620)
    assert [(row["level"], row["phase"]) for row in summary["escalated"]] == [(1, "pickup")]
    [receipt] = store.escalations()
    lead = receipt["after_state"]["escalation"]["escalated_to"]
    assert lead["department"] == "nursing" and lead["job_role"] == "registered_nurse"
    assert lead["status"] == "on_duty" and receipt["assigned_user"] == lead["actor_id"]
    assert receipt["actor_id"] == esc.MONITOR.actor_id and receipt["simulated"] is True
    assert receipt["parent_receipt_id"] == "open-wf1" and receipt["simulation_run_id"] == RUN
    assert "simulation_event_id" not in receipt and "execution_cursor" not in receipt
    [note] = store.notifications.docs
    assert note["status"] == "simulated" and note["to"] == lead["actor_id"]
    assert note["receipt_id"] == receipt["receipt_id"] and note["simulation_run_id"] == RUN
    [entry] = store.staff_tasks.docs[0]["event_log"]
    assert entry["field"] == "escalated" and entry["sim_level"] == 1
    assert entry["threshold_minutes"] == 20 and entry["waited_minutes"] == 20
    assert store.staff_tasks.docs[0]["simulated_escalation_level"] == 1
    assert run(store, 621)["escalated"] == [] and len(store.escalations()) == 1
    assert task_id == "task-wf1"


def test_second_level_goes_to_the_supervisor_and_never_repeats():
    store = Store()
    store.ticket("wf2", requested=600)
    run(store, 620)
    summary = run(store, 640)
    assert [row["level"] for row in summary["escalated"]] == [2]
    level2 = store.escalations()[-1]["after_state"]["escalation"]["escalated_to"]
    assert level2["department"] == "administration" and level2["status"] == "on_duty"
    for minute in (641, 700, 900):
        assert run(store, minute)["escalated"] == []
    assert len(store.escalations()) == 2 and len(store.notifications.docs) == 2


def test_missed_levels_are_each_written_once_and_retry_reuses_ids():
    store = Store()
    store.ticket("wf3", requested=600)
    assert [row["level"] for row in run(store, 700)["escalated"]] == [1, 2]
    store.staff_tasks.docs[0].pop("simulated_escalation")  # crash before task write
    run(store, 701)
    assert len(store.escalations()) == 2 and len(store.notifications.docs) == 2


def test_no_lead_reachable_is_recorded_truthfully():
    store = Store()
    store.ticket("wf4", category="kitchen", priority="urgent", requested=21 * 60,
                 routine="resident_call_snack")  # kitchen closed at 21:00, no on-call
    [row] = run(store, 21 * 60 + 4)["escalated"]
    assert row["lead_reachable"] is False and row["notified"] is None
    receipt = store.escalations()[0]
    assert esc.NO_LEAD in receipt["result"] and receipt["next_state"] == "no_lead_reachable"
    assert receipt["after_state"]["escalation"]["emergency"] is False
    assert store.notifications.docs[0]["recipient_reachable"] is False
    assert store.notifications.docs[0]["status"] == "simulated"


def test_routine_after_hours_waits_for_on_site_staff_then_escalates():
    store = Store()
    store.ticket("wf5", category="maintenance", requested=16 * 60, routine="staff_report_leaking_faucet")
    summary = run(store, 23 * 60)
    assert summary["escalated"] == [] and summary["deferred"] == 1
    opened = 1440 + 7 * 60  # day 1 07:00 maintenance on site
    assert run(store, opened + 119)["escalated"] == []
    [row] = run(store, opened + 120)["escalated"]
    assert row["level"] == 1 and row["notified"].startswith("sim:staff:maintenance:")


def test_completed_and_real_staff_tickets_never_escalate():
    store = Store()
    store.ticket("wf6", status="completed", requested=0)
    store.ticket("wf7", status="in_progress", requested=0, waited=0, assigned_to="user-real-1")
    summary = run(store, 2000)
    assert summary["checked"] == 0 and store.escalations() == []


def test_in_progress_resident_call_measures_from_claim_receipt():
    store = Store()
    store.ticket("wf8", status="in_progress", requested=600, waited=10,
                 assigned_to="sim:staff:nursing:care_aide:01")  # claimed at 615
    assert run(store, 674)["escalated"] == []  # complete threshold 60
    [row] = run(store, 675)["escalated"]
    assert row["phase"] == "complete" and row["level"] == 1
    assert store.escalations()[0]["parent_receipt_id"] == "claim-wf8"
    assert store.escalations()[0]["after_state"]["escalation"]["kind"] == "resident_call"


def test_scheduled_routine_is_not_due_before_its_minute_and_unknown_is_not_guessed():
    store = Store()
    store.ticket("wf9", requested=900, routine="morning_room_check")
    store.staff_tasks.docs.append({**SCOPE, "task_id": "task-orphan", "status": "pending",
                                   "category": "nursing", "simulated": True,
                                   "conversation_session_id": "simulator:event:orphan"})
    summary = run(store, 800)
    assert summary["escalated"] == [] and summary["unknown"] == ["task-orphan"]
    measured = esc.measure({"status": "pending", "category": "nursing"},
                           {"requested": 900, "started": None, "routine": "morning_room_check"},
                           930, thr.thresholds_for("nursing", "normal", thr.default_table()))
    assert measured["kind"] == "scheduled_routine" and measured["level"] == 1
    assert esc.ticket_kind("resident_call_towels") == "resident_call"


# ---- loop hook --------------------------------------------------------

def test_monitor_runs_at_most_once_per_simulated_minute_and_absorbs_failure():
    calls = []

    async def escalate(store, run_id, minute, *, now):
        calls.append(minute)
        if minute == 12:
            raise RuntimeError("database unavailable")
        return {"escalated": []}

    async def case():
        monitor = EscalationMonitor(store=object(), escalate=escalate)
        for minute in (10, 10, 10, 11, 11, 12, 12):
            await monitor(run_id=RUN, sim_minute=minute, now=NOW)
        return monitor

    monitor = asyncio.run(case())
    assert calls == [10, 11, 12] and monitor.errors == 1
    assert "database unavailable" in monitor.last_error


def test_loop_survives_a_failing_monitor_and_still_ticks():
    row = {"run_id": RUN, "state": "RUNNING", "cursor": 0, "sim_minute": 10}
    seen = []

    async def load(*, run_id):
        return dict(row)

    async def advance(**_call):
        return dict(row)

    async def monitor(**call):
        seen.append(call["sim_minute"])
        raise RuntimeError("monitor bug")

    async def tick(*_args, **_kwargs):
        return TickResult(RUN, "stopped", "none", None, None, 0, 0, 1, False)

    async def case():
        manager = loop.CommunityLoopManager(
            store=object(), timeline=object(), services=object(), load_run=load,
            advance_sim_clock=advance, complete_run=advance, tick=tick,
            clock=lambda: NOW, monitor=monitor)
        assert manager.start(RUN, "loop-a") is True
        return await manager.wait(RUN)

    status = asyncio.run(case())
    assert seen == [10] and status.phase == "stopped" and status.ticks_finished == 1
    assert status.error_count == 0


def test_composition_wires_the_escalation_monitor():
    from simulation.community_control_composition import compose_community_controls

    control = compose_community_controls(store=object(), clock=lambda: NOW)
    assert isinstance(control.loop.monitor, EscalationMonitor)


def test_escalation_receipt_and_notification_fit_the_canonical_models():
    from models import Notification, Receipt

    store = Store()
    store.ticket("wf10", requested=600)
    run(store, 620)
    receipt = store.escalations()[0]
    model = Receipt(**receipt).model_dump()
    assert model["after_state"]["escalation"]["level"] == 1
    assert model["actor_type"] == "simulated-agent" and model["result_label"] == "simulated"
    assert model["source"] == "simulator" and model["receipt_id"] == receipt["receipt_id"]
    note = Notification(**store.notifications.docs[0]).model_dump()
    assert note["status"] == "simulated" and note["channel"] == "inapp"
