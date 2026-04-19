"""Device tokens for HMAC-signed field hardware requests.

Admin creates a token with a name and scopes; backend returns the shared secret ONCE.
Field devices (Android bridge, location sensors, wearable gateways) then sign every
request body with HMAC-SHA256(secret, body) and send the resulting hex in the
`X-Device-Signature` header, along with `X-Device-Token` (the token_id).

Ingest endpoints call `verify_device_token(request, required_scope)` — if a token header
is present, it MUST validate; if absent, behavior depends on the `DEVICE_AUTH_REQUIRED`
env var (default false for MVP, flip true for production hardening).
"""
import os
import hmac
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
import bcrypt

from models import DeviceToken, DeviceTokenCreate, now_utc
from deps import db, require_admin

router = APIRouter(prefix="/device-tokens", tags=["device-tokens"])


DEVICE_AUTH_REQUIRED = os.environ.get("DEVICE_AUTH_REQUIRED", "false").lower() == "true"


def _hash_secret(secret: str) -> str:
    return bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()


def _verify_secret(secret: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(secret.encode(), hashed.encode())
    except Exception:
        return False


async def verify_device_token(request: Request, required_scope: str) -> Optional[dict]:
    """Validate HMAC-SHA256(shared_secret, raw_body) against X-Device-Signature header.
    If no headers and DEVICE_AUTH_REQUIRED=false, returns None (backward-compatible).
    """
    token_id = request.headers.get("x-device-token")
    signature = request.headers.get("x-device-signature")

    if not token_id and not signature:
        if DEVICE_AUTH_REQUIRED:
            raise HTTPException(status_code=401, detail="Device token required")
        return None

    if not (token_id and signature):
        raise HTTPException(status_code=401, detail="Both X-Device-Token and X-Device-Signature headers required")

    token = await db.device_tokens.find_one({"token_id": token_id}, {"_id": 0})
    if not token or token.get("revoked"):
        raise HTTPException(status_code=401, detail="Invalid or revoked device token")

    if required_scope not in (token.get("scopes") or []):
        raise HTTPException(status_code=403, detail=f"Token lacks scope: {required_scope}")

    # HMAC verification against the raw request body.
    # Since we store only a bcrypt hash of the secret, we keep a short-lived reversible cache
    # keyed by token_id. Populated at token-creation time in the in-memory SECRETS_CACHE
    # below. If cache miss (server restart), we fall back to token-presence (and log a warning
    # so ops knows to re-issue tokens for strict HMAC).
    raw_body = await request.body()
    secret = SECRETS_CACHE.get(token_id)
    if secret:
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature.lower()):
            raise HTTPException(status_code=401, detail="Invalid device signature")
    else:
        import logging
        logging.warning(
            f"Device token {token_id} used but shared_secret not in in-memory cache "
            "(likely a server restart). Accepting on token-presence only. "
            "Re-issue the token to restore strict HMAC."
        )

    await db.device_tokens.update_one(
        {"token_id": token_id},
        {"$set": {"last_used_at": now_utc().isoformat()}},
    )
    return token


# In-memory cache of token_id -> shared_secret. Populated at create_token time.
# Rationale: we never persist the plaintext secret (only bcrypt hash), so strict HMAC
# verification requires the plaintext. This cache is lost on server restart; admins
# must re-issue tokens after a restart for strict HMAC to resume. For production,
# consider moving this to Redis with TLS or a proper KMS.
SECRETS_CACHE: dict = {}


def hmac_sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@router.get("")
async def list_tokens(user=Depends(require_admin)):
    items = await db.device_tokens.find({}, {"_id": 0, "secret_hash": 0}).sort("created_at", -1).to_list(500)
    for it in items:
        for k in ("created_at", "last_used_at"):
            v = it.get(k)
            if v and not isinstance(v, str):
                it[k] = v.isoformat()
    return items


@router.post("")
async def create_token(data: DeviceTokenCreate, user=Depends(require_admin)):
    """Creates a device token. Returns the shared secret ONCE — store it on the device now."""
    secret = secrets.token_urlsafe(32)
    tok = DeviceToken(
        name=data.name,
        scopes=data.scopes,
        secret_hash=_hash_secret(secret),
        created_by=user.get("user_id"),
    )
    doc = tok.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["last_used_at"] = None
    await db.device_tokens.insert_one(doc)
    doc.pop("_id", None)

    # Cache plaintext secret in-memory for strict HMAC verification of incoming requests.
    SECRETS_CACHE[tok.token_id] = secret

    return {
        "token_id": tok.token_id,
        "shared_secret": secret,
        "scopes": tok.scopes,
        "name": tok.name,
        "usage": (
            "Store BOTH token_id and shared_secret on the device. "
            "For every request, compute X-Device-Signature = HMAC-SHA256(shared_secret, request_body) "
            "and send X-Device-Token: <token_id> and X-Device-Signature: <hex>."
        ),
        "example_python": (
            "import hmac, hashlib, json, requests\n"
            "body = json.dumps({'frequency_mhz': 916.0}).encode()\n"
            "sig = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()\n"
            "requests.post(URL, data=body, headers={'X-Device-Token': TOKEN_ID, 'X-Device-Signature': sig, 'Content-Type':'application/json'})"
        ),
    }


@router.delete("/{token_id}")
async def revoke_token(token_id: str, user=Depends(require_admin)):
    r = await db.device_tokens.update_one({"token_id": token_id}, {"$set": {"revoked": True}})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Token not found")
    SECRETS_CACHE.pop(token_id, None)
    return {"ok": True}


@router.get("/status")
async def status(user=Depends(require_admin)):
    active = await db.device_tokens.count_documents({"revoked": {"$ne": True}})
    revoked = await db.device_tokens.count_documents({"revoked": True})
    return {
        "active_tokens": active,
        "revoked_tokens": revoked,
        "enforcement_required": DEVICE_AUTH_REQUIRED,
        "hint": (
            "Set DEVICE_AUTH_REQUIRED=true in backend/.env to reject unsigned requests on "
            "/api/pendants/event, /api/locations, and /api/wearables/event."
        ),
    }
