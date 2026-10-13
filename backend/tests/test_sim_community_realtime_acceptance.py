"""User-visible acceptance: a living-community ticket moves while watched."""

import asyncio
from copy import deepcopy

from routes.actor_context import ActorContext
from simulation import community_runner
from simulation.community_activity_view import activity_snapshot
from simulation.community_runtime_view import runtime_snapshot
from simulation.community_ticket_plan import CLAIM, COMPLETE, OPEN
from tests.community_realtime_harness import (
    AUTHORITY,
    HOLDER_ID,
    NOW,
    RealtimeAcceptanceHarness,
)


OWNER = ActorContext(
    actor_id="user:michael", actor_type="real-human",
    identity_basis="authenticated", channel="staff_ui",
    name="Michael", role="owner", simulated=False,
)


def _target_task(snapshot, resident_id):
    return next(item for item in snapshot["tasks"]["items"]
                if item["resident"]["id"] == resident_id)


def _transition(snapshot, task_id, action):
    return next(item for item in snapshot["transitions"]["items"]
                if item["task_id"] == task_id and item["action_type"] == action)


def test_operator_watches_ticket_open_work_complete_pause_resume_and_stop():
    async def scenario():
        harness = RealtimeAcceptanceHarness(OWNER)
        created = await harness.create_and_provision()
        assert created["run"]["state"] == "PAUSED"
        assert len(harness.store.residents.docs) == 10
        assert len([row for row in harness.store.receipts.docs
                    if row.get("action_type") == "simulation_resident_provisioned"]) == 10

        resumed = await harness.resume("acceptance-resume-1")
        assert resumed["run"]["state"] == "RUNNING"
        assert resumed["readiness"]["resident_count"] == 10

        target_open = harness.plan.events[0]
        assert target_open.task_phase == OPEN
        opened = await harness.tick_next()
        assert opened.event_id == target_open.event_id and opened.cursor_after == 1

        runtime = await runtime_snapshot(store=harness.store, events=harness.plan.events)
        activity = await activity_snapshot(run_id=harness.run_id, store=harness.store)
        target = _target_task(activity, target_open.target_id)
        task_id = target["task_id"]
        assert runtime["status"] == activity["status"] == "loaded"
        assert runtime["run"]["state"] == "RUNNING"
        assert runtime["run"]["last_evidence"]["actor_id"] == target_open.target_id
        assert runtime["tickets"]["counts"] == {
            "open": 1, "in_progress": 0, "completed": 0,
            "skipped": 0, "other": 0, "total": 1,
        }
        assert target["status"] == "pending" and target["simulated"] is True
        assert target["resident"]["name"] == target_open.actor_name
        origin = _transition(activity, task_id, "resident_request_created")
        assert origin["actor"] == {
            "id": target_open.target_id, "type": "simulated-agent",
            "name": None, "role": None, "department": None,
            "channel": "simulator", "identity_basis": "synthetic",
            "simulated": True,
        }
        assert origin["provenance_status"] == "complete"

        paused = await harness.pause("acceptance-pause")
        assert paused["run"]["state"] == "PAUSED"
        before = deepcopy(harness.store.snapshot())
        frozen = await community_runner.tick(
            harness.run_id, HOLDER_ID, store=harness.store,
            timeline=harness.timeline, services=harness.services, now=NOW,
        )
        assert frozen.status == "paused" and frozen.cursor_before == frozen.cursor_after == 1
        after = harness.store.snapshot()
        assert after["staff_tasks"] == before["staff_tasks"]
        assert (await harness.run_row())["cursor"] == 1

        resumed = await harness.resume("acceptance-resume-2")
        assert resumed["run"]["state"] == "RUNNING"
        target_claim_index = next(
            index for index, event in enumerate(harness.plan.events)
            if event.workflow_event_id == target_open.workflow_event_id
            and event.task_phase == CLAIM
        )
        for _ in range(1, target_claim_index + 1):
            await harness.tick_next()

        runtime = await runtime_snapshot(store=harness.store, events=harness.plan.events)
        activity = await activity_snapshot(run_id=harness.run_id, store=harness.store)
        target = _target_task(activity, target_open.target_id)
        target_claim = harness.plan.events[target_claim_index]
        claimed = _transition(activity, task_id, "task_in_progress")
        assert target["status"] == "in_progress"
        assert target["assigned_worker"] == {
            "id": target_claim.actor_id, "name": target_claim.actor_name,
        }
        assert runtime["tickets"]["counts"]["in_progress"] == 1
        assert claimed["actor"]["id"] == target_claim.actor_id
        assert claimed["actor"]["department"] == target_claim.department
        assert claimed["parent_receipt_id"] == origin["receipt_id"]
        assert claimed["provenance_status"] == "complete"

        target_complete_index = next(
            index for index, event in enumerate(harness.plan.events)
            if event.workflow_event_id == target_open.workflow_event_id
            and event.task_phase == COMPLETE
        )
        for _ in range(target_claim_index + 1, target_complete_index + 1):
            await harness.tick_next()

        runtime = await runtime_snapshot(store=harness.store, events=harness.plan.events)
        activity = await activity_snapshot(run_id=harness.run_id, store=harness.store)
        target = _target_task(activity, target_open.target_id)
        completed = _transition(activity, task_id, "task_completed")
        target_complete = harness.plan.events[target_complete_index]
        assert runtime["status"] == activity["status"] == "loaded"
        assert runtime["run"]["last_evidence"]["actor_id"] == target_complete.actor_id
        assert runtime["run"]["last_evidence"]["actor_department"] == target_complete.department
        assert target["status"] == "completed"
        assert target["completed_at"] is not None
        assert runtime["tickets"]["counts"]["completed"] == 1
        assert completed["actor"]["id"] == target_complete.actor_id
        assert completed["before_status"] == "in_progress"
        assert completed["after_status"] == "completed"
        assert completed["parent_receipt_id"] == claimed["receipt_id"]
        assert completed["provenance_status"] == "complete"
        executor_proof = next(
            row for row in harness.store.receipts.docs
            if row.get("simulation_event_id") == target_complete.event_id
        )
        assert executor_proof["parent_receipt_id"] == completed["receipt_id"]
        assert executor_proof["correlation_id"] == origin["receipt_id"]

        stopped = await harness.stop("acceptance-stop")
        assert stopped["run"]["state"] == "STOPPED"
        final = await runtime_snapshot(store=harness.store, events=harness.plan.events)
        assert final["run"]["state"] == "STOPPED"
        assert final["run"]["cursor"] == target_complete_index + 1
        stop_receipt = stopped["receipt"]
        assert stop_receipt["action_type"] == "simulation_community_run_stopped"
        assert stop_receipt["actor_id"] == OWNER.actor_id
        assert stop_receipt["authority"] == AUTHORITY

    asyncio.run(scenario())
