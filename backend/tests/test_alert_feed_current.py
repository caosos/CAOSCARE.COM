"""careops-alerts-staff-feed-current-001: the staff Live alerts feed lists
current open alerts (newer than STALE_ALERT_HOURS, the same alert_is_stale
bound the owner board uses), newest first; older open alerts are returned
only on request (scope=older) and counted in /alerts/stats, never hidden
silently and never closed. In-process, DB-direct; refuses the live DB.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes alert records; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes.alerts import alert_stats, alerts_feed  # noqa: E402
from routes.ops_overview_util import STALE_ALERT_HOURS  # noqa: E402

TAG = f"afc_{uuid.uuid4().hex[:8]}"
NOW = datetime.now(timezone.utc)
USER = {"user_id": f"{TAG}_n", "role": "staff", "department": "nursing"}


def _alert(name, age_h, status="active"):
    return {"alert_id": f"{TAG}_{name}", "room": f"{TAG}-R", "severity": "assist", "status": status,
            "escalation_level": 0, "event_log": [], "created_at": (NOW - timedelta(hours=age_h)).isoformat()}


async def _scenario():
    await db.alerts.insert_many([_alert("new", 0.1), _alert("day", 30, "acknowledged"),
                                 _alert("old1", STALE_ALERT_HOURS + 1), _alert("old2", 24 * 20, "escalated"),
                                 _alert("done", 1, "resolved")])
    try:
        mine = lambda items: [i["alert_id"].removeprefix(f"{TAG}_") for i in items if i["alert_id"].startswith(TAG)]
        cur = mine(await alerts_feed(user=USER))
        assert cur == ["new", "day"], cur            # current only, newest first, resolved excluded
        old = mine(await alerts_feed(scope="older", user=USER))
        assert old == ["old1", "old2"], old
        stats = await alert_stats(user=USER)
        assert stats["older_open"] >= 2           # counted on the dashboard's existing stats call
        for n in ("old1", "old2"):                   # nothing was closed
            assert (await db.alerts.find_one({"alert_id": f"{TAG}_{n}"}))["status"] in ("active", "escalated")
    finally:
        await db.alerts.delete_many({"alert_id": {"$regex": f"^{TAG}_"}})


def test_staff_feed_lists_current_and_counts_older():
    asyncio.get_event_loop().run_until_complete(_scenario())
