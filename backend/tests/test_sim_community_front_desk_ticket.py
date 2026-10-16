"""Focused proof for provider-fenced canonical Front Desk task origin."""

import asyncio

import pytest

from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_day_queue import build_day_queue
from simulation.community_executor import ExecutionContext
from simulation.community_front_desk_ticket import FrontDeskTicketError, create_front_desk_request
from tests.community_runtime_fake import RuntimeStore


def _event():
    return next(event for event in build_day_queue() if (
        event.action_type == "front_desk_message_follow_up"
        and event.task_phase == "open"
    ))


def _context(**changes):
    values = {
        "run_id": "run-front-desk", "holder_id": "holder", "fence": 1,
        "cursor": 0, "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID, "providers_allowed": False,
    }
    values.update(changes)
    return ExecutionContext(**values)


def test_front_desk_task_is_canonical_run_scoped_and_provider_fenced():
    async def scenario():
        event, store = _event(), RuntimeStore()
        store.residents.docs.append({
            "resident_id": event.target_id, "name": event.actor_name, "room": "SIM-003",
            "synthetic": True, "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
        })
        origins = []

        async def origin(task, actor):
            origins.append((task, actor))
            return {"receipt_id": "rcpt-front-desk-origin"}

        result = await create_front_desk_request(
            event=event, context=_context(), summary="Review a simulated resident message.",
            priority="normal", store=store, origin_recorder=origin,
        )

        assert result["status"] == "pending"
        assert len(store.staff_tasks.docs) == len(origins) == 1
        task, actor = origins[0]
        assert task["task_id"] == result["task_id"]
        assert task["category"] == task["visibility_role"] == "front_desk"
        assert task["source"] == "simulator" and task["simulated"] is True
        assert task["simulation_run_id"] == "run-front-desk"
        assert task["simulation_scope"] == SIMULATION_SCOPE
        assert task["simulation_community_id"] == COMMUNITY_ID
        assert actor.actor_id == event.target_id
        assert actor.actor_type == "simulated-agent"
        assert actor.identity_basis == "synthetic" and actor.simulated is True

    asyncio.run(scenario())


def test_front_desk_task_refuses_provider_access_or_unscoped_resident():
    async def scenario():
        event, store = _event(), RuntimeStore()
        with pytest.raises(FrontDeskTicketError, match="invalid Front Desk"):
            await create_front_desk_request(
                event=event, context=_context(providers_allowed=True),
                summary="x", priority="normal", store=store,
            )
        with pytest.raises(FrontDeskTicketError, match="exact synthetic resident"):
            await create_front_desk_request(
                event=event, context=_context(), summary="x", priority="normal", store=store,
            )
        assert store.staff_tasks.docs == []

    asyncio.run(scenario())
