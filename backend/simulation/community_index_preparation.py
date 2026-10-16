"""Non-destructive, receipt-backed simulator index preparation service.

The caller injects storage and explicitly invokes this service.  It has no
route, startup hook, default database, provider, deployment, or drop path.
"""

from datetime import datetime, timezone

from routes.actor_context import ActorContext
from simulation.community_index_contract import REQUIRED_INDEXES
from simulation.community_index_evidence import (
    COMPLETED, FAILED, RECONCILED, REQUESTED, IndexEvidenceError,
    build_receipt, load_receipts, operation_identity, validate_receipts,
)
from simulation.community_index_inspection import inspect_index_contract, public_snapshot
from simulation.community_provisioning import ProvisioningError, _require_operator


class IndexPreparationError(RuntimeError):
    """Simulator index preparation was refused or failed closed."""


def _utc(value: datetime | None) -> datetime:
    instant = value or datetime.now(timezone.utc)
    if not isinstance(instant, datetime) or instant.tzinfo is None:
        raise IndexPreparationError("index preparation timestamp must be timezone-aware")
    return instant.astimezone(timezone.utc)


def _operator(operator: ActorContext, authority: str) -> None:
    try:
        _require_operator(operator, authority)
    except ProvisioningError as exc:
        raise IndexPreparationError(str(exc)) from exc


async def _evidence(store, operation_id, key_digest, operator, authority, session):
    try:
        rows = await load_receipts(store, operation_id, session=session)
        return validate_receipts(rows, operation_id, key_digest, operator, authority)
    except IndexEvidenceError as exc:
        raise IndexPreparationError(str(exc)) from exc


async def _insert(store, document: dict, *, session=None) -> None:
    await store.receipts.insert_one(document, session=session)


def _result(outcome: dict, inspection: dict, *, replay: bool) -> dict:
    return {
        "status": "failed" if outcome["action_type"] == FAILED else "ready",
        "action_type": outcome["action_type"],
        "receipt_id": outcome["receipt_id"],
        "operation_id": outcome["related_object_id"],
        "idempotent_replay": replay,
        "inspection": public_snapshot(inspection),
    }


async def _write_outcome(
    store, action, operation_id, key_digest, operator, authority,
    before, after, when, *, failure_reason=None, session=None,
) -> dict:
    document = build_receipt(
        action, operation_id, key_digest, operator, authority,
        public_snapshot(before), public_snapshot(after), when,
        failure_reason=failure_reason,
    )
    try:
        await _insert(store, document, session=session)
        return document
    except Exception:
        evidence = await _evidence(
            store, operation_id, key_digest, operator, authority, session,
        )
        if evidence["outcome"] is not None:
            return evidence["outcome"]
        raise IndexPreparationError(
            "index state changed but durable outcome evidence could not be written"
        )


async def _create_missing(store, inspection: dict, *, session=None) -> list[str]:
    created = []
    by_name = {row["name"]: row for row in inspection["required"]}
    for requirement in REQUIRED_INDEXES:
        if by_name[requirement["name"]]["status"] != "missing":
            continue
        collection = getattr(store, requirement["collection"])
        options = ({"partialFilterExpression": requirement["partial"]}
                   if requirement.get("partial") else {})
        returned = await collection.create_index(
            list(requirement["keys"]),
            name=requirement["name"],
            unique=requirement["unique"],
            session=session,
            **options,
        )
        if returned != requirement["name"]:
            raise IndexPreparationError("database did not confirm the required index name")
        created.append(requirement["name"])
    return created


def _has_hard_blocker(inspection: dict) -> bool:
    return any(
        row["status"] in {"conflict", "probe_failed"}
        for row in inspection["required"]
    )


async def prepare_required_indexes(
    operator: ActorContext,
    authority: str,
    operation_key: str,
    *,
    store,
    session=None,
    now: datetime | None = None,
    recover_interrupted: bool = False,
) -> dict:
    """Create only missing exact indexes and durably prove the outcome.

    A prior request without an outcome requires explicit recovery so a second
    caller cannot silently race an attempt that may still be active.
    """
    _operator(operator, authority)
    instant = _utc(now)
    try:
        operation_id, key_digest = operation_identity(operation_key)
    except IndexEvidenceError as exc:
        raise IndexPreparationError(str(exc)) from exc
    evidence = await _evidence(
        store, operation_id, key_digest, operator, authority, session,
    )
    if evidence["outcome"] is not None:
        inspection = await inspect_index_contract(store, session=session)
        return _result(evidence["outcome"], inspection, replay=True)
    interrupted = evidence["request"] is not None
    if interrupted and not recover_interrupted:
        raise IndexPreparationError(
            "an incomplete preparation request exists; explicit recovery is required"
        )

    before = await inspect_index_contract(store, session=session)
    if not interrupted:
        request = build_receipt(
            REQUESTED, operation_id, key_digest, operator, authority,
            public_snapshot(before), public_snapshot(before), instant,
        )
        try:
            await _insert(store, request, session=session)
        except Exception:
            evidence = await _evidence(
                store, operation_id, key_digest, operator, authority, session,
            )
            if evidence["request"] is None:
                raise IndexPreparationError(
                    "no index change allowed without durable request evidence"
                )
            raise IndexPreparationError(
                "another preparation attempt owns this operation key"
            )

    if _has_hard_blocker(before):
        outcome = await _write_outcome(
            store, FAILED, operation_id, key_digest, operator, authority,
            before, before, instant,
            failure_reason="required index metadata is unavailable or conflicting",
            session=session,
        )
        return _result(outcome, before, replay=False)

    if before["ready"]:
        outcome = await _write_outcome(
            store, RECONCILED, operation_id, key_digest, operator, authority,
            before, before, instant, session=session,
        )
        return _result(outcome, before, replay=False)

    try:
        created = await _create_missing(store, before, session=session)
    except Exception as exc:
        after = await inspect_index_contract(store, session=session)
        if after["ready"]:
            outcome = await _write_outcome(
                store, RECONCILED, operation_id, key_digest, operator, authority,
                before, after, instant, session=session,
            )
            return _result(outcome, after, replay=False)
        outcome = await _write_outcome(
            store, FAILED, operation_id, key_digest, operator, authority,
            before, after, instant,
            failure_reason=f"index creation failed ({type(exc).__name__})",
            session=session,
        )
        return _result(outcome, after, replay=False)

    after = await inspect_index_contract(store, session=session)
    action = RECONCILED if interrupted else COMPLETED
    if not after["ready"]:
        action = FAILED
    outcome = await _write_outcome(
        store, action, operation_id, key_digest, operator, authority,
        before, after, instant,
        failure_reason=None if action != FAILED else "created indexes did not verify exactly",
        session=session,
    )
    result = _result(outcome, after, replay=False)
    result["created_indexes"] = created
    return result
