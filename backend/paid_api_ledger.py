"""Paid API ledger: one durable receipt per paid provider request, and an application-level budget guard for
paid tests (owner cost directive 2026-10-16/17, aria-owner-conversation-001).

Why: a ~$32 provider bill could not be attributed from local evidence - the only usage records lived in
db.realtime_diagnostics of whichever database a backend happened to use, scratch seed resets erased them, and
text probes kept none at all. This module is the one source of truth for "who spent what on which model".

Storage is its own database (CAOSCARE_LEDGER_DB, default caoscare_paid_api_ledger), never DB_NAME, so test
cleanup, gate database drops and scratch seed resets cannot touch it.
  receipts      append-only. This module only ever inserts; nothing here updates or deletes a receipt.
  budgets       mutable state of one owner-opened test budget (cap, reserved, spent, unknown, open).
  reservations  mutable state of one bounded paid test session against a budget.
Receipts never hold credentials, raw audio or conversation text - only ids, models, counters and statuses.

Three amounts are never mixed: `usage` is exactly what the provider reported (None = unknown, never 0);
`estimate` is calculated from that usage at PRICING (named version); provider-billed charges are only ever
recorded by reconcile_unknown()/record(kind="provider_billing", ...) from a provider export.

The budget guard for paid tests lives in paid_api_budget.py (ledger.budget); a live room is receipted,
never blocked by it.

Sync pymongo on purpose: the probe scripts and the backend share this code; the backend calls it through
asyncio.to_thread (routes/paid_api_receipts.py).
"""
import hashlib
import os
import socket
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pymongo
from pymongo.errors import DuplicateKeyError

# USD per 1M tokens: developers.openai.com/api/docs/pricing as read 2026-10-17. A new price is a new version.
PRICING_VERSION = "openai-public-2026-10-17"
_MINI = dict(text_in=0.60, text_cached=0.06, text_out=2.40, audio_in=10.00, audio_cached=0.30, audio_out=20.00)
_GA = dict(text_in=4.00, text_cached=0.40, text_out=16.00, audio_in=32.00, audio_cached=0.40, audio_out=64.00)
PRICES = {
    "gpt-realtime-2.1-mini": _MINI, "gpt-realtime-mini": _MINI,
    "gpt-realtime-2.1": dict(_GA, text_out=24.00),
    "gpt-realtime": _GA, "gpt-realtime-2025-08-28": _GA,
}
UNKNOWN = "unknown"
STALE_GRACE_S = 300   # a reservation still open this long after its own deadline is stale: its usage is unknown


def now():
    return datetime.now(timezone.utc)


def key_id(key):
    """Safe key identifier: a fingerprint, never the key or any part of it."""
    return "keyfp_" + hashlib.sha256((key or "").encode()).hexdigest()[:12] if key else UNKNOWN


def provenance(purpose, **extra):
    """Who started this request: run/test/process, from the environment the caller runs in."""
    return {
        "purpose": purpose,
        "run_id": os.environ.get("CAOSCARE_RUN_ID") or UNKNOWN,
        "run_purpose": os.environ.get("CAOSCARE_RUN_PURPOSE") or UNKNOWN,   # e.g. live, scratch-acceptance, probe
        "test": os.environ.get("PYTEST_CURRENT_TEST") or None,
        "db_name": os.environ.get("DB_NAME") or None,
        "runtime_sha": os.environ.get("CAOSCARE_RUNTIME_SHA") or None,
        "host": socket.gethostname(), "pid": os.getpid(), "process": os.path.basename(sys.argv[0] or "") or None,
        **extra,
    }


def _usage_parts(usage):
    """Provider usage -> billable parts. None when usage is missing or any counter in it is (unknown, not zero)."""
    if not isinstance(usage, dict):
        return None
    i = usage.get("input_token_details") or {}
    c = i.get("cached_tokens_details") or {}
    o = usage.get("output_token_details") or {}
    raw = dict(text=i.get("text_tokens"), cached_text=c.get("text_tokens"), audio=i.get("audio_tokens"),
               cached_audio=c.get("audio_tokens"), text_out=o.get("text_tokens"), audio_out=o.get("audio_tokens"))
    if any(not isinstance(v, int) or v < 0 for v in raw.values()):
        return None
    return dict(text_in=raw["text"] - raw["cached_text"], text_cached=raw["cached_text"],
                audio_in=raw["audio"] - raw["cached_audio"], audio_cached=raw["cached_audio"],
                text_out=raw["text_out"], audio_out=raw["audio_out"])


def estimate_usd(model, usage):
    """Calculated cost of reported usage at PRICING_VERSION; None when usage or the model's price is unknown."""
    parts, price = _usage_parts(usage), PRICES.get(model or "")
    if parts is None or price is None:
        return None
    return round(sum(parts[k] * price[k] for k in parts) / 1e6, 8)


def worst_case_usd(model, max_responses, max_text_input_tokens, max_audio_input_tokens, max_output_tokens):
    """Reservation for a bounded session: every response at its input bounds with nothing cached, every output
    token priced as audio. Risk not covered: a runner that does not enforce its own bounds, provider-side
    behaviour beyond them (e.g. a session left open past max_session_seconds), or a price change."""
    p = PRICES.get(model or "")
    if p is None or any(not isinstance(v, int) or v <= 0 for v in
                        (max_responses, max_text_input_tokens, max_audio_input_tokens, max_output_tokens)):
        return None
    per = (max_text_input_tokens * p["text_in"] + max_audio_input_tokens * p["audio_in"]
           + max_output_tokens * max(p["audio_out"], p["text_out"])) / 1e6
    return round(per * max_responses, 8)


class PaidApiLedger:
    def __init__(self, mongo_url=None, db_name=None):
        url = mongo_url or os.environ.get("MONGO_URL") or "mongodb://localhost:27017"
        self.db = pymongo.MongoClient(url)[db_name or os.environ.get("CAOSCARE_LEDGER_DB") or "caoscare_paid_api_ledger"]
        r = self.db.receipts
        r.create_index("receipt_id", unique=True)
        # One counted receipt per provider usage event; repeats are kept, flagged and never counted.
        r.create_index("dedupe_key", unique=True, partialFilterExpression={"counted": True})
        r.create_index([("session_id", 1), ("recorded_at", 1)])
        from paid_api_budget import PaidTestBudget   # the budget module reads this one's prices
        self.budget = PaidTestBudget(self)

    # -- receipts (insert only) -------------------------------------------------------------------------
    def record(self, kind, **fields):
        doc = {"receipt_id": "rcpt_" + uuid.uuid4().hex, "kind": kind, "recorded_at": now().isoformat(),
               "pricing_version": PRICING_VERSION, **fields}
        self.db.receipts.insert_one(doc)
        return doc["receipt_id"]

    def record_usage(self, *, provider, provider_response_id, usage, model_requested, model_provider,
                     status, session_id=None, provider_session_id=None, provenance=None, **extra):
        """One provider usage event (e.g. a Realtime response.done). Counted once per provider response id;
        a repeat is kept as counted=False with duplicate_of. Missing usage stays unknown and marks the
        session's reservation, which then blocks further paid tests until reconciled."""
        model = model_provider or model_requested
        fields = dict(provider=provider, provider_response_id=provider_response_id or UNKNOWN,
                      session_id=session_id, provider_session_id=provider_session_id or UNKNOWN,
                      model_requested=model_requested or UNKNOWN, model_provider=model_provider or UNKNOWN,
                      status=status or UNKNOWN, usage=usage if isinstance(usage, dict) else None,
                      usage_status=("reported" if _usage_parts(usage) else "incomplete") if isinstance(usage, dict) else UNKNOWN,
                      estimate={"usd": estimate_usd(model, usage), "pricing_version": PRICING_VERSION},
                      billable_activity=True if isinstance(usage, dict) else UNKNOWN,
                      provenance=provenance or {}, **extra)
        key = f"{provider}:response:{provider_response_id}" if provider_response_id else None
        try:
            rid = self.record("provider_usage", dedupe_key=key, counted=key is not None, **fields)
        except DuplicateKeyError:
            first = self.db.receipts.find_one({"dedupe_key": key, "counted": True}, {"receipt_id": 1})
            rid = self.record("provider_usage", dedupe_key=key, counted=False,
                              duplicate_of=(first or {}).get("receipt_id"), **fields)
            return {"receipt_id": rid, "counted": False, "duplicate_of": (first or {}).get("receipt_id")}
        if key is None:   # no provider id: kept, but it cannot be deduplicated, so it is never counted
            self.budget.mark_unknown(session_id)
            return {"receipt_id": rid, "counted": False, "duplicate_of": None}
        self.budget.settle(session_id, fields["estimate"]["usd"], unknown=fields["usage_status"] != "reported",
                           usage=fields["usage"])
        return {"receipt_id": rid, "counted": True, "duplicate_of": None}
