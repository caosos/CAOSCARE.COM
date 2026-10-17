"""Application-level budget guard for PAID TESTS (not live rooms), on the paid API ledger's database.

A test reserves its worst case before it may start, atomically against an owner-opened budget
(find_one_and_update with the cap inside the filter, so concurrent reservations cannot both pass it).
Refused - and receipted - when: no budget exists (the cap is unknown; none is ever assumed), the budget's
pricing version is not the ledger's, the model has no price, a bound is missing, an earlier session's usage
is unknown or stale, or the worst case would pass the cap. Usage settles reservations as it arrives; unknown
usage keeps the remaining reservation counted and blocks the budget until reconcile_unknown().

Not a provider-side cutoff. Spend can still pass the cap through: a runner that does not stop at its own
bounds (recorded as budget_bound_exceeded, after the fact), a session left open past its deadline (stale ->
unknown, blocks new tests, but its in-flight spend continues until the provider ends it), usage the provider
bills later or never reports to us, or a price change. Only the provider's own project budget/limits and the
billing export can close those gaps.
"""
import uuid
from datetime import timedelta

import pymongo

import paid_api_ledger as L


class PaidTestBudget:
    def __init__(self, ledger):
        self.ledger, self.db = ledger, ledger.db
        self.db.budgets.create_index("budget_id", unique=True)
        self.db.reservations.create_index("reservation_id", unique=True)
        self.db.reservations.create_index("session_id")

    def open_budget(self, budget_id, cap_usd, approved_by):
        """Owner action. The cap is whatever the owner approved; nothing here proposes or defaults one."""
        if not isinstance(cap_usd, (int, float)) or cap_usd <= 0 or not approved_by:
            raise ValueError("a budget needs a positive owner-approved cap and who approved it")
        self.db.budgets.insert_one({"budget_id": budget_id, "cap_usd": float(cap_usd), "approved_by": approved_by,
                                    "pricing_version": L.PRICING_VERSION, "status": "open", "reserved_usd": 0.0,
                                    "spent_usd": 0.0, "unknown_count": 0, "open_count": 0,
                                    "opened_at": L.now().isoformat()})
        self.ledger.record("budget_opened", budget_id=budget_id, cap_usd=float(cap_usd), approved_by=approved_by)

    def reserve(self, budget_id, *, model, max_responses, max_text_input_tokens, max_audio_input_tokens,
                max_output_tokens, max_session_seconds, provenance, retry_of=None):
        """Reserve one bounded paid session's worst case, atomically. Returns {"ok": True, reservation_id,
        reserved_usd} or {"ok": False, reason}. Each retry is its own reservation, linked by retry_of."""
        self._expire_stale(budget_id)
        why = None
        b = self.db.budgets.find_one({"budget_id": budget_id})
        amount = L.worst_case_usd(model, max_responses, max_text_input_tokens, max_audio_input_tokens, max_output_tokens)
        if not b:
            why = "no owner-approved budget exists (the cap is unknown)"
        elif b.get("pricing_version") != L.PRICING_VERSION:
            why = "the budget was priced with a different pricing version"
        elif amount is None:
            why = f"no price for model {model!r} or a bound is missing"
        elif not isinstance(max_session_seconds, int) or max_session_seconds <= 0:
            why = "max_session_seconds is missing"
        elif b.get("unknown_count", 0) > 0:
            why = "an earlier paid session's usage is unknown - reconcile it first"
        if why is None:
            ok = self.db.budgets.find_one_and_update(
                {"budget_id": budget_id, "status": "open", "unknown_count": 0, "pricing_version": L.PRICING_VERSION,
                 "$expr": {"$lte": [{"$add": ["$reserved_usd", "$spent_usd", amount]}, "$cap_usd"]}},
                {"$inc": {"reserved_usd": amount, "open_count": 1}})
            if not ok:
                why = "the worst case would pass the cap"
        if why:
            self.ledger.record("budget_refused", budget_id=budget_id, model_requested=model, reason=why,
                        worst_case_usd=amount, provenance=provenance, retry_of=retry_of)
            return {"ok": False, "reason": why}
        rid = "resv_" + uuid.uuid4().hex
        deadline = L.now() + timedelta(seconds=max_session_seconds)
        self.db.reservations.insert_one({
            "reservation_id": rid, "budget_id": budget_id, "model": model, "status": "open",
            "reserved_usd": amount, "remaining_usd": amount, "spent_usd": 0.0, "overage_usd": 0.0,
            "responses": 0, "max_responses": max_responses, "unknown_usage": False, "session_id": None,
            "deadline": deadline.isoformat(), "retry_of": retry_of})
        self.ledger.record("budget_reserved", budget_id=budget_id, reservation_id=rid, model_requested=model,
                    reserved_usd=amount, deadline=deadline.isoformat(), provenance=provenance, retry_of=retry_of,
                    bounds=dict(max_responses=max_responses, max_text_input_tokens=max_text_input_tokens,
                                max_audio_input_tokens=max_audio_input_tokens, max_output_tokens=max_output_tokens,
                                max_session_seconds=max_session_seconds))
        return {"ok": True, "reservation_id": rid, "reserved_usd": amount}

    def bind_session(self, reservation_id, session_id):
        self.db.reservations.update_one({"reservation_id": reservation_id, "session_id": None},
                                        {"$set": {"session_id": session_id}})

    def close(self, reservation_id, reason):
        """Release what a finished session did not spend. A session whose usage is unknown keeps its whole
        remaining reservation counted and blocks the budget until reconciled. Risk: usage the provider bills
        after close (delayed or never reported to us) is only caught by reconciliation against the export."""
        r = self.db.reservations.find_one_and_update({"reservation_id": reservation_id, "status": "open"},
                                                     {"$set": {"status": "closed", "closed_reason": reason}})
        if not r:
            return False
        inc = {"open_count": -1}
        if r.get("unknown_usage"):
            inc["unknown_count"] = 1
        else:
            inc["reserved_usd"] = -r["remaining_usd"]
        self.db.budgets.update_one({"budget_id": r["budget_id"]}, {"$inc": inc})
        self.ledger.record("budget_closed", budget_id=r["budget_id"], reservation_id=reservation_id, reason=reason,
                    released_usd=0.0 if r.get("unknown_usage") else r["remaining_usd"],
                    unknown_usage=r.get("unknown_usage", False), responses=r.get("responses"))
        return True

    def reconcile_unknown(self, reservation_id, provider_billed_usd, source):
        """Owner/operator action after reading the provider export: replace an unknown with a billed amount."""
        r = self.db.reservations.find_one_and_update(
            {"reservation_id": reservation_id, "unknown_usage": True, "status": {"$in": ["closed", "stale"]}},
            {"$set": {"unknown_usage": False, "reconciled_usd": provider_billed_usd}})
        if not r:
            return False
        self.db.budgets.update_one({"budget_id": r["budget_id"]},
                                   {"$inc": {"unknown_count": -1, "reserved_usd": -r["remaining_usd"],
                                             "spent_usd": provider_billed_usd}})
        self.ledger.record("provider_billing", reservation_id=reservation_id, budget_id=r["budget_id"],
                    provider_billed_usd=provider_billed_usd, source=source)
        return True

    def state(self, budget_id):
        return self.db.budgets.find_one({"budget_id": budget_id}, {"_id": 0})

    def mark_unknown(self, session_id):
        if session_id:
            self.db.reservations.update_one({"session_id": session_id, "status": "open"},
                                            {"$set": {"unknown_usage": True}})

    def settle(self, session_id, usd, unknown, usage=None):
        if not session_id:
            return
        r = self.db.reservations.find_one({"session_id": session_id, "status": "open"})
        if not r:
            return
        if usd is None and not unknown:   # usage reported in full, model unnamed: price it as the reserved model
            usd = L.estimate_usd(r["model"], usage)
        if unknown or usd is None:
            self.mark_unknown(session_id)
            return
        take = min(usd, r["remaining_usd"])
        over = round(usd - take, 8)
        res = self.db.reservations.find_one_and_update(
            {"reservation_id": r["reservation_id"], "status": "open"},
            {"$inc": {"remaining_usd": -take, "spent_usd": usd, "overage_usd": over, "responses": 1}},
            return_document=pymongo.ReturnDocument.AFTER)
        if res:
            self.db.budgets.update_one({"budget_id": r["budget_id"]}, {"$inc": {"reserved_usd": -take, "spent_usd": usd}})
            if over > 0 or res["responses"] > res["max_responses"]:
                self.ledger.record("budget_bound_exceeded", budget_id=r["budget_id"], reservation_id=r["reservation_id"],
                            overage_usd=over, responses=res["responses"], max_responses=res["max_responses"])

    def _expire_stale(self, budget_id):
        cutoff = (L.now() - timedelta(seconds=L.STALE_GRACE_S)).isoformat()
        while True:
            r = self.db.reservations.find_one_and_update(
                {"budget_id": budget_id, "status": "open", "deadline": {"$lt": cutoff}},
                {"$set": {"status": "stale", "unknown_usage": True}})
            if not r:
                return
            self.db.budgets.update_one({"budget_id": budget_id}, {"$inc": {"open_count": -1, "unknown_count": 1}})
            self.ledger.record("budget_stale", budget_id=budget_id, reservation_id=r["reservation_id"],
                        reason="still open past its deadline: its usage is unknown")
