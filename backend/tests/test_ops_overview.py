"""Admin/ED operations overview - read-only aggregation (GET /ops/overview).

Seeds its own TAG-prefixed admin + tasks + a fresh department + a few
alert docs directly in Mongo (alerts are inserted, never written through
alerts.py - this test does not touch the ResidentEvent/RF/realtime lane),
exercises the endpoint, then deletes everything it made. All DB work is in
one asyncio.run() (Motor single-loop constraint, same as the siblings).

    TEST_API_BASE=http://127.0.0.1:8001 pytest tests/test_ops_overview.py -q
Defaults to http://127.0.0.1:8000. Skips cleanly if unreachable.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
import requests

BASE_URL = os.environ.get("TEST_API_BASE", os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TAG = f"ops_{uuid.uuid4().hex[:8]}"


def _backend_up() -> bool:
    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


def _iso(dt):
    return dt.replace(tzinfo=timezone.utc).isoformat()


async def _run():
    # Own Motor client bound to this asyncio.run() loop - see the note in
    # test_staff_department.py; keeps the DB test files co-runnable.
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    now = datetime.now(timezone.utc)
    pw = "ops-admin-pw-123"
    admin_id = uid("user")
    admin_email = f"{TAG}_admin@example.com"
    await db.users.insert_one({
        "user_id": admin_id, "email": admin_email, "name": "Ops Admin", "role": "admin",
        "auth_provider": "jwt", "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
        "created_at": now_utc().isoformat(),
    })

    # --- tasks -------------------------------------------------------------
    def task(**kw):
        base = {
            "task_id": uid("task"), "title": kw.pop("title", f"{TAG} task"),
            "description": "", "category": "other", "shift": "any", "status": "pending",
            "priority": "normal", "source": "staff", "visibility_role": "all_staff",
            "assigned_to": None, "assigned_name": None, "room": f"{TAG}-RM",
            "created_at": _iso(now), "re_request_count": 0,
        }
        base.update(kw)
        return base

    t_old = task(title=f"{TAG} oldest maint", category="maintenance", visibility_role="maintenance",
                 source="aria_voice", created_at=_iso(now - timedelta(days=400)))
    t_overdue = task(title=f"{TAG} overdue maint", category="maintenance", visibility_role="maintenance",
                     assigned_to="u_x", assigned_name="Bob", due_at=_iso(now - timedelta(hours=3)))
    t_done = task(title=f"{TAG} hk done", category="housekeeping", visibility_role="housekeeping",
                  status="completed", completed_at=_iso(now), completed_by_name="Ann")
    t_ride = task(title=f"{TAG} ride", category="transportation", visibility_role="transportation",
                  source="aria_voice", requested_for_date=(now - timedelta(days=1)).strftime("%Y-%m-%d"))
    t_gen = task(title=f"{TAG} general unassigned")
    await db.staff_tasks.insert_many([t_old, t_overdue, t_done, t_ride, t_gen])

    # --- alerts (inserted directly; read-only from the endpoint's POV) ----
    a_emerg = {"alert_id": uid("alert"), "status": "active", "severity": "emergency",
               "resident_name": f"{TAG} Rez", "room": f"{TAG}-9", "triggered_by": "kiosk_button",
               "created_at": _iso(now - timedelta(minutes=10))}
    a_ack = {"alert_id": uid("alert"), "status": "acknowledged", "severity": "assist",
             "resident_name": f"{TAG} Rez2", "room": f"{TAG}-8", "acknowledged_by": "Nurse Kim",
             "triggered_by": "kiosk_button", "created_at": _iso(now - timedelta(hours=1))}
    a_stale = {"alert_id": uid("alert"), "status": "active", "severity": "assist",
               "resident_name": f"{TAG} Rez3", "room": f"{TAG}-7", "triggered_by": "rf_pendant",
               "created_at": _iso(now - timedelta(hours=100))}
    await db.alerts.insert_many([a_emerg, a_ack, a_stale])

    dept_id = None
    try:
        r = requests.post(f"{API}/auth/login", json={"email": admin_email, "password": pw}, timeout=5)
        r.raise_for_status()
        H = {"Authorization": f"Bearer {r.json()['token']}"}

        # a brand-new department with zero tasks -> "renders with empty datasets"
        r = requests.post(f"{API}/departments", headers=H, json={"label": f"{TAG} Empty Dept"}, timeout=5)
        assert r.status_code == 200, r.text
        dept_id = r.json()["department_id"]
        empty_slug = r.json()["slug"]

        # attention_limit=400 so seeded rows are findable even on a DB that
        # already carries hundreds of unrelated (stale test) alerts.
        ov = requests.get(f"{API}/ops/overview", headers=H, params={"attention_limit": 400}, timeout=15)
        assert ov.status_code == 200, ov.text
        d = ov.json()

        # structure always present
        for k in ("generated_at", "facility_date", "attention", "attention_total",
                  "departments", "assistance", "tasks", "transportation", "counts_caveat"):
            assert k in d, f"missing key {k}"
        assert isinstance(d["attention"], list)
        assert isinstance(d["departments"], list)
        assert isinstance(d["tasks"]["oldest_open"], list)
        assert isinstance(d["tasks"]["unassigned"], list)
        assert isinstance(d["transportation"]["waiting_unbooked"], list)

        by_ref = {r["ref_id"]: r for r in d["attention"]}

        # --- 1. attention builder: each seeded row lands in the right tier ---
        assert d["attention"], "attention list unexpectedly empty with seeded data"
        # a non-stale active emergency always sorts to the very top (tier 0)
        assert d["attention"][0]["severity"] == "emergency", d["attention"][0]
        em = by_ref.get(a_emerg["alert_id"])
        assert em and em["tier"] == 0 and em["kind"] == "assistance", em
        ov_row = by_ref.get(t_overdue["task_id"])
        assert ov_row and ov_row["tier"] == 2 and ov_row["reason"].startswith("Overdue by"), ov_row
        ride_row = by_ref.get(t_ride["task_id"])
        assert ride_row and ride_row["tier"] == 3, ride_row
        gen_row = by_ref.get(t_gen["task_id"])
        assert gen_row and gen_row["tier"] == 5 and "Unassigned" in gen_row["reason"], gen_row
        stale_row = by_ref.get(a_stale["alert_id"])
        assert stale_row and stale_row["tier"] >= 7, stale_row  # demoted, still present

        # --- deterministic ordering (default limit) ---
        base = requests.get(f"{API}/ops/overview", headers=H, timeout=15).json()["attention"]
        again = requests.get(f"{API}/ops/overview", headers=H, timeout=15).json()["attention"]
        assert [(r["kind"], r["ref_id"], r["tier"]) for r in base] == [(r["kind"], r["ref_id"], r["tier"]) for r in again]
        tiers = [r["tier"] for r in base]
        assert tiers == sorted(tiers), "attention not ordered by tier"

        # --- 2. department status ---
        by_slug = {row["slug"]: row for row in d["departments"]}
        assert by_slug["maintenance"]["open"] >= 2
        assert by_slug["maintenance"]["overdue"] >= 1
        assert by_slug["maintenance"]["unassigned"] >= 1
        assert by_slug["housekeeping"]["completed_today"] >= 1
        assert by_slug["all_staff"]["unassigned"] >= 1 and by_slug["all_staff"]["is_general"] is True
        assert by_slug[empty_slug]["open"] == 0 and by_slug[empty_slug]["overdue"] == 0

        # --- 3. resident assistance summary ---
        a = d["assistance"]
        assert a["active"] >= 1 and a["acknowledged"] >= 1
        assert a["open_total"] >= 2 and a["unowned_open"] >= 1 and a["owned_open"] >= 1
        assert a["possibly_stale_open_gt_72h"] >= 1
        assert a["oldest_open"] is not None

        # --- 4. task ownership / aging ---
        assert d["tasks"]["unassigned_open"] >= 2
        assert d["tasks"]["overdue_open"] >= 1
        assert d["tasks"]["completed_today"] >= 1
        # t_old is 400 days back - it must be the single oldest open task,
        # and (being unassigned) also the first row of the "no owner" list.
        assert d["tasks"]["oldest_open"][0]["title"] == f"{TAG} oldest maint", d["tasks"]["oldest_open"][:3]
        assert d["tasks"]["unassigned"][0]["title"] == f"{TAG} oldest maint"
        assert d["tasks"]["oldest_open"][0]["department"] == "Maintenance"
        assert d["tasks"]["oldest_open"][0]["link_hint"] == "requests"  # source=aria_voice

        # --- 5. transportation ---
        tr = d["transportation"]
        assert tr["needs_action"] >= 1
        assert tr["past_requested_date_open"] >= 1
        assert isinstance(tr["waiting_unbooked"], list) and len(tr["waiting_unbooked"]) <= 10
        # t_ride is a tier-3 attention row (built earlier) - the compact
        # transport list itself is capped/sorted, so assert on the total.
        assert by_ref[t_ride["task_id"]]["reason"] in ("Ride requested, no slot booked", "Past its requested date, still open")
    finally:
        if dept_id:
            try:
                requests.delete(f"{API}/departments/{dept_id}",
                                headers={"Authorization": f"Bearer {r.json()['token']}"}, timeout=5)
            except Exception:
                pass
        await db.staff_tasks.delete_many({"room": f"{TAG}-RM"})
        await db.alerts.delete_many({"alert_id": {"$in": [a_emerg["alert_id"], a_ack["alert_id"], a_stale["alert_id"]]}})
        await db.departments.delete_many({"slug": {"$regex": f"^{TAG.lower()}"}})
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})


def test_ops_overview():
    if not _backend_up():
        pytest.skip(f"backend not reachable at {BASE_URL}")
    asyncio.run(_run())
