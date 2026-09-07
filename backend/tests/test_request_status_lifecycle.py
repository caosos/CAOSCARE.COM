"""check_request_status: CURRENT state != HISTORY, and authoritative
lifecycle timestamps (Level 1 directive 2026-09-07).

PROVEN DEFECT this fixes: resident_request_status() sorted by created_at
desc with NO status filter, so a completed request from days ago was
returned to Aria as the resident's "current" request.

Directive tests 1-11. Hits the running backend over HTTP + uses deps.db to
seed synthetic StaffTask rows (never touches real resident data). Skips if
unreachable. Run: pytest tests/test_request_status_lifecycle.py -q
"""
import asyncio
import os
import sys
import uuid
from datetime import timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _status(resident_id, category=None):
    p = {"resident_id": resident_id}
    if category:
        p["category"] = category
    r = requests.get(f"{API}/tasks/resident-request/status", params=p, timeout=5)
    r.raise_for_status()
    return r.json()


def _history(resident_id, category=None):
    p = {"resident_id": resident_id}
    if category:
        p["category"] = category
    r = requests.get(f"{API}/tasks/resident-request/history", params=p, timeout=5)
    r.raise_for_status()
    return r.json()


async def _run():
    from deps import db
    from models import StaffTask, now_utc

    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("backend not reachable")

    rid = f"res_test_{uuid.uuid4().hex[:10]}"
    room = f"rlt_{uuid.uuid4().hex[:8]}"

    async def mk(category, status, *, days_ago_created=0, ack=None, started=None,
                completed=None, last_re=None, re_count=0, words="the thing", notes=""):
        base = now_utc()
        doc = StaffTask(
            title=words, description=words, category=category, resident_id=rid, room=room,
            source="aria_voice", resident_words=words, priority="normal",
        ).model_dump()
        doc["status"] = status
        doc["created_at"] = (base - timedelta(days=days_ago_created)).isoformat()
        doc["acknowledged_at"] = ack.isoformat() if ack else None
        doc["started_at"] = started.isoformat() if started else None
        doc["completed_at"] = completed.isoformat() if completed else None
        doc["last_re_requested_at"] = last_re.isoformat() if last_re else None
        doc["re_request_count"] = re_count
        doc["notes"] = notes
        await db.staff_tasks.insert_one(doc)
        return doc["task_id"]

    try:
        now = now_utc()

        # 1. one completed maintenance, no open maintenance -> current: not found
        done1 = await mk("maintenance", "completed", days_ago_created=2,
                         ack=now - timedelta(days=2), completed=now - timedelta(days=1))
        s = _status(rid, "maintenance")
        assert s["found"] is False and s["scope"] == "current", s

        # 2. older completed + newer OPEN (same category) -> current: the open one
        open2 = await mk("maintenance", "pending", days_ago_created=0, words="broken blind")
        s = _status(rid, "maintenance")
        assert s["found"] is True and s["task_id"] == open2 and s["is_open"] is True
        assert s["what_for"] == "broken blind"

        # 3. multiple completed, no open (nursing) -> current: not found
        await mk("nursing", "completed", days_ago_created=3, completed=now - timedelta(days=3))
        await mk("nursing", "skipped", days_ago_created=1)
        assert _status(rid, "nursing")["found"] is False

        # 4. explicit historical lookup still retrieves completed history
        h = _history(rid, "nursing")
        assert h["found"] is True and h["scope"] == "history"
        assert any(r["status"] == "completed" for r in h["requests"])
        hm = _history(rid, "maintenance")
        assert any(r["task_id"] == done1 for r in hm["requests"])

        # 5. companion/session context does NOT preload a completed request
        from routes.realtime_companion_memory import build_resident_profile_and_memory
        await db.residents.insert_one({"resident_id": rid, "name": "Rlt Tester", "room": room})
        r = await db.residents.find_one({"resident_id": rid}, {"_id": 0})
        prof = await build_resident_profile_and_memory(rid, r, "Rlt", "Rlt Tester")
        assert "broken blind" not in prof and "maintenance" not in prof.lower()
        assert "the thing" not in prof

        # 6. Aria has authoritative created_at for a current request
        s = _status(rid, "maintenance")
        assert s["created"] and s["created"]["iso"] and s["created"]["label"]
        import re as _re
        assert _re.match(r"(today|yesterday|\w+day|\w+ \d+) at \d{1,2}:\d{2} (AM|PM)$", s["created"]["label"]), s["created"]["label"]

        # 7. if acknowledged_at exists, Aria receives it
        open7 = await mk("housekeeping", "in_progress", ack=now - timedelta(minutes=14),
                         started=now - timedelta(minutes=10), words="spill")
        s = _status(rid, "housekeeping")
        assert s["task_id"] == open7
        assert s["acknowledged_at"] and s["acknowledged_at"]["label"]
        assert s["started_at"] and s["started_at"]["label"]

        # 8. completed/resolved timestamp reaches historical lookup
        await mk("kitchen", "completed", days_ago_created=1, completed=now - timedelta(hours=6), words="cold soup")
        h = _history(rid, "kitchen")
        got = [x for x in h["requests"] if x["what_for"] == "cold soup"][0]
        assert got["completed_at"] and got["completed_at"]["iso"] and got["completed_at"]["label"]

        # 9. missing lifecycle timestamp stays null, never invented
        s = _status(rid, "maintenance")           # the pending 'broken blind' one
        assert s["found"] is True
        assert s["acknowledged_at"] is None
        assert s["started_at"] is None
        assert s["completed_at"] is None
        assert s["latest_update_at"] is None      # StaffTask.notes has no timestamp

        # 10. re-request: original created_at unchanged, last_re_requested_at separate, count intact
        created0 = now - timedelta(days=1)        # exactly 24h -> "yesterday at <same time>"
        re_at = now - timedelta(hours=2)
        open10 = await mk("front_desk", "pending", words="package")
        await db.staff_tasks.update_one({"task_id": open10}, {"$set": {
            "created_at": created0.isoformat(), "last_re_requested_at": re_at.isoformat(),
            "re_request_count": 2}})
        s = _status(rid, "front_desk")
        assert s["created"]["iso"] == created0.isoformat()
        assert s["last_re_requested_at"]["iso"] == re_at.isoformat()
        assert s["last_re_requested_at"]["iso"] != s["created"]["iso"]
        assert s["re_request_count"] == 2

        # 11. facility-local formatting from existing timezone truth
        s = _status(rid, "front_desk")
        # created0 was ~27h ago -> facility-local label must read "yesterday at H:MM AM/PM"
        assert s["created"]["label"].startswith("yesterday at "), s["created"]["label"]
        # local iso is tz-aware and offset from UTC (America/Chicago, not +00:00)
        assert s["created"]["local"] and ("+00:00" not in s["created"]["local"])
    finally:
        await db.staff_tasks.delete_many({"resident_id": rid})
        await db.residents.delete_many({"resident_id": rid})
        await db.receipts.delete_many({"resident_id": rid})


def test_request_status_current_vs_history_and_lifecycle():
    asyncio.run(_run())
