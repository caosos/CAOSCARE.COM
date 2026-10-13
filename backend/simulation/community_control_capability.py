"""Fail-closed capability proof for living-community HTTP controls."""

import os

from simulation.community_index_contract import inspect_required_indexes


ENABLE_ENV = "CAOSCARE_LIVING_COMMUNITY_CONTROLS"


def controls_explicitly_enabled() -> bool:
    return os.environ.get(ENABLE_ENV, "").strip().lower() == "true"


async def probe_read_only_transaction(store) -> dict:
    """Execute and abort a real transactional read; never write test data."""
    client = getattr(store, "client", None)
    start_session = getattr(client, "start_session", None)
    if not callable(start_session):
        return {
            "status": "failed",
            "supported": False,
            "blocker": "database client does not expose sessions",
        }
    session = None
    try:
        session = await start_session()
        async with session:
            session.start_transaction()
            await store.sim_runs.find_one(
                {"_id": "__living_community_read_only_transaction_probe__"},
                {"_id": 1},
                session=session,
            )
            if not getattr(session, "in_transaction", False):
                raise RuntimeError("transaction was not active during the read")
            await session.abort_transaction()
        return {"status": "passed", "supported": True, "blocker": None}
    except Exception as exc:
        if session is not None and getattr(session, "in_transaction", False):
            try:
                await session.abort_transaction()
            except Exception:
                pass
        return {
            "status": "failed",
            "supported": False,
            "blocker": type(exc).__name__,
        }


async def control_capability(store) -> dict:
    enabled = controls_explicitly_enabled()
    transaction = await probe_read_only_transaction(store)
    indexes = await inspect_required_indexes(store)
    blockers = []
    if not enabled:
        blockers.append({
            "code": "controls_not_enabled",
            "message": f"Set {ENABLE_ENV}=true explicitly to enable mutations.",
        })
    if not transaction["supported"]:
        blockers.append({
            "code": "transactions_unavailable",
            "message": "MongoDB did not complete a real read-only transaction probe.",
        })
    if not indexes["ready"]:
        blockers.append({
            "code": "required_indexes_unavailable",
            "message": "Required named MongoDB indexes are missing, incompatible, or could not be inspected: "
                       + ", ".join(indexes["blockers"]),
        })
    allowed = enabled and transaction["supported"] and indexes["ready"]
    return {
        "schema_version": 1,
        "read_only": True,
        "controls_enabled": enabled,
        "transaction_probe": transaction,
        "index_probe": indexes,
        "mutations_allowed": allowed,
        "available_actions": (
            ["create_paused", "provision_residents", "resume", "pause", "step", "stop"]
            if allowed else []
        ),
        "step": {
            "enabled": allowed,
            "reason": (
                None if allowed else
                "Step requires the same explicit flag, transaction, and index gates."
            ),
        },
        "blockers": blockers,
    }
