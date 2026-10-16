"""Transactional, owner-invoked reset boundary for the living community.

Reset removes only exact living-community residents and their canonical work,
notification, and run rows.  Receipts are append-only and remain as evidence.
There is deliberately no route, startup hook, provider call, or scheduler hook.
"""
from datetime import datetime, timezone
from hashlib import sha256
from typing import Optional

from routes.actor_context import ActorContext
from simulation.community_blueprint import COMMUNITY_ID, RESIDENTS, SIMULATION_SCOPE
from simulation.community_provisioning import ProvisioningError, _require_operator
from simulation.community_reset_evidence import (
    OUTCOME_ACTION,
    REPLAY_ACTION,
    REQUEST_ACTION,
    RESET_COLLECTIONS,
    ResetEvidenceError,
    build_receipt,
    committed_result,
    load_reset_receipts,
    receipt_id,
    snapshot,
)


class CommunityResetError(RuntimeError):
    """Reset was refused, aborted, or has an explicitly unknown outcome."""


def _default_store():
    from deps import db

    return db


def _reset_id(reset_key: str, expected_run_id: str) -> str:
    key = (reset_key or "").strip()
    if not key or len(key) > 160:
        raise CommunityResetError("a stable reset_key of 1-160 characters is required")
    digest = sha256(
        f"{SIMULATION_SCOPE}:{COMMUNITY_ID}:{expected_run_id}:{key}".encode()
    ).hexdigest()[:20]
    return f"simreset:{digest}"


def _exact(row: dict) -> bool:
    return (
        row.get("simulation_scope") == SIMULATION_SCOPE
        and row.get("simulation_community_id") == COMMUNITY_ID
    )


async def _rows(collection, query: dict, session, *, include_id: bool = False) -> list[dict]:
    projection = None if include_id else {"_id": 0}
    cursor = collection.find(query, projection, session=session)
    return await cursor.to_list(None)


def _candidate_query(extra: Optional[list[dict]] = None) -> dict:
    return {"$or": [
        {"simulation_scope": SIMULATION_SCOPE},
        {"simulation_community_id": COMMUNITY_ID},
        *(extra or []),
    ]}


def _assert_exact(name: str, rows: list[dict]) -> None:
    if any(not _exact(row) for row in rows):
        raise CommunityResetError(f"{name} contains a partial, mismatched, or unmarked dependency")
    if name == "residents" and any(row.get("synthetic") is not True for row in rows):
        raise CommunityResetError("living-community resident is not explicitly synthetic")
    if name in ("staff_tasks", "notifications") and any(
        row.get("simulated") is not True for row in rows
    ):
        raise CommunityResetError(f"{name} contains a row not explicitly simulated")
    if name == "notifications" and any(row.get("status") != "simulated" for row in rows):
        raise CommunityResetError("living-community notification has non-simulated delivery state")


async def _preflight(store, session) -> tuple[dict[str, list[dict]], list[dict]]:
    resident_ids = [resident.resident_id for resident in RESIDENTS]
    rooms = [resident.room for resident in RESIDENTS]
    pendants = [resident.pendant_id for resident in RESIDENTS]
    residents = await _rows(
        store.residents,
        _candidate_query([
            {"resident_id": {"$in": resident_ids}},
            {"room": {"$in": rooms}},
            {"pendant_id": {"$in": pendants}},
        ]),
        session,
    )
    _assert_exact("residents", residents)

    runs = await _rows(store.sim_runs, _candidate_query(), session)
    _assert_exact("sim_runs", runs)
    if any(row.get("state") != "STOPPED" for row in runs):
        raise CommunityResetError("every living-community run must be STOPPED before reset")
    if any("execution_lease" in row for row in runs):
        raise CommunityResetError("living-community run has an active execution lease")
    run_ids = [row.get("run_id") for row in runs if row.get("run_id")]

    links = [
        {"resident_id": {"$in": resident_ids}},
        {"room": {"$in": rooms}},
    ]
    if run_ids:
        links.append({"simulation_run_id": {"$in": run_ids}})
    tasks = await _rows(store.staff_tasks, _candidate_query(links), session)
    _assert_exact("staff_tasks", tasks)
    task_ids = [row.get("task_id") for row in tasks if row.get("task_id")]
    note_links = list(links)
    if task_ids:
        note_links.extend([
            {"task_id": {"$in": task_ids}},
            {"related_object_id": {"$in": task_ids}},
        ])
    notes = await _rows(store.notifications, _candidate_query(note_links), session)
    _assert_exact("notifications", notes)

    object_ids = [
        *task_ids,
        *(row.get("notification_id") for row in notes),
        *run_ids,
        *resident_ids,
    ]
    receipt_links = [
        {"resident_id": {"$in": resident_ids}},
        {"room": {"$in": rooms}},
        {"related_object_id": {"$in": [value for value in object_ids if value]}},
    ]
    if run_ids:
        receipt_links.append({"simulation_run_id": {"$in": run_ids}})
    receipts = await _rows(
        store.receipts, _candidate_query(receipt_links), session, include_id=True,
    )
    _assert_exact("receipts", receipts)
    return {
        "residents": residents,
        "staff_tasks": tasks,
        "notifications": notes,
        "sim_runs": runs,
    }, receipts


async def _perform(
    store, session, operator, authority, reset_id, when, expected_run_id,
) -> dict:
    rows, receipts = await _preflight(store, session)
    try:
        reset_receipts = await load_reset_receipts(store, session, reset_id)
        prior = committed_result(reset_id, reset_receipts, rows)
    except ResetEvidenceError as exc:
        raise CommunityResetError(str(exc)) from exc
    if prior:
        prior["idempotent_replay"] = True
        prior["deleted"] = {name: 0 for name in RESET_COLLECTIONS}
        if not any(row.get("action_type") == REPLAY_ACTION for row in reset_receipts):
            outcome_id = receipt_id(reset_id, "outcome")
            outcome_state = next(
                row for row in reset_receipts if row["receipt_id"] == outcome_id
            )["after_state"]
            replay = build_receipt(
                REPLAY_ACTION, reset_id, operator, authority,
                prior["reset_generation"], outcome_state, outcome_state, when,
                parent=outcome_id,
            )
            await store.receipts.insert_one(replay, session=session)
        prior["receipt_id"] = receipt_id(reset_id, "replay")
        return prior

    runs = rows["sim_runs"]
    if len(runs) != 1 or runs[0].get("run_id") != expected_run_id:
        raise CommunityResetError("reset requires the exact confirmed STOPPED run")

    prior_outcomes = [row for row in receipts if row.get("action_type") == OUTCOME_ACTION]
    generation = 1 + max(
        ((row.get("after_state") or {}).get("reset_generation") or 0
         for row in prior_outcomes), default=0,
    )
    before = snapshot(rows, len(receipts))
    request_id = receipt_id(reset_id, "request")
    request = build_receipt(
        REQUEST_ACTION, reset_id, operator, authority, generation, before, before, when,
    )
    await store.receipts.insert_one(request, session=session)

    deleted = {}
    exact_filter = {
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    }
    for name in ("notifications", "staff_tasks", "sim_runs", "residents"):
        result = await getattr(store, name).delete_many(exact_filter, session=session)
        expected = len(rows[name])
        if result.deleted_count != expected:
            raise CommunityResetError(f"{name} changed after preflight; reset refused")
        deleted[name] = result.deleted_count

    after = {
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "counts": {name: 0 for name in RESET_COLLECTIONS},
        "preserved_receipts": len(receipts) + 2,
    }
    outcome_id = receipt_id(reset_id, "outcome")
    outcome = build_receipt(
        OUTCOME_ACTION, reset_id, operator, authority, generation,
        before, after, when, parent=request_id,
    )
    await store.receipts.insert_one(outcome, session=session)
    return {"reset_id": reset_id, "reset_generation": generation,
            "idempotent_replay": False, "receipt_id": outcome_id, "deleted": deleted}


async def _reconcile(store, reset_id: str) -> Optional[dict]:
    """Read exact durable evidence outside the failed transaction."""
    rows, _ = await _preflight(store, None)
    try:
        exact = await load_reset_receipts(store, None, reset_id)
        return committed_result(reset_id, exact, rows)
    except ResetEvidenceError as exc:
        raise CommunityResetError(str(exc)) from exc


async def _abort(session) -> bool:
    try:
        await session.abort_transaction()
        return True
    except Exception:
        return False


async def reset_living_community(
    operator: ActorContext, authority: str, reset_key: str, expected_run_id: str,
    *, store=None, now: Optional[datetime] = None,
) -> dict:
    """Reset exact living-community rows in one required database transaction."""
    try:
        _require_operator(operator, authority)
    except ProvisioningError as exc:
        raise CommunityResetError(str(exc)) from exc
    expected_run_id = (expected_run_id or "").strip()
    if not expected_run_id or len(expected_run_id) > 200:
        raise CommunityResetError("an exact expected_run_id is required")
    reset_id = _reset_id(reset_key, expected_run_id)
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise CommunityResetError("reset timestamp must be timezone-aware")
    selected = store if store is not None else _default_store()
    client = getattr(selected, "client", None)
    if client is None or not callable(getattr(client, "start_session", None)):
        raise CommunityResetError("transaction-capable database session is required")
    async with await client.start_session() as session:
        try:
            session.start_transaction()
            attempted = await _perform(
                selected, session, operator, authority, reset_id,
                instant.astimezone(timezone.utc), expected_run_id,
            )
        except Exception as exc:
            aborted = await _abort(session)
            if aborted:
                try:
                    concurrent = await _reconcile(selected, reset_id)
                except Exception:
                    concurrent = None
                if concurrent:
                    concurrent.update(
                        idempotent_replay=True,
                        commit_reconciled=True,
                        deleted={name: 0 for name in RESET_COLLECTIONS},
                    )
                    return concurrent
                if isinstance(exc, CommunityResetError):
                    raise
                raise CommunityResetError("reset transaction aborted before commit") from exc
            raise CommunityResetError(
                "reset outcome is unknown because transaction abort could not be confirmed"
            ) from exc
        try:
            await session.commit_transaction()
        except Exception as exc:
            try:
                committed = await _reconcile(selected, reset_id)
            except Exception as reconcile_exc:
                raise CommunityResetError(
                    "reset commit outcome is unknown; retry the same reset_key to reconcile"
                ) from reconcile_exc
            if not committed:
                raise CommunityResetError(
                    "reset commit outcome is unknown; retry the same reset_key to reconcile"
                ) from exc
            committed["commit_reconciled"] = True
            return committed
        attempted["commit_reconciled"] = False
        return attempted
