"""Step 1 — the resident-request tools must speak from Layer E.

`check_request_status` and the `request_staff_help` duplicate branch build
their spoken result from `_resident_safe_view` / the dedupe response. Those
now carry `lifecycle` + `spoken` from `routes/aria_request_status.py`, which
reuses Layer E's `task_lifecycle`. This proves the tool-facing view and
`resolve_operational_state` cannot disagree about the same task, and that no
stale "waiting / unanswered" language survives once a request is resolved.

Direct-function tests over seeded Mongo (the running dev backend has not been
reloaded since these fields were added), same convention as the other
substrate tests.
"""
import asyncio
import os
import sys
import uuid
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _skip_if_down():
    try:
        import requests
        requests.get(os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000")
                     + "/api/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("backend / mongo not reachable")


_STALE_WAITING = ("waiting", "unanswered", "not yet acknowledged", "no one has picked it up",
                  "still open", "hasn't been")
_DONE_WORDS = ("taken care of", "has been handled", "already been handled")


async def _run():
    from deps import db
    from models import now_utc
    from routes.resident_requests import _resident_safe_view, resident_request_status
    from routes.aria_operational_state import resolve_operational_state, task_lifecycle

    rid = f"res_test_{uuid.uuid4().hex[:8]}"
    room = f"rtse_{uuid.uuid4().hex[:6]}"
    now = now_utc()
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    try:
        await db.staff_tasks.insert_one({
            "task_id": task_id, "title": "Check the reading lamp", "status": "pending",
            "category": "maintenance", "source": "aria_voice",
            "resident_id": rid, "room": room,
            "resident_words": "my reading lamp keeps flickering",
            "conversation_session_id": f"rt_{uuid.uuid4().hex[:6]}",
            "created_at": (now - timedelta(hours=3)).isoformat(),
        })

        # --- OPEN: tool view lifecycle == Layer E lifecycle for the same task
        doc = await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0})
        view = _resident_safe_view(doc)
        assert view["lifecycle"] == "open" == task_lifecycle(doc)
        op = await resolve_operational_state(rid, room)
        e_item = next(i for i in op["current"] + op["background"] if i["ref"] == task_id)
        assert e_item["lifecycle"] == view["lifecycle"], "tool view and Layer E disagree"
        assert "3 hours ago" in view["opened_age"]
        low = view["spoken"].lower()
        assert not any(w in low for w in _DONE_WORDS), view["spoken"]

        # via the endpoint function
        res = await resident_request_status(resident_id=rid)
        assert res["found"] and res["lifecycle"] == "open"
        assert "spoken" in res

        # --- ACKNOWLEDGED: no "resolved" language, no "no one has picked it up"
        await db.staff_tasks.update_one({"task_id": task_id}, {"$set": {
            "status": "in_progress", "acknowledged_at": now.isoformat(),
            "assigned_name": "J. Ruiz"}})
        doc = await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0})
        view = _resident_safe_view(doc)
        assert view["lifecycle"] == "in_progress" == task_lifecycle(doc)
        assert "J. Ruiz" in view["spoken"]
        assert "no one has picked it up" not in view["spoken"].lower()

        # --- RESOLVED: previously-open request now done -> reports resolved,
        #     and NO stale waiting/unanswered language survives.
        await db.staff_tasks.update_one({"task_id": task_id}, {"$set": {
            "status": "completed", "completed_at": now.isoformat(),
            "completed_by_name": "J. Ruiz"}})
        doc = await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0})
        view = _resident_safe_view(doc)
        assert view["lifecycle"] == "resolved" == task_lifecycle(doc)
        low = view["spoken"].lower()
        assert any(w in low for w in _DONE_WORDS), view["spoken"]
        assert not any(w in low for w in _STALE_WAITING), view["spoken"]
        # Layer E now drops it from open work -> cannot contradict
        op = await resolve_operational_state(rid, room)
        assert task_id not in {i["ref"] for i in op["current"] + op["background"]}

        res = await resident_request_status(resident_id=rid)
        assert res["lifecycle"] == "resolved"
        assert not any(w in res["spoken"].lower() for w in _STALE_WAITING)

    finally:
        await db.staff_tasks.delete_many({"task_id": task_id})


async def _dedupe_branch():
    """The request_staff_help duplicate response also carries lifecycle/spoken
    and never calls an open dup 'resolved'."""
    from deps import db
    from models import now_utc
    from routes.resident_requests import create_resident_request, ResidentRequestInput

    rid = f"res_test_{uuid.uuid4().hex[:8]}"
    room = f"rtse_{uuid.uuid4().hex[:6]}"
    made = []
    try:
        r1 = await create_resident_request(ResidentRequestInput(
            category="maintenance", resident_id=rid, room=room,
            resident_words="the AC is too warm", summary="the AC is too warm",
            source="aria_voice"))
        made.append(r1["task_id"])
        assert r1["duplicate"] is False

        r2 = await create_resident_request(ResidentRequestInput(
            category="maintenance", resident_id=rid, room=room,
            resident_words="still too warm", summary="still too warm",
            source="aria_voice"))
        assert r2["duplicate"] is True
        assert r2["lifecycle"] == "open"
        assert "spoken" in r2 and "resolved" not in r2["spoken"].lower()
        assert "taken care of" not in r2["spoken"].lower()
    finally:
        await db.staff_tasks.delete_many({"resident_id": rid})
        await db.receipts.delete_many({"resident_id": rid})


def test_request_status_view_matches_layer_e():
    _skip_if_down()
    asyncio.get_event_loop().run_until_complete(_run())


def test_dedupe_branch_speaks_lifecycle():
    _skip_if_down()
    asyncio.get_event_loop().run_until_complete(_dedupe_branch())
