"""Adapter registry. Only adapters listed here can be bound to an agent."""
from agent_control.adapters.mock import MockAdapter

ADAPTERS = {"mock": MockAdapter()}
