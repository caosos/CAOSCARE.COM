"""Agent registry (db.agent_registry) and server-side bindings.

The six Pilot 1 agents are registered with no binding: they are shown as
OFFLINE with UNKNOWN task/branch until Michael binds them to a real session.
Nothing about them is inferred. One test agent is bound to the mock adapter.
"""
from typing import Optional

from deps import db
from agent_control.adapters import ADAPTERS
from agent_control.models import AgentSeed

# Server-side configuration only. An agent can be bound to one of these ids;
# a request body can never supply a target, path, session name or executable.
BINDINGS = {
    "mock-test": {"adapter": "mock", "target": "mock-test"},
}

SEED = [
    AgentSeed(agent_id="claude-1-coordinator", display_name="Claude 1", role="Coordinator"),
    AgentSeed(agent_id="claude-2-wake", display_name="Claude 2", role="Wake phrase / voice"),
    AgentSeed(agent_id="claude-3-simulator", display_name="Claude 3", role="Operations simulator"),
    AgentSeed(agent_id="claude-4-shared-core", display_name="Claude 4", role="Shared core"),
    AgentSeed(agent_id="claude-5-hardware-rf", display_name="Claude 5", role="Hardware / RF"),
    AgentSeed(agent_id="claude-6-security", display_name="Claude 6", role="Security"),
    AgentSeed(agent_id="claude-test-mock", display_name="Test agent (mock)",
              role="Control-plane test agent", binding_id="mock-test"),
]

_UNKNOWN_FIELDS = {"session_ref": None, "branch": None, "current_task": None,
                   "blocked_on": None, "last_activity_at": None,
                   "last_message": None, "last_receipt_id": None}


async def ensure_seeded() -> None:
    """Idempotent: inserts missing agents, never overwrites existing records."""
    await db.agent_commands.create_index("client_command_id", unique=True)
    await db.agent_commands.create_index("command_id", unique=True)
    for seed in SEED:
        await db.agent_registry.update_one(
            {"agent_id": seed.agent_id},
            {"$setOnInsert": {**seed.model_dump(), **_UNKNOWN_FIELDS}}, upsert=True)


def binding_for(agent: dict) -> Optional[dict]:
    return BINDINGS.get(agent.get("binding_id") or "")


async def get_agent(agent_id: str) -> Optional[dict]:
    return await db.agent_registry.find_one({"agent_id": agent_id}, {"_id": 0})


async def with_status(agent: dict) -> dict:
    """Agent record plus live status from its adapter. Unbound → offline."""
    binding = binding_for(agent)
    if not binding:
        status = {"state": "offline", "adapter": None, "simulated": False,
                  "detail": "not bound to a session"}
    else:
        st = await ADAPTERS[binding["adapter"]].get_agent_status(binding)
        status = st.model_dump(exclude={"events"})
    return {**agent, "status": status}


async def list_agents() -> list:
    await ensure_seeded()
    agents = await db.agent_registry.find({}, {"_id": 0}).sort("agent_id", 1).to_list(100)
    return [await with_status(a) for a in agents]
