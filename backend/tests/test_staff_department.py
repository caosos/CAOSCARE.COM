"""Staff department assignment - admin can create/edit a staff member and
set / change / clear their department, validated against the real
Department list (docs/ADMIN_OPERATIONS_AUDIT.md P0 #1).

Hits the real running backend over HTTP with its own synthetic admin +
staff fixtures (created directly in db.users, deleted at the end) so it
never depends on demo-seed credentials and never touches real accounts.
All DB work happens inside a single asyncio.run() call - Motor binds its
client to one event loop for the process (same constraint the sibling
test_resident_events.py works around).

Run with (pointed at a backend started from THIS worktree):
    TEST_API_BASE=http://127.0.0.1:8001 pytest tests/test_staff_department.py -q
Defaults to http://127.0.0.1:8000. Skips cleanly if unreachable.
"""
import asyncio
import os
import sys
import uuid

import bcrypt
import pytest
import requests

BASE_URL = os.environ.get("TEST_API_BASE", os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")
API = f"{BASE_URL}/api"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TAG = f"swdept_{uuid.uuid4().hex[:8]}"


def _backend_up() -> bool:
    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


async def _run():
    from deps import db
    from models import uid, now_utc

    pw = "test-admin-pw-123"
    admin_id = uid("user")
    admin_email = f"{TAG}_admin@example.com"
    await db.users.insert_one({
        "user_id": admin_id, "email": admin_email, "name": "Dept Test Admin",
        "role": "admin", "auth_provider": "jwt",
        "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
        "created_at": now_utc().isoformat(),
    })
    try:
        r = requests.post(f"{API}/auth/login", json={"email": admin_email, "password": pw}, timeout=5)
        r.raise_for_status()
        H = {"Authorization": f"Bearer {r.json()['token']}"}

        # --- default departments: renamed label, unchanged slug ---
        depts = requests.get(f"{API}/departments", headers=H, timeout=5).json()
        nursing = next((d for d in depts if d["slug"] == "nursing"), None)
        assert nursing is not None, "seeded 'nursing' department missing"
        assert nursing["label"] == "Nursing / Care", nursing
        slugs = {d["slug"] for d in depts}
        for expected in ("maintenance", "housekeeping", "transportation", "kitchen", "administration"):
            assert expected in slugs, f"missing default department {expected}"

        # --- create with a department ---
        r = requests.post(f"{API}/staff", headers=H, json={
            "email": f"{TAG}_s1@example.com", "name": "Maint Person",
            "password": "staff-pw-123456", "role": "staff", "department": "maintenance",
        }, timeout=5)
        assert r.status_code == 200, r.text
        sid = r.json()["user_id"]
        assert r.json()["department"] == "maintenance"

        # --- create rejects an unknown department ---
        r = requests.post(f"{API}/staff", headers=H, json={
            "email": f"{TAG}_bad@example.com", "name": "Bad", "password": "staff-pw-123456",
            "role": "staff", "department": "not_a_real_department",
        }, timeout=5)
        assert r.status_code == 400, r.text

        # --- list shows the department ---
        lst = requests.get(f"{API}/staff", headers=H, timeout=5).json()
        row = next((u for u in lst if u["user_id"] == sid), None)
        assert row and row["department"] == "maintenance"

        # --- change department ---
        r = requests.patch(f"{API}/staff/{sid}", headers=H, json={"department": "housekeeping"}, timeout=5)
        assert r.status_code == 200, r.text
        assert r.json()["department"] == "housekeeping"

        # --- clear department with "" ---
        r = requests.patch(f"{API}/staff/{sid}", headers=H, json={"department": ""}, timeout=5)
        assert r.status_code == 200, r.text
        assert r.json().get("department") in (None, "")

        # --- patch rejects an unknown department ---
        r = requests.patch(f"{API}/staff/{sid}", headers=H, json={"department": "bogus"}, timeout=5)
        assert r.status_code == 400, r.text

        # --- edit name + role together ---
        r = requests.patch(f"{API}/staff/{sid}", headers=H, json={"name": "Renamed Person", "role": "front_desk"}, timeout=5)
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "Renamed Person" and r.json()["role"] == "front_desk"

        # --- an admin cannot demote their own account out of the admin tier ---
        r = requests.patch(f"{API}/staff/{admin_id}", headers=H, json={"role": "staff"}, timeout=5)
        assert r.status_code == 400, r.text
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})


def test_staff_department_assignment():
    if not _backend_up():
        pytest.skip(f"backend not reachable at {BASE_URL}")
    asyncio.run(_run())
