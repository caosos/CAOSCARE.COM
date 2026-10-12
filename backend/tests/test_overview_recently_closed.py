"""The any-request status read also returns requests completed in the last
few hours (not cancelled ones, not old ones), so Aria can say a just-finished
request was taken care of instead of only "nothing open"."""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_recently_closed():
    async def run():
        from deps import db
        from routes.resident_request_overview import resident_requests_open
        rid = "res_test_recent_closed"
        now = datetime.now(timezone.utc)
        base = {"resident_id": rid, "room": "T-RC", "category": "nursing", "source": "aria_voice",
                "title": "help", "created_at": (now - timedelta(hours=1)).isoformat()}
        docs = [
            {**base, "task_id": "t_rc_done", "status": "completed", "completed_at": (now - timedelta(minutes=5)).isoformat(), "completed_by_name": "Nora"},
            {**base, "task_id": "t_rc_cancel", "status": "skipped", "completed_at": (now - timedelta(minutes=5)).isoformat()},
            {**base, "task_id": "t_rc_old", "status": "completed", "completed_at": (now - timedelta(days=2)).isoformat()},
        ]
        await db.staff_tasks.delete_many({"resident_id": rid})
        await db.staff_tasks.insert_many(docs)
        try:
            out = await resident_requests_open(resident_id=rid)
            assert out["found"] is False
            assert [r["task_id"] for r in out["recently_closed"]] == ["t_rc_done"]
            assert "taken care of" in out["recently_closed"][0]["spoken"]
        finally:
            await db.staff_tasks.delete_many({"resident_id": rid})
    asyncio.run(run())
