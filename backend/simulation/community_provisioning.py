"""Receipt-backed provisioning of the ten-resident community burn-in.

This is the canonical write boundary for blueprint residents.  It preflights
every stable resident id, room, and pendant before the first insert, refuses
anything ambiguous, then creates only canonical ``db.residents`` rows.  It
never creates staff accounts; simulated workers remain ActorContext profiles.

The store, receipt writer, and resident document factory are injectable so the
safety behavior can be proven without a database.  Production defaults use the
existing Mongo store, Resident model, and shared receipt service.
"""
from typing import Awaitable, Callable, Optional
import uuid

from routes.actor_context import ActorContext
from simulation.community_blueprint import (
    BURN_IN_RESIDENTS,
    COMMUNITY_ID,
    SIMULATION_SCOPE,
    ResidentRecipe,
)


PROVISION_ACTION = "simulation_resident_provisioned"
RECONCILE_ACTION = "simulation_resident_reconciled"
RECEIPT_ACTIONS = (PROVISION_ACTION, RECONCILE_ACTION)
ADMIN_ROLES = ("owner", "admin")


class ProvisioningError(RuntimeError):
    """Provisioning cannot proceed without risking real or ambiguous data."""


def _require_operator(operator: ActorContext, authority: str) -> None:
    if (
        operator.actor_type != "real-human"
        or operator.identity_basis != "authenticated"
        or operator.simulated
        or operator.role not in ADMIN_ROLES
    ):
        raise ProvisioningError("an authenticated real owner or admin must provision burn-in residents")
    if authority != f"admin_override:{operator.role}":
        raise ProvisioningError("provisioning authority must match the authenticated operator role")


def _marked_for_blueprint(doc: dict, recipe: ResidentRecipe) -> bool:
    return all(
        (
            doc.get("resident_id") == recipe.resident_id,
            doc.get("room") == recipe.room,
            doc.get("pendant_id") == recipe.pendant_id,
            doc.get("synthetic") is True,
            doc.get("simulation_scope") == SIMULATION_SCOPE,
            doc.get("simulation_community_id") == COMMUNITY_ID,
        )
    )


def _state(doc: dict) -> dict:
    return {
        key: doc.get(key)
        for key in (
            "resident_id",
            "room",
            "pendant_id",
            "synthetic",
            "simulation_scope",
            "simulation_community_id",
        )
    }


async def _collision(store, recipe: ResidentRecipe) -> Optional[dict]:
    """Return the one record occupying any stable identity, refusing splits."""
    hits = await store.residents.find(
        {"$or": [
            {"resident_id": recipe.resident_id},
            {"room": recipe.room},
            {"pendant_id": recipe.pendant_id},
        ]},
        {"_id": 0},
    ).to_list(20)
    if len(hits) > 1:
        raise ProvisioningError(
            f"split identity collision for {recipe.resident_id}: id, room, or pendant belong to different residents"
        )
    return hits[0] if hits else None


async def _existing_receipt(store, resident_id: str) -> Optional[dict]:
    receipts = await store.receipts.find(
        {
            "related_object_type": "resident",
            "related_object_id": resident_id,
            "action_type": {"$in": list(RECEIPT_ACTIONS)},
            "actor_type": "real-human",
            "identity_basis": "authenticated",
            "result_label": "simulated",
        },
        {"_id": 0},
    ).to_list(50)
    return next(
        (
            receipt
            for receipt in receipts
            if (receipt.get("after_state") or {}).get("simulation_scope") == SIMULATION_SCOPE
            and (receipt.get("after_state") or {}).get("simulation_community_id") == COMMUNITY_ID
        ),
        None,
    )


def _default_document(recipe: ResidentRecipe) -> dict:
    from models import Resident

    doc = Resident(**recipe.resident_payload()).model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc.update(
        simulation_scope=SIMULATION_SCOPE,
        simulation_community_id=COMMUNITY_ID,
        simulation_apartment_id=recipe.apartment_id,
        occupant_slot=recipe.occupant_slot,
    )
    return doc


async def _default_receipt_writer(**kwargs) -> dict:
    from routes.receipts import create_receipt

    return await create_receipt(**kwargs)


def _default_store():
    from deps import db

    return db


async def _write_receipt(
    writer: Callable[..., Awaitable[dict]], operator: ActorContext, authority: str,
    doc: dict, *, created: bool,
) -> dict:
    receipt_id = f"rcpt_{uuid.uuid4().hex[:12]}"
    state = _state(doc)
    return await writer(
        action_type=PROVISION_ACTION if created else RECONCILE_ACTION,
        related_object_type="resident",
        related_object_id=doc["resident_id"],
        source="staff",
        resident_id=doc["resident_id"],
        room=doc["room"],
        status="completed",
        result="created synthetic burn-in resident" if created else "reconciled existing synthetic burn-in resident",
        receipt_id=receipt_id,
        provenance={
            **operator.receipt_fields(),
            "authority": authority,
            "correlation_id": receipt_id,
            "before_state": None if created else state,
            "after_state": state,
            "result_label": "simulated",
            "next_state": "ready_for_burn_in",
        },
    )


async def provision_burn_in_residents(
    operator: ActorContext,
    authority: str,
    *,
    store=None,
    receipt_writer: Optional[Callable[..., Awaitable[dict]]] = None,
    document_factory: Optional[Callable[[ResidentRecipe], dict]] = None,
) -> dict:
    """Create or reuse exactly ten marked canonical resident records.

    All identities are checked before any mutation.  A matching, fully marked
    resident is reused; any unmarked or partially matching record is a hard
    stop.  Existing provisioning receipts are reused, and a marked legacy row
    without one receives a reconciliation receipt rather than a false creation
    claim.
    """
    _require_operator(operator, authority)
    store = store or _default_store()
    receipt_writer = receipt_writer or _default_receipt_writer
    document_factory = document_factory or _default_document
    recipes = tuple(BURN_IN_RESIDENTS)
    if len(recipes) != 10:
        raise ProvisioningError("burn-in blueprint must contain exactly 10 residents")

    existing_by_id = {}
    for recipe in recipes:
        existing = await _collision(store, recipe)
        if existing and not _marked_for_blueprint(existing, recipe):
            raise ProvisioningError(
                f"resident identity collision for {recipe.resident_id}; existing data was not changed"
            )
        existing_by_id[recipe.resident_id] = existing

    created_ids, reused_ids, receipts = [], [], []
    for recipe in recipes:
        existing = existing_by_id[recipe.resident_id]
        if existing:
            doc = existing
            reused_ids.append(recipe.resident_id)
        else:
            doc = document_factory(recipe)
            doc.update(
                synthetic=True,
                simulation_scope=SIMULATION_SCOPE,
                simulation_community_id=COMMUNITY_ID,
            )
            if not _marked_for_blueprint(doc, recipe):
                raise ProvisioningError(
                    f"resident document factory changed a stable identity for {recipe.resident_id}"
                )
            await store.residents.insert_one(dict(doc))
            created_ids.append(recipe.resident_id)

        # A newly inserted generation always gets a fresh creation receipt.
        # Historical receipts survive cleanup and must never be reused as
        # evidence for a later insert of the same stable blueprint identity.
        receipt = None if existing is None else await _existing_receipt(store, recipe.resident_id)
        if not receipt:
            receipt = await _write_receipt(
                receipt_writer, operator, authority, doc, created=existing is None
            )
        receipts.append(receipt)

    return {
        "community_id": COMMUNITY_ID,
        "resident_ids": [recipe.resident_id for recipe in recipes],
        "created_ids": created_ids,
        "reused_ids": reused_ids,
        "receipts": receipts,
    }
