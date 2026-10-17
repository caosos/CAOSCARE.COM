"""Backend side of the paid API ledger (paid_api_ledger.py): receipts for the Realtime requests this backend
makes or hears about, and the paid-test budget gate at session mint. Three moments are kept apart:
  session_token_minted  POST /realtime/client_secrets - creates a token; billable_activity False.
  session_connected     POST /realtime/calls (SDP) - the session goes live; billing can start from here.
  provider_usage        each response.done the room page reports - the provider's usage, as reported.
Mint and connect are linked by a fingerprint of the session's client secret, never the secret itself.

Live rooms are receipted, never blocked: a receipt failure is logged and the call goes on. Paid tests are
the opposite: when CAOSCARE_PAID_TEST_BUDGET_ID is set, a session is minted only after the budget accepted
its worst case (paid_api_budget.py), and any failure refuses the mint (fail closed).
"""
import asyncio
import logging
import os

from fastapi import HTTPException

import paid_api_ledger as L

log = logging.getLogger(__name__)
_ledger = None
_BOUNDS = ("MAX_RESPONSES", "MAX_TEXT_INPUT_TOKENS", "MAX_AUDIO_INPUT_TOKENS", "MAX_OUTPUT_TOKENS", "MAX_SESSION_SECONDS")


def ledger():
    global _ledger
    if _ledger is None:
        _ledger = L.PaidApiLedger()
    return _ledger


async def _safe(fn, *args, **kw):
    """Live path: a receipt failure never touches the call; it is logged loudly instead."""
    try:
        return await asyncio.to_thread(fn, *args, **kw)
    except Exception as e:   # noqa: BLE001 - evidence must never break a resident's call
        log.error(f"paid API receipt NOT written ({getattr(fn, '__name__', fn)}): {e}")
        return None


def _headers(resp):
    h = getattr(resp, "headers", None) or {}
    return {"provider_request_id": h.get("x-request-id") or L.UNKNOWN,
            "provider_organization": h.get("openai-organization") or L.UNKNOWN,
            "provider_project": h.get("openai-project") or L.UNKNOWN}


def test_budget_id():
    return (os.environ.get("CAOSCARE_PAID_TEST_BUDGET_ID") or "").strip() or None


async def reserve_for_test(model, purpose, session_id):
    """Paid tests only: reserve the session's worst case before it is minted, or refuse the mint."""
    budget_id = test_budget_id()
    if not budget_id:
        return None
    bounds = {}
    for name in _BOUNDS:
        raw = os.environ.get(f"CAOSCARE_PAID_TEST_{name}")
        bounds[name.lower()] = int(raw) if raw and raw.isdigit() else None
    try:
        out = await asyncio.to_thread(ledger().budget.reserve, budget_id, model=model,
                                      provenance=L.provenance(purpose, session_id=session_id), **bounds)
    except Exception as e:   # noqa: BLE001 - the guard fails closed
        raise HTTPException(status_code=503, detail=f"Paid test refused: budget guard unavailable ({e})")
    if not out.get("ok"):
        raise HTTPException(status_code=503, detail=f"Paid test refused: {out.get('reason')}")
    return out["reservation_id"]


async def record_mint(resp, *, requested_model, purpose, session_id, started_at, key, reservation_id=None, **where):
    """One receipt per client_secrets attempt, successful or not."""
    body = {}
    try:
        body = resp.json() if resp is not None and resp.status_code < 400 else {}
    except Exception:   # noqa: BLE001
        body = {}
    sess = body.get("session") or {}
    secret = body.get("value") or (body.get("client_secret") or {}).get("value")
    if reservation_id:   # a failed mint never connected: release its reservation
        if resp is not None and resp.status_code < 400:
            await _safe(ledger().budget.bind_session, reservation_id, session_id)
        else:
            await _safe(ledger().budget.close, reservation_id, "mint_failed")
    await _safe(ledger().record, "session_token_minted", provider="openai", endpoint="realtime/client_secrets",
                session_id=session_id, provider_session_id=sess.get("id") or L.UNKNOWN,
                session_secret_fp=L.key_id(secret) if secret else L.UNKNOWN, key_id=L.key_id(key),
                model_requested=requested_model, model_provider=sess.get("model") or L.UNKNOWN,
                status=getattr(resp, "status_code", None) or "error", started_at=started_at,
                ended_at=L.now().isoformat(), expires_at=body.get("expires_at"), billable_activity=False,
                usage=None, usage_status="not_applicable", reservation_id=reservation_id,
                provenance=L.provenance(purpose, **where), **_headers(resp))


async def record_connect(resp, *, ephemeral_key, started_at):
    """The SDP exchange that turns a minted token into a live, billable session."""
    loc = (getattr(resp, "headers", None) or {}).get("location") or ""
    await _safe(ledger().record, "session_connected", provider="openai", endpoint="realtime/calls",
                session_secret_fp=L.key_id(ephemeral_key), provider_call_id=loc.rsplit("/", 1)[-1] or L.UNKNOWN,
                status=getattr(resp, "status_code", None) or "error", started_at=started_at,
                ended_at=L.now().isoformat(), billable_activity=bool(resp is not None and resp.status_code < 400),
                provenance=L.provenance("realtime_connect"), **_headers(resp))


async def record_diagnostic(event_type, session_id, response_id, meta, room=None):
    """Called for every room-page diagnostic event; only billing-relevant ones become receipts."""
    meta = meta or {}
    if event_type == "response_done":
        await _safe(ledger().record_usage, provider="openai", provider_response_id=response_id,
                    usage=meta.get("usage"), model_requested=meta.get("model"),
                    model_provider=meta.get("provider_model"), status=meta.get("status"),
                    session_id=session_id, provider_session_id=meta.get("provider_session_id"),
                    transport=meta.get("transport"), provenance=L.provenance("realtime_response", room=room))
    elif event_type == "session_ended":
        await _safe(ledger().record, "session_ended", session_id=session_id, reason=meta.get("reason"),
                    provenance=L.provenance("realtime_session_end", room=room))
        r = await _safe(ledger().db.reservations.find_one, {"session_id": session_id, "status": "open"})
        if r:
            await _safe(ledger().budget.close, r["reservation_id"], meta.get("reason") or "session_ended")
