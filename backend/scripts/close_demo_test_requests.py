"""Close named test requests in the demo-only room, keeping their history.

For test requests left in the demo room that DEMO RESET cannot close
because they were created before the demo resident was marked synthetic
(so they carry no simulated marker). Marking them simulated afterwards would
rewrite their provenance, so instead each named request is closed through
the same lifecycle step DEMO RESET uses (task_actions.skip by a system
actor): one chained receipt per request, the reason in its note, nothing
deleted. Refuses any request outside the demo room.

    cd backend && .venv/bin/python scripts/close_demo_test_requests.py "reason" task_a task_b ...
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from fastapi import HTTPException  # noqa: E402

from deps import db  # noqa: E402
from routes import task_actions  # noqa: E402
from routes.actor_context import actor_system  # noqa: E402
from routes.demo_kiosk import DEMO_ROOM  # noqa: E402


async def main(reason: str, task_ids: list) -> list:
    actor = actor_system("test_data_cleanup")
    out = []
    for tid in task_ids:
        task = await db.staff_tasks.find_one({"task_id": tid}, {"_id": 0, "room": 1, "status": 1})
        if not task or task.get("room") != DEMO_ROOM:
            out.append({"task_id": tid, "closed": False, "reason": "not a demo-room request"})
            continue
        try:
            after, receipt = await task_actions.skip(tid, reason, actor, None,
                                                     authority="system:test_data_cleanup")
            out.append({"task_id": tid, "closed": True, "status": after["status"],
                        "receipt_id": receipt["receipt_id"]})
        except HTTPException as e:
            out.append({"task_id": tid, "closed": False, "reason": str(e.detail)})
    return out


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    print(json.dumps(asyncio.run(main(sys.argv[1], sys.argv[2:])), indent=1))
