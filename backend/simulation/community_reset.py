"""Transactional, owner-invoked reset boundary for the living community.

Reset removes only exact living-community residents and their canonical work,
notification, and run rows.  Receipts are append-only and remain as evidence.
There is deliberately no route, startup hook, provider call, or scheduler hook.
"""
from datetime import datetime, timezone
from hashlib import sha256
from typing import Optional

from models import Receipt
from routes.actor_context import ActorContext
from simulation.community_blueprint import COMMUNITY_ID, RESIDENTS, SIMULATION_SCOPE
from simulation.community_provisioning import ProvisioningError, _require_operator


REQUEST_ACTION = "simulation_community_reset_requested"
OUTCOME_ACTION = "simulation_community_reset_completed"
REPLAY_ACTION = "simulation_community_reset_replayed"
RESET_COLLECTIONS = ("residents", "staff_tasks", "notifications", "sim_runs")


class CommunityResetError(RuntimeError):
    """Reset was refused or its transaction rolled back."""


def _default_store():
    from deps import db

    return db


def _reset_id(reset_key: str) -> str:
    key = (reset_key or "").strip()
    if not key or len(key) > 160:
        raise CommunityResetError("a stable reset_key of 1-160 characters is required")
    digest = sha256(f"{SIMULATION_SCOPE}:{COMMUNITY_ID}:{key}".encode()).hexdigest()[:20]
    return f"simreset:{digest}"


def _exact(row: dict) -> bool:
    return (
        row.get("simulation_scope") == SIMULATION_SCOPE
        and row.get("simulation_community_id") == COMMUNITY_ID
    )


async def _rows(collection, query: dict, session) -> list[dict]:
    cursor = collection.find(query, {"_id": 0}, session=session)
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
    receipts = await _rows(store.receipts, _candidate_query(receipt_links), session)
    _assert_exact("receipts", receipts)
    return {
        "residents": residents,
        "staff_tasks": tasks,
        "notifications": notes,
        "sim_runs": runs,
    }, receipts


def _snapshot(rows: dict[str, list[dict]], receipt_count: int) -> dict:
    return {
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "counts": {name: len(rows[name]) for name in RESET_COLLECTIONS},
        "preserved_receipts": receipt_count,
    }


def _receipt(
    action: str,
    receipt_id: str,
    reset_id: str,
    operator: ActorContext,
    authority: str,
    generation: int,
    before: dict,
    after: dict,
    when: datetime,
    *,
    parent: Optional[str] = None,
) -> dict:
    doc = Receipt(
        receipt_id=receipt_id,
        action_type=action,
        related_object_type="simulation_community_reset",
        related_object_id=reset_id,
        source="staff",
        status="created" if action == REQUEST_ACTION else "completed",
        completed_at=None if action == REQUEST_ACTION else when,
        result="reset authorized" if action == REQUEST_ACTION else
        "idempotent reset retry observed" if action == REPLAY_ACTION else
        "living-community data reset transaction committed",
        **operator.receipt_fields(),
        simulation_scope=SIMULATION_SCOPE,
        simulation_community_id=COMMUNITY_ID,
        authority=authority,
        parent_receipt_id=parent,
        correlation_id=f"rcpt:{reset_id}:request",
        before_state={**before, "reset_generation": generation},
        after_state={**after, "reset_generation": generation},
        result_label="simulated",
        next_state="reset_pending" if action == REQUEST_ACTION else "reset_complete",
        created_at=when,
    ).model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    if doc.get("completed_at") is not None:
        doc["completed_at"] = doc["completed_at"].isoformat()
    return doc


async def _perform(store, session, operator, authority, reset_id, when) -> dict:
    reset_receipts = await _rows(store.receipts, {
        "related_object_type": "simulation_community_reset",
        "related_object_id": reset_id,
    }, session)
    _assert_exact("receipts", reset_receipts)
    prior = [row for row in reset_receipts if row.get("action_type") == OUTCOME_ACTION]
    if len(prior) > 1:
        raise CommunityResetError("duplicate reset outcomes require manual review")
    if prior:
        outcome = prior[0]
        generation = (outcome.get("after_state") or {}).get("reset_generation")
        if not isinstance(generation, int) or generation < 1:
            raise CommunityResetError("prior reset outcome has invalid generation evidence")
        replay_number = sum(
            row.get("action_type") == REPLAY_ACTION for row in reset_receipts
        ) + 1
        replay = _receipt(
            REPLAY_ACTION, f"rcpt:{reset_id}:replay:{replay_number}", reset_id,
            operator, authority, generation, outcome["after_state"],
            outcome["after_state"], when, parent=outcome["receipt_id"],
        )
        await store.receipts.insert_one(replay, session=session)
        return {"reset_id": reset_id, "reset_generation": generation,
                "idempotent_replay": True, "receipt_id": replay["receipt_id"],
                "deleted": {name: 0 for name in RESET_COLLECTIONS}}
    if reset_receipts:
        raise CommunityResetError("incomplete prior reset evidence requires manual review")

    rows, receipts = await _preflight(store, session)
    prior_outcomes = [row for row in receipts if row.get("action_type") == OUTCOME_ACTION]
    generation = 1 + max(
        ((row.get("after_state") or {}).get("reset_generation") or 0
         for row in prior_outcomes), default=0,
    )
    before = _snapshot(rows, len(receipts))
    request_id = f"rcpt:{reset_id}:request"
    request = _receipt(
        REQUEST_ACTION, request_id, reset_id, operator, authority, generation,
        before, before, when,
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
            raise CommunityResetError(f"{name} changed after preflight; reset rolled back")
        deleted[name] = result.deleted_count

    after = {
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "counts": {name: 0 for name in RESET_COLLECTIONS},
        "preserved_receipts": len(receipts) + 2,
    }
    outcome_id = f"rcpt:{reset_id}:outcome"
    outcome = _receipt(
        OUTCOME_ACTION, outcome_id, reset_id, operator, authority, generation,
        before, after, when, parent=request_id,
    )
    await store.receipts.insert_one(outcome, session=session)
    return {"reset_id": reset_id, "reset_generation": generation,
            "idempotent_replay": False, "receipt_id": outcome_id, "deleted": deleted}


async def reset_living_community(
    operator: ActorContext,
    authority: str,
    reset_key: str,
    *,
    store=None,
    now: Optional[datetime] = None,
) -> dict:
    """Reset exact living-community rows in one required database transaction."""
    try:
        _require_operator(operator, authority)
    except ProvisioningError as exc:
        raise CommunityResetError(str(exc)) from exc
    reset_id = _reset_id(reset_key)
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise CommunityResetError("reset timestamp must be timezone-aware")
    selected = store or _default_store()
    client = getattr(selected, "client", None)
    if client is None or not callable(getattr(client, "start_session", None)):
        raise CommunityResetError("transaction-capable database session is required")
    try:
        async with await client.start_session() as session:
            async with session.start_transaction():
                return await _perform(
                    selected, session, operator, authority, reset_id,
                    instant.astimezone(timezone.utc),
                )
    except CommunityResetError:
        raise
    except Exception as exc:
        raise CommunityResetError("reset transaction failed and was rolled back") from exc
