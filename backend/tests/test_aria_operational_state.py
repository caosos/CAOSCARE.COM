"""Regression tests for the conversation-substrate operational-state authority
(routes/aria_operational_state.py).

Anchored to Room 214 evidence
(docs/ROOM_214_CONVERSATION_EVIDENCE_2026-09-08.md, Part 4 #1):

  * a stale, unacknowledged staff request must report as `open` WITH an age,
    not as timeless "already on file";
  * an acknowledged/resolved item must not still read as waiting;
  * when a live emergency EVENT (db.alerts) and an old staff REQUEST
    (db.staff_tasks) both exist, the emergency is `current` and the old
    request is `background` - the bug was `check_request_status` reporting
    the old bathroom request as "the request on file" during a bleeding call;
  * a fresh session with nothing open produces an EMPTY block (no forced
    workflow at session start).

Hits the real running backend over HTTP for the endpoint and uses the shared
Mongo for seeding, same convention as tests/test_resident_events.py. Skips
cleanly if the backend is unreachable.
"""
import asyncio
import os
import sys
import uuid
from datetime import timedelta, timezone

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _skip_if_down():
    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("backend not reachable")


async def _seed_and_check():
    from deps import db
    from models import now_utc

    rid = f"res_test_{uuid.uuid4().hex[:8]}"
    room = f"optest_{uuid.uuid4().hex[:6]}"
    now = now_utc()

    # An open assistance EVENT (alerts) - the resident pressed ~5h ago, and
    # no staff has touched it. This is the "hours ago, still pending" case.
    stale_event = f"alert_{uuid.uuid4().hex[:12]}"
    await db.alerts.insert_one({
        "alert_id": stale_event, "resident_id": rid, "room": room,
        "status": "active", "severity": "assist", "triggered_by": "rf_pendant",
        "message": "RF pendant pressed", "resident_stated_reason": "needs the bathroom",
        "press_count": 4, "presses": [], "aria_state": "dormant",
        "created_at": (now - timedelta(hours=5)).isoformat(),
        "acknowledged_at": None, "resolved_at": None,
    })
    # An old staff REQUEST (staff_tasks), still pending, different wording.
    stale_task = f"task_{uuid.uuid4().hex[:12]}"
    await db.staff_tasks.insert_one({
        "task_id": stale_task, "resident_id": rid, "room": room,
        "category": "nursing", "status": "pending", "source": "aria_voice",
        "title": "needs help using the bathroom", "description": "needs help using the bathroom",
        "resident_words": "needs help using the bathroom", "re_request_count": 3,
        "created_at": (now - timedelta(hours=5)).isoformat(), "acknowledged_at": None,
    })

    try:
        from routes.aria_operational_state import resolve_operational_state

        # --- no alert_id, single open event => that event is `current` ---
        st = await resolve_operational_state(resident_id=rid, room=room)
        assert st["has_open_work"] is True
        ev = [i for i in st["current"] if i["ref"] == stale_event]
        assert ev, "the single open event must be classified current"
        assert ev[0]["lifecycle"] == "open"
        assert ev[0]["acknowledged"] is False
        assert "hours ago" in ev[0]["opened_age"], ev[0]["opened_age"]
        # the pending staff request is real work, reported with its age
        tk = [i for i in (st["current"] + st["background"]) if i["ref"] == stale_task]
        assert tk and tk[0]["lifecycle"] == "open"
        assert tk[0]["opened_age"] != "at an unknown time"
        assert tk[0]["re_request_count"] == 3

        # --- a NEW live emergency event arrives; the old bathroom request
        #     must fall to `background`, not masquerade as "the request" ---
        live = f"alert_{uuid.uuid4().hex[:12]}"
        await db.alerts.insert_one({
            "alert_id": live, "resident_id": rid, "room": room,
            "status": "active", "severity": "emergency", "triggered_by": "ai_triage",
            "message": "call_for_help", "resident_stated_reason": "bleeding",
            "press_count": 1, "presses": [], "aria_state": "active",
            "created_at": now.isoformat(), "acknowledged_at": None, "resolved_at": None,
        })
        st2 = await resolve_operational_state(resident_id=rid, room=room, alert_id=live)
        cur_refs = {i["ref"] for i in st2["current"]}
        bg_refs = {i["ref"] for i in st2["background"]}
        assert live in cur_refs, "the event Aria was brought in on is current"
        assert stale_task in bg_refs, "an unrelated older request must be background, not current"
        assert stale_event in bg_refs
        live_view = next(i for i in st2["current"] if i["ref"] == live)
        assert live_view["about"] == "bleeding"

        # --- acknowledged => no longer reads as waiting ---
        await db.alerts.update_one({"alert_id": live}, {"$set": {
            "status": "acknowledged", "acknowledged_by": "R. Nguyen RN",
            "acknowledged_at": now.isoformat()}})
        st3 = await resolve_operational_state(resident_id=rid, room=room, alert_id=live)
        v = next(i for i in st3["current"] if i["ref"] == live)
        assert v["lifecycle"] == "acknowledged"
        assert v["acknowledged"] is True
        assert v["handled_by"] == "R. Nguyen RN"

        # --- resolved => drops out of open work, into recently_resolved ---
        await db.alerts.update_one({"alert_id": live}, {"$set": {
            "status": "resolved", "resolved_by": "R. Nguyen RN",
            "resolved_at": now.isoformat()}})
        st4 = await resolve_operational_state(resident_id=rid, room=room, alert_id=live)
        assert live not in {i["ref"] for i in st4["current"] + st4["background"]}
        assert live in {i["ref"] for i in st4["recently_resolved"]}

    finally:
        await db.alerts.delete_many({"resident_id": rid})
        await db.staff_tasks.delete_many({"resident_id": rid})


async def _empty_case():
    from routes.aria_operational_state import resolve_operational_state
    from routes.realtime_operational_context import render_operational_block

    st = await resolve_operational_state(resident_id=f"res_none_{uuid.uuid4().hex[:8]}")
    assert st["has_open_work"] is False
    assert st["current"] == [] and st["background"] == []
    # A fresh session with nothing open must not begin inside a workflow.
    assert render_operational_block(st) == ""
    assert render_operational_block(None) == ""


def test_operational_state_lifecycle_and_relevance():
    _skip_if_down()
    asyncio.get_event_loop().run_until_complete(_seed_and_check())


def test_operational_state_empty_means_no_workflow():
    _skip_if_down()
    asyncio.get_event_loop().run_until_complete(_empty_case())


def test_operational_state_http_endpoint():
    """Thin wrapper over resolve_operational_state(). Skips if the shared
    dev backend hasn't been reloaded since this route was added (no reload
    flag on that process)."""
    _skip_if_down()
    r = requests.get(f"{API}/aria/operational-state",
                     params={"room": f"optest_{uuid.uuid4().hex[:6]}"}, timeout=5)
    if r.status_code == 404:
        pytest.skip("backend not reloaded since /aria/operational-state was added")
    r.raise_for_status()
    body = r.json()
    assert "speak_guidance" in body and body["has_open_work"] is False
