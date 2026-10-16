"""Read-only Mongo topology/transaction evidence and scratch-name guards."""

import re
from collections.abc import Iterable

from simulation.community_control_capability import probe_read_only_transaction


SCRATCH_PREFIX = "caoscare_sim_acceptance_"
SCRATCH_PATTERN = re.compile(rf"^{SCRATCH_PREFIX}[a-z0-9]{{8,32}}$")
KNOWN_PRODUCTION_NAMES = frozenset({"caoscare", "caoscare_production", "production", "prod"})


class CommunityMongoAcceptanceError(RuntimeError):
    """The requested probe or isolated acceptance run is unsafe or failed."""


def classify_topology(hello: dict) -> str:
    """Classify a Mongo ``hello`` response without retaining endpoint data."""
    if not isinstance(hello, dict):
        raise CommunityMongoAcceptanceError("MongoDB hello returned no document")
    if hello.get("msg") == "isdbgrid":
        return "sharded"
    if isinstance(hello.get("setName"), str) and hello["setName"].strip():
        return "replica_set"
    return "standalone"


def validate_scratch_database(
    scratch_db: str,
    *,
    production_db: str | Iterable[str] | None,
    confirmed: bool,
) -> str:
    """Require a disposable name, explicit confirmation, and prod inequality."""
    name = scratch_db.strip() if isinstance(scratch_db, str) else ""
    if not SCRATCH_PATTERN.fullmatch(name):
        raise CommunityMongoAcceptanceError(
            f"scratch database must match {SCRATCH_PREFIX}<8-32 lowercase letters/digits>"
        )
    forbidden = set(KNOWN_PRODUCTION_NAMES)
    candidates = (production_db,) if isinstance(production_db, str) else production_db or ()
    forbidden.update(
        value.strip().lower()
        for value in candidates
        if isinstance(value, str) and value.strip()
    )
    if name.lower() in forbidden:
        raise CommunityMongoAcceptanceError("scratch database matches a production database name")
    if not confirmed:
        raise CommunityMongoAcceptanceError(
            "scratch mutations require --confirm-scratch-mutations"
        )
    return name


async def probe_mongo(store) -> dict:
    """Run only ``hello`` plus a real transactional read that is aborted."""
    try:
        hello = await store.client.admin.command({"hello": 1})
        topology = classify_topology(hello)
    except CommunityMongoAcceptanceError:
        raise
    except Exception as exc:
        return {
            "status": "failed",
            "topology": "unknown",
            "transaction_read_abort": False,
            "error_type": type(exc).__name__,
        }
    transaction = await probe_read_only_transaction(store)
    passed = bool(transaction.get("supported"))
    return {
        "status": "passed" if passed else "failed",
        "topology": topology,
        "transaction_read_abort": passed,
        "error_type": None if passed else transaction.get("blocker") or "TransactionProbeFailed",
    }


async def require_pristine_scratch(store, expected_name: str) -> None:
    """Refuse a wrong or previously materialized database before any write."""
    if getattr(store, "name", None) != expected_name:
        raise CommunityMongoAcceptanceError("selected database is not the validated scratch database")
    try:
        collections = await store.list_collection_names()
    except Exception as exc:
        raise CommunityMongoAcceptanceError(
            f"scratch emptiness inspection failed ({type(exc).__name__})"
        ) from exc
    if collections:
        raise CommunityMongoAcceptanceError(
            "scratch database is not pristine; choose a new unique disposable name"
        )
