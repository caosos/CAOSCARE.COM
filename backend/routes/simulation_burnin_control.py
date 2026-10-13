"""Guarded manual control for P1A burn-in resident provisioning.

This router is intentionally separate from the existing simulator routes. It
does not start/resume a run, schedule an event, call a provider, or enable an
autonomous loop. A request defaults to a canonical dry-run. The only mutation
requires an authenticated owner/admin, a PAUSED run, and a short-lived signed
confirmation token bound to that operator, run and exact preflight digest.

The coordinator must explicitly register this router; importing this module
alone exposes no endpoint and performs no work.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
import jwt
from pydantic import BaseModel

from deps import db, require_admin
from routes.actor_context import actor_from_user
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE


router = APIRouter(prefix="/simulator/community/burn-in", tags=["simulator"])
PAUSED = "PAUSED"
TOKEN_TYPE = "p1a_burn_in_confirmation"
TOKEN_AUDIENCE = "caoscare-p1a-burn-in"
TOKEN_ISSUER = "caoscare"
TOKEN_TTL_SECONDS = 5 * 60
ALGORITHM = "HS256"
EXECUTION_FLAG = "CAOSCARE_COMMUNITY_BURNIN_EXECUTION"


class ProvisionControl(BaseModel):
    run_id: str
    execute: bool = False
    confirmation_token: Optional[str] = None


def _operator(user: dict):
    return actor_from_user(user, channel="staff_ui"), f"admin_override:{user['role']}"


async def _paused_run(run_id: str, store=None) -> dict:
    row = await (store or db).sim_runs.find_one({"run_id": run_id}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    if row.get("state") != PAUSED:
        raise HTTPException(
            status_code=409,
            detail=f"Burn-in provisioning requires a PAUSED run; this run is {row.get('state') or 'unknown'}",
        )
    if (
        row.get("simulation_scope") != SIMULATION_SCOPE
        or row.get("simulation_community_id") != COMMUNITY_ID
    ):
        raise HTTPException(status_code=409, detail="Run is not bound to the living-community burn-in")
    return row


class _CaptureInserts:
    """Delegate every read and capture inserts without touching the store."""

    def __init__(self, collection):
        self.collection = collection
        self.inserted = []

    def find(self, *args, **kwargs):
        return self.collection.find(*args, **kwargs)

    async def find_one(self, *args, **kwargs):
        return await self.collection.find_one(*args, **kwargs)

    async def insert_one(self, doc):
        self.inserted.append(deepcopy(doc))
        return object()


class _DryRunStore:
    def __init__(self, store):
        self.residents = _CaptureInserts(store.residents)
        self.receipts = store.receipts


def _digest(plan: dict) -> str:
    bound = {
        "community_id": plan["community_id"],
        "created_ids": plan["created_ids"],
        "reused_ids": plan["reused_ids"],
        "new_receipt_targets": plan["new_receipt_targets"],
    }
    raw = json.dumps(bound, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


async def _preflight(operator, authority: str, store=None) -> dict:
    """Run the canonical provisioner against insert-capturing seams."""
    from simulation.community_provisioning import provision_burn_in_residents

    source = store or db
    dry_store = _DryRunStore(source)
    proposed_receipts = []

    async def capture_receipt(**kwargs):
        proposed_receipts.append(deepcopy(kwargs))
        return {**kwargs, **deepcopy(kwargs.get("provenance") or {})}

    result = await provision_burn_in_residents(
        operator,
        authority,
        store=dry_store,
        receipt_writer=capture_receipt,
    )
    return {
        "community_id": result["community_id"],
        "resident_count": len(result["resident_ids"]),
        "created_ids": result["created_ids"],
        "reused_ids": result["reused_ids"],
        "new_receipt_targets": [r["related_object_id"] for r in proposed_receipts],
        "writes_planned": len(dry_store.residents.inserted) + len(proposed_receipts),
    }


async def _execute_provision(operator, authority: str) -> dict:
    from simulation.community_provisioning import provision_burn_in_residents

    return await provision_burn_in_residents(operator, authority)


def _secret() -> str:
    value = os.environ.get("JWT_SECRET", "")
    if not value:
        raise HTTPException(status_code=503, detail="Confirmation signing is not configured")
    return value


def _issue_confirmation(user: dict, run_id: str, plan_digest: str) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=TOKEN_TTL_SECONDS)
    claims = {
        "token_type": TOKEN_TYPE,
        "sub": user["user_id"],
        "principal_role": user["role"],
        "run_id": run_id,
        "plan_digest": plan_digest,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "aud": TOKEN_AUDIENCE,
        "iss": TOKEN_ISSUER,
    }
    return jwt.encode(claims, _secret(), algorithm=ALGORITHM), expires.isoformat()


def _verify_confirmation(token: Optional[str], user: dict, run_id: str, plan_digest: str) -> None:
    if not token:
        raise HTTPException(status_code=409, detail="A fresh preflight confirmation token is required")
    try:
        claims = jwt.decode(
            token,
            _secret(),
            algorithms=[ALGORITHM],
            audience=TOKEN_AUDIENCE,
            issuer=TOKEN_ISSUER,
            options={"require": ["sub", "principal_role", "run_id", "plan_digest", "iat", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=409, detail="Confirmation token expired; run preflight again") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=403, detail="Invalid confirmation token") from exc
    expected = {
        "token_type": TOKEN_TYPE,
        "sub": user.get("user_id"),
        "principal_role": user.get("role"),
        "run_id": run_id,
        "plan_digest": plan_digest,
    }
    if any(claims.get(key) != value for key, value in expected.items()):
        raise HTTPException(status_code=409, detail="Confirmation no longer matches this operator, run or preflight")


@router.post("/provision")
async def provision_control(body: ProvisionControl, user=Depends(require_admin)):
    """Dry-run by default; execute only the exact freshly confirmed plan."""
    await _paused_run(body.run_id)
    operator, authority = _operator(user)
    try:
        plan = await _preflight(operator, authority)
    except Exception as exc:
        from simulation.community_provisioning import ProvisioningError

        if isinstance(exc, ProvisioningError):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise
    plan_digest = _digest(plan)

    if not body.execute:
        token, expires_at = _issue_confirmation(user, body.run_id, plan_digest)
        return {
            "dry_run": True,
            "executed": False,
            "autonomous_execution": False,
            "provider_calls": False,
            "execution_enabled": os.environ.get(EXECUTION_FLAG, "").strip().lower() == "true",
            "run_id": body.run_id,
            "run_state": PAUSED,
            "plan": plan,
            "plan_digest": plan_digest,
            "confirmation_token": token,
            "confirmation_expires_at": expires_at,
            "message": "Preflight only. No residents or receipts were written.",
        }

    _verify_confirmation(body.confirmation_token, user, body.run_id, plan_digest)
    if os.environ.get(EXECUTION_FLAG, "").strip().lower() != "true":
        raise HTTPException(
            status_code=409,
            detail=f"Manual burn-in execution is disabled; {EXECUTION_FLAG}=true is required",
        )
    await _paused_run(body.run_id)
    # The canonical service repeats every collision/marker check immediately
    # before its own writes; the digest check above additionally rejects a
    # changed plan since preflight.
    try:
        result = await _execute_provision(operator, authority)
    except Exception as exc:
        from simulation.community_provisioning import ProvisioningError

        if isinstance(exc, ProvisioningError):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise
    return {
        "dry_run": False,
        "executed": True,
        "autonomous_execution": False,
        "provider_calls": False,
        "execution_enabled": True,
        "run_id": body.run_id,
        "run_state": PAUSED,
        "community_id": result["community_id"],
        "created_ids": result["created_ids"],
        "reused_ids": result["reused_ids"],
        "receipt_ids": [r.get("receipt_id") for r in result["receipts"]],
    }
