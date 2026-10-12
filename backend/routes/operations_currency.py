"""Current vs historical operations (careops-current-operations-truth-001).

The dev and production databases hold months of RF bring-up activations and
mock/test requests that were never closed. Screens listed them as "open" next
to real, current work. This module is the ONE rule that says which open
record is which, so every screen filters the same way and nothing is erased:

  sim_current - simulated, from the simulator run that is RUNNING/PAUSED now
  sim_past    - simulated, from a run that has stopped
  current     - real (not simulated) and opened inside the window
  review      - real/unknown and older than the window: needs a human look
                (review_reason says why: test/mock resident, no resident
                attached, or real/unknown origin)

Windows: alerts STALE_ALERT_HOURS (72 h, shared with the overview); tasks
CAOSCARE_TASK_REVIEW_DAYS (14 days). Age alone never closes anything:
`POST /ops/legacy/close` lets an administrator close REVIEW records with a
reason, through the canonical receipted paths; an emergency additionally
needs a written human disposition.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db, require_admin
from models import now_utc
from routes.ops_overview_util import STALE_ALERT_HOURS

router = APIRouter(prefix="/ops", tags=["ops"])
TASK_REVIEW_DAYS = max(1, int(os.getenv("CAOSCARE_TASK_REVIEW_DAYS", "14")))
OPEN_ALERT = ("active", "acknowledged")
OPEN_TASK = ("pending", "in_progress")
TEST_PREFIXES = ("MOCK ", "TEST ", "Demo - ", "MOCK", "TEST")


def _dt(v) -> Optional[datetime]:
    if not v:
        return None
    try:
        d = datetime.fromisoformat(v) if isinstance(v, str) else v
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


async def active_run() -> Optional[dict]:
    return await db.sim_runs.find_one({"state": {"$in": ["RUNNING", "PAUSED"]}}, {"_id": 0}, sort=[("started_at", -1)])


def _review_reason(rec: dict) -> str:
    name = rec.get("resident_name") or ""
    if not rec.get("resident_id") and not name:
        return "no resident attached (device or test activity)"
    if name.startswith(TEST_PREFIXES):
        return "test / mock resident"
    return "real or unknown origin - check before closing"


def classify(rec: dict, kind: str, run_id: Optional[str], now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    window = timedelta(hours=STALE_ALERT_HOURS) if kind == "alert" else timedelta(days=TASK_REVIEW_DAYS)
    opened = _dt(rec.get("created_at"))
    if rec.get("simulated"):
        if rec.get("simulation_run_id"):
            live = bool(run_id) and rec.get("simulation_run_id") == run_id
            return {"bucket": "sim_current" if live else "sim_past", "run_id": rec.get("simulation_run_id"), "reason": None}
        # simulated but not part of a simulator run (the demo room): current while recent, like real work
        recent = bool(opened) and now - opened <= window
        return {"bucket": "sim_current" if recent else "sim_past", "run_id": None, "reason": None}
    if opened and now - opened <= window:
        return {"bucket": "current", "run_id": None, "reason": None}
    return {"bucket": "review", "run_id": None, "reason": _review_reason(rec)}


async def annotate(records: list, kind: str) -> list:
    """Add `currency` to each OPEN record (closed records are history already)."""
    run = await active_run()
    rid = run["run_id"] if run else None
    now = datetime.now(timezone.utc)
    open_set = OPEN_ALERT if kind == "alert" else OPEN_TASK
    for r in records:
        if r.get("status") in open_set:
            r["currency"] = classify(r, kind, rid, now)
    return records


def filter_view(records: list, view: Optional[str]) -> list:
    if view == "current":
        return [r for r in records if (r.get("currency") or {}).get("bucket") in (None, "current", "sim_current")]
    if view == "review":
        return [r for r in records if (r.get("currency") or {}).get("bucket") in ("review", "sim_past")]
    return records


@router.get("/currency")
async def currency(user=Depends(require_admin)):
    """Simulator state + open alerts/tasks counted by bucket (and review reason)."""
    run = await active_run()
    last = await db.sim_runs.find_one({}, {"_id": 0}, sort=[("updated_at", -1)])
    rid = run["run_id"] if run else None
    now = datetime.now(timezone.utc)
    out = {"simulator": {"active_run_id": rid, "state": run["state"] if run else "STOPPED",
                         "scenario": (run or last or {}).get("scenario"),
                         "last_run_id": (last or {}).get("run_id"), "last_updated_at": (last or {}).get("updated_at")},
           "windows": {"alert_hours": STALE_ALERT_HOURS, "task_days": TASK_REVIEW_DAYS}}
    for kind, coll, statuses in (("alerts", db.alerts, OPEN_ALERT), ("tasks", db.staff_tasks, OPEN_TASK)):
        counts: dict = {"current": 0, "sim_current": 0, "sim_past": 0, "review": 0, "review_by_reason": {}, "review_emergencies": 0}
        async for r in coll.find({"status": {"$in": list(statuses)}}, {"_id": 0, "simulated": 1, "simulation_run_id": 1, "created_at": 1,
                                                                      "resident_id": 1, "resident_name": 1, "severity": 1}):
            c = classify(r, kind[:-1], rid, now)
            counts[c["bucket"]] += 1
            if c["bucket"] == "review":
                counts["review_by_reason"][c["reason"]] = counts["review_by_reason"].get(c["reason"], 0) + 1
                if r.get("severity") == "emergency":
                    counts["review_emergencies"] += 1
        out[kind] = counts
    return out


class LegacyClose(BaseModel):
    kind: Literal["alert", "task"]
    ids: List[str] = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=3, max_length=300)
    disposition: Optional[str] = Field(default=None, max_length=300)   # required for an emergency alert


@router.post("/legacy/close")
async def close_legacy(data: LegacyClose, user=Depends(require_admin)):
    """Close reviewed historical records. Only REVIEW records are accepted
    (current and simulated work is refused); tasks go through the canonical
    receipted skip; alerts are resolved with outcome `legacy_review_closed`
    and a receipt; an emergency needs `disposition` (what a person confirmed)."""
    from routes import task_actions
    from routes.actor_context import actor_from_user
    from routes.receipts import create_receipt
    run = await active_run()
    rid = run["run_id"] if run else None
    actor = actor_from_user(user)
    results = []
    for oid in dict.fromkeys(data.ids):
        if data.kind == "task":
            t = await db.staff_tasks.find_one({"task_id": oid}, {"_id": 0})
            if not t or t.get("status") not in OPEN_TASK:
                results.append({"id": oid, "ok": False, "why": "not found or already closed"}); continue
            c = classify(t, "task", rid)
            if c["bucket"] != "review":
                results.append({"id": oid, "ok": False, "why": f"not a review item ({c['bucket']})"}); continue
            await task_actions.skip(oid, f"Legacy record closed after review: {data.reason}", actor, user)
            results.append({"id": oid, "ok": True})
        else:
            a = await db.alerts.find_one({"alert_id": oid}, {"_id": 0})
            if not a or a.get("status") not in OPEN_ALERT:
                results.append({"id": oid, "ok": False, "why": "not found or already closed"}); continue
            c = classify(a, "alert", rid)
            if c["bucket"] != "review":
                results.append({"id": oid, "ok": False, "why": f"not a review item ({c['bucket']})"}); continue
            if a.get("severity") == "emergency" and not (data.disposition or "").strip():
                results.append({"id": oid, "ok": False, "why": "emergency: a written human disposition is required"}); continue
            now = now_utc().isoformat()
            notes = f"Legacy record closed after review: {data.reason}" + (f" | Disposition: {data.disposition.strip()}" if data.disposition else "")
            r = await db.alerts.update_one({"alert_id": oid, "status": {"$in": list(OPEN_ALERT)}},
                                           {"$set": {"status": "resolved", "resolved_by": user["name"], "resolved_at": now,
                                                     "outcome": "legacy_review_closed", "close_notes": notes, "category": "legacy_test_data"}})
            if not r.modified_count:
                results.append({"id": oid, "ok": False, "why": "changed concurrently"}); continue
            await create_receipt(action_type="alert_legacy_closed", related_object_type="alert", related_object_id=oid,
                                 source="staff", resident_id=a.get("resident_id"), room=a.get("room"), status="completed", result=notes,
                                 provenance={**actor.receipt_fields(), "authority": f"admin_override:{user.get('role')}",
                                             "before_state": {"status": a.get("status"), "severity": a.get("severity"), "created_at": a.get("created_at")},
                                             "after_state": {"status": "resolved", "outcome": "legacy_review_closed"},
                                             "review_reason": c["reason"], "result_label": "verified"})
            results.append({"id": oid, "ok": True})
    return {"closed": sum(1 for r in results if r["ok"]), "refused": [r for r in results if not r["ok"]], "results": results}
