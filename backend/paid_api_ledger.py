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

# Prices and estimation live in one place (paid_api_pricing.py); re-exported here for callers.
from paid_api_pricing import PRICING_VERSION, estimate_usd, usage_complete, worst_case_usd, cascade_worst_case_usd  # noqa: E402,F401
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
                     status, session_id=None, provider_session_id=None, provenance=None, kind="provider_usage",
                     pricing_inputs=None, **extra):
        """One provider usage event (e.g. a Realtime response.done). Counted once per provider response id;
        a repeat is kept as counted=False with duplicate_of. Missing usage stays unknown and marks the
        session's reservation, which then blocks further paid tests until reconciled."""
        model = model_provider or model_requested
        fields = dict(provider=provider, provider_response_id=provider_response_id or UNKNOWN,
                      session_id=session_id, provider_session_id=provider_session_id or UNKNOWN,
                      model_requested=model_requested or UNKNOWN, model_provider=model_provider or UNKNOWN,
                      status=status or UNKNOWN, usage=usage if isinstance(usage, dict) else None,
                      usage_status=("reported" if usage_complete(model, usage) else "incomplete") if isinstance(usage, dict) else UNKNOWN,
                      estimate={"usd": estimate_usd(model, usage, **(pricing_inputs or {})), "pricing_version": PRICING_VERSION,
                                "basis": "provider_usage" if usage_complete(model, usage) else
                                         ("request_size" if pricing_inputs else None)},
                      billable_activity=True if isinstance(usage, dict) else UNKNOWN,
                      provenance=provenance or {}, **extra)
        key = f"{provider}:response:{provider_response_id}" if provider_response_id else None
        try:
            rid = self.record(kind, dedupe_key=key, counted=key is not None, **fields)
        except DuplicateKeyError:
            first = self.db.receipts.find_one({"dedupe_key": key, "counted": True}, {"receipt_id": 1})
            rid = self.record(kind, dedupe_key=key, counted=False,
                              duplicate_of=(first or {}).get("receipt_id"), **fields)
            return {"receipt_id": rid, "counted": False, "duplicate_of": (first or {}).get("receipt_id")}
        if key is None:   # no provider id: kept, but it cannot be deduplicated, so it is never counted
            self.budget.mark_unknown(session_id)
            return {"receipt_id": rid, "counted": False, "duplicate_of": None}
        # Known cost: the provider reported usage, or the model is billed by request size alone (tts-1 per
        # character), so what we sent is what is billed. usage_status still says the provider reported nothing.
        known = fields["usage_status"] == "reported" or (fields["estimate"]["basis"] == "request_size"
                                                         and fields["estimate"]["usd"] is not None and not usage)
        self.budget.settle(session_id, fields["estimate"]["usd"], unknown=not known, usage=fields["usage"])
        return {"receipt_id": rid, "counted": True, "duplicate_of": None}
