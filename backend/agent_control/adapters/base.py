"""The one interface every agent adapter implements (design §3).

The binding passed in comes from agent_control.registry.BINDINGS (server-side
configuration), never from a request body. Adapters must not run a shell and
must not read Claude Code session keys or sockets.
"""
from typing import List, Protocol

from agent_control.models import AgentReply, AgentStatus, Delivery


class AgentAdapter(Protocol):
    kind: str

    async def get_agent_status(self, binding: dict) -> AgentStatus: ...

    async def send_command(self, binding: dict, command: dict) -> Delivery: ...

    async def collect_reply(self, binding: dict, command: dict) -> AgentReply | None:
        """The agent's response/status for this command, if any yet."""
        ...

    async def get_agent_events(self, binding: dict, limit: int = 20) -> List[dict]: ...

    async def pause_agent(self, binding: dict) -> Delivery: ...
