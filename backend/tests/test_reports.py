"""Operations reporting framework - daily exceptions, weekly workload, CSV.

Read-only over staff_tasks / receipts / alerts. Proves: populated + empty
reports, old-but-not-due work is NOT called overdue, weekly uses StaffTask
truth, department boundaries + admin cross-department, staff role is
refused, CSV carries the same filtered rows with stable ids, and the
Operations Overview / receipts endpoints don't regress.

Own Motor client per asyncio.run(); TAG fixtures deleted after.

    TEST_API_BASE=http://127.0.0.1:8001 pytest tests/test_reports.py -q
"""
import asyncio
import csv
import io
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

TAG = f"rep_{uuid.uuid4().hex[:8]}"


def _backend_up():
    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=5)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _iso(dt):
    return dt.replace(tzinfo=timezone.utc).isoformat()


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    now = datetime.now(timezone.utc)
    pw = "rep-pw-12345678"
    admin_id, tech_id, staff_id = uid("user"), uid("user"), uid("user")
    TECH_NAME = f"{TAG} Techy"
    seeds = [
        (admin_id, f"{TAG}_admin@example.com", "admin", None, f"{TAG} Adminy"),
        (tech_id, f"{TAG}_tech@example.com", "staff", "maintenance", TECH_NAME),
        (staff_id, f"{TAG}_staff@example.com", "staff", "housekeeping", f"{TAG} Housey"),
    ]
    for uid_, email, role, dept, name in seeds:
        await db.users.insert_one({
            "user_id": uid_, "email": email, "name": name, "role": role,
            "department": dept, "auth_provider": "jwt",
            "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
            "created_at": now_utc().isoformat(),
        })

    def task(**kw):
        base = {
            "task_id": uid("task"), "title": kw.pop("title", f"{TAG} task"), "description": "",
            "category": "other", "shift": "any", "status": "pending", "priority": "normal",
            "visibility_role": "maintenance", "assigned_to": None, "assigned_name": None,
            "room": f"{TAG}-RM", "created_at": _iso(now), "re_request_count": 0,
        }
        base.update(kw)
        return base

    t_old = task(task_id=uid("task"), title=f"{TAG} old unassigned", created_at=_iso(now - timedelta(days=400)))
    t_overdue = task(title=f"{TAG} overdue", assigned_to=tech_id, assigned_name=TECH_NAME,
                     due_at=_iso(now - timedelta(hours=3)), created_at=_iso(now - timedelta(days=2)))
    t_done = task(title=f"{TAG} done today", status="completed", assigned_to=tech_id,
                  assigned_name=TECH_NAME, completed_at=_iso(now), completed_by=tech_id,
                  created_at=_iso(now - timedelta(days=1)))
    t_ride = task(title=f"{TAG} ride", category="transportation", visibility_role="transportation",
                  requested_for_date=(now - timedelta(days=1)).strftime("%Y-%m-%d"),
                  created_at=_iso(now - timedelta(hours=1)))
    t_rereq = task(title=f"{TAG} re-asked", visibility_role="nursing", assigned_to=admin_id,
                   assigned_name=f"{TAG} Adminy", re_request_count=2, created_at=_iso(now - timedelta(hours=5)))
    t_hk = task(title=f"{TAG} hk unassigned", visibility_role="housekeeping", created_at=_iso(now - timedelta(hours=3)))
    await db.staff_tasks.insert_many([t_old, t_overdue, t_done, t_ride, t_rereq, t_hk])

    r_failed = {"receipt_id": uid("rcpt"), "action_type": "device_command", "status": "failed",
                "related_object_type": "device_command", "related_object_id": uid("cmd"),
                "assigned_role": "maintenance", "room": f"{TAG}-RC", "failure_reason": "bridge offline",
                "created_at": now.isoformat()}
    await db.receipts.insert_one(r_failed)
    a_open = {"alert_id": uid("alert"), "status": "active", "severity": "assist",
             "resident_name": f"{TAG} res", "room": f"{TAG}-9", "triggered_by": "kiosk_button",
             "created_at": _iso(now - timedelta(hours=2))}
    await db.alerts.insert_one(a_open)

    try:
        A = _login(f"{TAG}_admin@example.com", pw)
        S = _login(f"{TAG}_staff@example.com", pw)

        # ---------- DAILY EXCEPTIONS ----------
        d = requests.get(f"{API}/reports/daily-exceptions", headers=A, timeout=15).json()
        assert d["total"] == len(d["rows"]) and sum(d["counts"].values()) == d["total"]
        assert d["caveats"]
        by_ref = {r["ref_id"]: r for r in d["rows"]}

        old = by_ref[t_old["task_id"]]
        assert old["kind"] == "unassigned_open" and old["overdue"] is False
        assert old["age_hours"] > 1000 and "overdue" not in old["reason"].lower()

        ovr = by_ref[t_overdue["task_id"]]
        assert ovr["kind"] == "overdue" and ovr["overdue"] is True and ovr["reason"].startswith("Overdue by")

        assert by_ref[t_ride["task_id"]]["kind"] == "transportation_attention"
        rq = by_ref[t_rereq["task_id"]]
        assert rq["kind"] == "re_requested_open" and rq["department_slug"] == "nursing"
        assert by_ref[a_open["alert_id"]]["ref_type"] == "alert" and by_ref[a_open["alert_id"]]["kind"] == "open_assistance_event"
        fa = by_ref[r_failed["receipt_id"]]
        assert fa["ref_type"] == "receipt" and fa["kind"] == "failed_action" and fa["department_slug"] == "maintenance"

        # department filter
        m = requests.get(f"{API}/reports/daily-exceptions", headers=A, params={"department": "maintenance"}, timeout=15).json()
        m_refs = {r["ref_id"] for r in m["rows"]}
        assert all(r["department_slug"] == "maintenance" for r in m["rows"])
        assert t_old["task_id"] in m_refs and t_hk["task_id"] not in m_refs and a_open["alert_id"] not in m_refs

        hk = requests.get(f"{API}/reports/daily-exceptions", headers=A, params={"department": "housekeeping"}, timeout=15).json()
        hk_refs = {r["ref_id"] for r in hk["rows"]}
        assert all(r["department_slug"] == "housekeeping" for r in hk["rows"])
        assert t_hk["task_id"] in hk_refs and t_old["task_id"] not in hk_refs and a_open["alert_id"] not in hk_refs

        # empty
        empty = requests.get(f"{API}/reports/daily-exceptions", headers=A, params={"department": "zzz_none"}, timeout=15).json()
        assert empty["rows"] == [] and empty["total"] == 0 and empty["counts"] == {} and empty["caveats"]

        # old-but-not-due is never in the overdue bucket
        assert not any(r["kind"] == "overdue" and r["overdue"] and not r["due_at"] for r in d["rows"])

        # ---------- DAILY CSV == filtered JSON ----------
        cr = requests.get(f"{API}/reports/daily-exceptions", headers=A, params={"format": "csv"}, timeout=15)
        assert cr.status_code == 200 and "text/csv" in cr.headers["content-type"]
        crows = list(csv.DictReader(io.StringIO(cr.text)))
        assert len(crows) == d["total"]
        assert {r["ref_id"] for r in crows} == set(by_ref.keys()) | {r["ref_id"] for r in d["rows"]}
        assert "ref_id" in crows[0] and "department_slug" in crows[0] and "receipt_id" in crows[0]

        cm = requests.get(f"{API}/reports/daily-exceptions", headers=A, params={"format": "csv", "department": "maintenance"}, timeout=15)
        assert {r["ref_id"] for r in csv.DictReader(io.StringIO(cm.text))} == m_refs

        # ---------- WEEKLY WORKLOAD ----------
        w = requests.get(f"{API}/reports/weekly-workload", headers=A, timeout=15).json()
        wr = {r["department_slug"]: r for r in w["rows"]}
        mrow = wr["maintenance"]
        assert mrow["still_open"] >= 2 and mrow["unassigned_open"] >= 1
        assert mrow["completed"] >= 1                       # t_done, completed today (in window)
        assert mrow["created"] >= 2                         # t_overdue + t_done are recent; t_old (400d) is NOT
        assert mrow["oldest_open_ref_id"] == t_old["task_id"] and mrow["oldest_open_age_hours"] > 9000
        techrow = next((s for s in mrow["by_staff"] if s["user_id"] == tech_id), None)
        assert techrow and techrow["completed_this_week"] >= 1 and techrow["open"] >= 1
        assert wr["housekeeping"]["still_open"] >= 1

        wm = requests.get(f"{API}/reports/weekly-workload", headers=A, params={"department": "maintenance"}, timeout=15).json()
        assert [r["department_slug"] for r in wm["rows"]] == ["maintenance"]

        wc = requests.get(f"{API}/reports/weekly-workload", headers=A, params={"format": "csv"}, timeout=15)
        assert "text/csv" in wc.headers["content-type"]
        wcrows = list(csv.DictReader(io.StringIO(wc.text)))
        assert len(wcrows) == len(w["rows"]) and "department_slug" in wcrows[0] and "staff_breakdown" in wcrows[0]
        mcsv = next(r for r in wcrows if r["department_slug"] == "maintenance")
        assert TECH_NAME in mcsv["staff_breakdown"]

        # ---------- role gate ----------
        for path in ("/reports/daily-exceptions", "/reports/weekly-workload"):
            assert requests.get(f"{API}{path}", headers=S, timeout=5).status_code == 403
            assert requests.get(f"{API}{path}", headers=S, params={"format": "csv"}, timeout=5).status_code == 403

        # ---------- no regression ----------
        assert requests.get(f"{API}/ops/overview", headers=A, timeout=15).status_code == 200
        assert requests.get(f"{API}/receipts", headers=A, params={"limit": 5}, timeout=10).status_code == 200
    finally:
        await db.staff_tasks.delete_many({"room": {"$regex": f"^{TAG}"}})
        await db.receipts.delete_many({"$or": [{"room": {"$regex": f"^{TAG}"}}, {"receipt_id": r_failed["receipt_id"]}]})
        await db.alerts.delete_many({"alert_id": a_open["alert_id"]})
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})


def test_reports():
    if not _backend_up():
        pytest.skip(f"backend not reachable at {BASE_URL}")
    asyncio.run(_run())
