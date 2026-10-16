"""Shared, read-only transaction/index gate for startup recovery."""

from typing import Awaitable, Callable

from simulation.community_control_capability import (
    control_capability,
    controls_explicitly_enabled,
)
from simulation.community_index_contract import REQUIRED_INDEXES


class CommunityStartupCapabilityError(RuntimeError):
    """The shared capability proof did not match its canonical contract."""


CapabilityProbe = Callable[[], Awaitable[dict]]


def shared_capability_probe(*, store, probe=control_capability) -> CapabilityProbe:
    """Bind the same read-only transaction/six-index gate as HTTP controls."""
    async def capability():
        if not controls_explicitly_enabled():
            return {
                "schema_version": 1,
                "controls_enabled": False,
                "mutations_allowed": False,
                "blockers": [{"code": "controls_not_enabled"}],
            }
        return await probe(store)

    return capability


def capability_blockers(value) -> tuple[str, ...]:
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise CommunityStartupCapabilityError("shared capability proof is invalid")
    blockers = [
        row.get("code", "capability_blocked")
        for row in value.get("blockers", ())
        if isinstance(row, dict)
    ]
    if value.get("controls_enabled") is not True:
        blockers.append("controls_not_enabled")
        return tuple(dict.fromkeys(blockers))
    transaction = value.get("transaction_probe")
    if not isinstance(transaction, dict) or transaction.get("supported") is not True:
        blockers.append("transactions_unavailable")
    indexes = value.get("index_probe")
    expected = {row["name"] for row in REQUIRED_INDEXES}
    required = indexes.get("required", ()) if isinstance(indexes, dict) else ()
    ready = {
        row.get("name") for row in required
        if isinstance(row, dict) and row.get("status") == "ready"
    }
    if (
        not isinstance(indexes, dict) or indexes.get("ready") is not True
        or ready != expected or len(required) != len(expected)
    ):
        blockers.append("required_indexes_unavailable")
    if value.get("mutations_allowed") is not True:
        blockers.append("mutations_not_allowed")
    return tuple(dict.fromkeys(blockers))
