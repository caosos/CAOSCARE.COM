"""In-process test agent. It is not a Claude session: everything it reports
is labelled simulated. Used for the first vertical slice and for tests.

A mock binding may set "fail": True to exercise the delivery-failure path."""
from typing import List

from agent_control.models import AgentReply, AgentStatus, Delivery


class MockAdapter:
    kind = "mock"

    def __init__(self):
        self._inbox: dict = {}          # binding target -> list of delivered commands

    async def get_agent_status(self, binding: dict) -> AgentStatus:
        return AgentStatus(state="online", adapter=self.kind, simulated=True,
                           detail="in-process mock agent (not a Claude session)")

    async def send_command(self, binding: dict, command: dict) -> Delivery:
        if binding.get("fail"):
            return Delivery(ok=False, evidence="mock binding configured to fail", simulated=True)
        self._inbox.setdefault(binding["target"], []).append(command["command_id"])
        return Delivery(ok=True, simulated=True,
                        evidence=f"mock inbox {binding['target']} holds {command['command_id']}")

    async def collect_reply(self, binding: dict, command: dict) -> AgentReply | None:
        if command["command_id"] not in self._inbox.get(binding["target"], []):
            return None
        first = command["instruction"].strip().splitlines()[0][:80]
        return AgentReply(status="acknowledged", simulated=True,
                          message=f"mock agent received: {first}")

    async def get_agent_events(self, binding: dict, limit: int = 20) -> List[dict]:
        return [{"command_id": c} for c in self._inbox.get(binding["target"], [])[-limit:]]

    async def pause_agent(self, binding: dict) -> Delivery:
        return Delivery(ok=False, evidence="pause not supported by the mock agent", simulated=True)
