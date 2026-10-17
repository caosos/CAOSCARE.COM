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
import uuid

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


def session_purpose(room=None, owner=False):
    """What a Realtime session is for, as reports name it."""
    if owner:
        return "owner_aria"
    return "room214_conversation" if str(room or "") == "214" else "resident_conversation"


def _session_origin(session_id):
    """Purpose and room of a session, from its own mint receipt (the page's events carry neither)."""
    m = ledger().db.receipts.find_one({"kind": "session_token_minted", "session_id": session_id},
                                      {"provenance.purpose": 1, "provenance.room": 1}) if session_id else None
    p = (m or {}).get("provenance") or {}
    return p.get("purpose") or "realtime_conversation", p.get("room")


async def record_diagnostic(event_type, session_id, response_id, meta, room=None):
    """Called for every room-page diagnostic event; only billing-relevant ones become receipts."""
    meta = meta or {}
    if event_type not in ("response_done", "transcription_usage", "session_ended"):
        return
    if meta.get("transport") == "cascade" and event_type != "session_ended":
        return   # the low-cost voice transport's provider calls are receipted where they are made (routes/aria_voice.py)
    origin = await _safe(_session_origin, session_id) or ("realtime_conversation", None)
    room = room or origin[1]
    if event_type == "response_done":
        # The page names its provider ("openai"); a self-test names itself and is never an OpenAI charge.
        await _safe(ledger().record_usage, provider=meta.get("provider") or "openai", provider_response_id=response_id,
                    usage=meta.get("usage"), model_requested=meta.get("model"),
                    model_provider=meta.get("provider_model"), status=meta.get("status"),
                    session_id=session_id, provider_session_id=meta.get("provider_session_id"),
                    transport=meta.get("transport"), provenance=L.provenance(origin[0], room=room))
    elif event_type == "transcription_usage":
        # Input-audio transcription inside the session is billed separately; missing usage stays unknown.
        await _safe(ledger().record_usage, provider=meta.get("provider") or "openai",
                    provider_response_id=f"transcription:{response_id}" if response_id else None,
                    usage=meta.get("usage"), model_requested=meta.get("model"), model_provider=meta.get("model"),
                    status="completed", session_id=session_id, provider_session_id=meta.get("provider_session_id"),
                    provenance=L.provenance("speech_transcription", room=room, conversation_purpose=origin[0]))
    elif event_type == "session_ended":
        await _safe(ledger().record, "session_ended", session_id=session_id, reason=meta.get("reason"),
                    provenance=L.provenance(origin[0], room=room))
        r = await _safe(ledger().db.reservations.find_one, {"session_id": session_id, "status": "open"})
        if r:
            await _safe(ledger().budget.close, r["reservation_id"], meta.get("reason") or "session_ended")


# -- paid HTTP requests (chat / Responses / transcription / speech) ----------------------------------------------

def _json(resp):
    try:
        ctype = (getattr(resp, "headers", None) or {}).get("content-type", "")
        return resp.json() if resp is not None and "json" in ctype else {}
    except Exception:   # noqa: BLE001
        return {}


def now_iso():
    return L.now().isoformat()


def record_request(resp, *, purpose, endpoint, model_requested, started_at, key, attempt=1, retry_of=None,
                   failure=None, chars=None, session_id=None, body=None, **where):
    """One receipt per paid HTTP request, successful or not. Sync - call it from the thread that made the
    request. Keeps the provider's own usage; with none, the estimate (if any) comes from what we sent (chars)
    and says so. Never stores request/response content or provider error bodies - only an error type/code.
    `body`: for a streamed response, the {id, model, usage} gathered from its chunks (the stream has no JSON body)."""
    try:
        body = body if body is not None else _json(resp) if resp is not None else {}
        body = body if isinstance(body, dict) else {}
        err = body.get("error") if isinstance(body.get("error"), dict) else {}
        out = body.get("output") if isinstance(body.get("output"), list) else []
        calls = sum(1 for o in out if isinstance(o, dict) and o.get("type") == "web_search_call")
        rid = body.get("id") or (getattr(resp, "headers", None) or {}).get("x-request-id") or f"local_{uuid.uuid4().hex}"
        ledger().record_usage(
            kind="provider_request", provider="openai", provider_response_id=rid, usage=body.get("usage"),
            model_requested=model_requested, model_provider=body.get("model"),
            status=getattr(resp, "status_code", None) or "error", session_id=session_id,
            endpoint=endpoint, key_id=L.key_id(key), started_at=started_at, ended_at=L.now().isoformat(),
            attempt=attempt, retry_of=retry_of, failure=failure or err.get("code") or err.get("type"),
            pricing_inputs={k: v for k, v in (("chars", chars), ("search_calls", calls)) if v},
            provenance=L.provenance(purpose, **where), **_headers(resp))
    except Exception as e:   # noqa: BLE001 - evidence must never break the request it describes
        log.error(f"paid API receipt NOT written ({purpose} {endpoint}): {e}")


async def record_request_async(resp, **kw):
    await asyncio.to_thread(record_request, resp, **kw)


# -- backend-held Realtime sockets (phone bridge) -----------------------------------------------------------

async def record_phone_call(resp_status, *, path, model, started_at, key):
    """`/realtime/calls/{id}/accept` starts a billable phone session; reject/refer/hangup are free control.
    The provider call id joins to the CAOSCare call through db.call_sessions.openai_call_id."""
    accept = path.endswith("/accept")
    await _safe(ledger().record, "session_connected" if accept else "provider_control", provider="openai",
                endpoint=path.split("/")[-1], provider_call_id=path.split("/")[-2] if path.count("/") >= 3 else L.UNKNOWN,
                model_requested=model or L.UNKNOWN, status=resp_status or "error",
                billable_activity=bool(accept and resp_status and resp_status < 300), key_id=L.key_id(key),
                started_at=started_at, ended_at=L.now().isoformat(), provenance=L.provenance("phone_aria"))


async def record_realtime_event(msg, *, session_id, purpose, model, state):
    """Usage carried by provider events on a socket the backend holds itself (no page in between)."""
    t = msg.get("type")
    if t in ("session.created", "session.updated"):
        state["provider_session"] = (msg.get("session") or {}).get("id") or state.get("provider_session")
        state["provider_model"] = (msg.get("session") or {}).get("model") or state.get("provider_model")
    elif t == "response.done":
        r = msg.get("response") or {}
        await _safe(ledger().record_usage, provider="openai", provider_response_id=r.get("id"), usage=r.get("usage"),
                    model_requested=model, model_provider=state.get("provider_model"), status=r.get("status"),
                    session_id=session_id, provider_session_id=state.get("provider_session"),
                    provenance=L.provenance(purpose))
    elif t == "conversation.item.input_audio_transcription.completed":
        item = msg.get("item_id")
        await _safe(ledger().record_usage, provider="openai",
                    provider_response_id=f"transcription:{item}" if item else None, usage=msg.get("usage"),
                    model_requested="gpt-4o-transcribe", model_provider="gpt-4o-transcribe", status="completed",
                    session_id=session_id, provider_session_id=state.get("provider_session"),
                    provenance=L.provenance("speech_transcription", conversation_purpose=purpose))

