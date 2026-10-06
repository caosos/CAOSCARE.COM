"""SC-9: any signed-in staff member can read department display names
(GET /departments/labels) so a department workspace shows "Nursing / Care",
not the slug. The full department list and every department change stay
admin-only.

Hits the real running backend over HTTP with synthetic users created
directly in db.users and deleted at the end (same pattern as
test_staff_department.py).

    TEST_API_BASE=http://127.0.0.1:8001 pytest tests/test_sc9_department_labels.py -q
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

TAG = f"sc9_{uuid.uuid4().hex[:8]}"
PW = "sc9-test-pw-123456"


def _backend_up() -> bool:
    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


def _login(email):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": PW}, timeout=5)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    pw_hash = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
    people = {
        "nurse": ("staff", "nursing"),
        "tech": ("staff", "maintenance"),
        "desk": ("front_desk", None),
        "admin": ("admin", None),
    }
    for key, (role, dept) in people.items():
        doc = {"user_id": uid("user"), "email": f"{TAG}_{key}@example.com", "name": f"SC9 {key}",
               "role": role, "auth_provider": "jwt", "password_hash": pw_hash,
               "created_at": now_utc().isoformat()}
        if dept:
            doc["department"] = dept
        await db.users.insert_one(doc)
    try:
        H = {k: _login(f"{TAG}_{k}@example.com") for k in people}

        # Nursing and maintenance staff read their human-readable names.
        for key, slug, label in (("nurse", "nursing", "Nursing / Care"), ("tech", "maintenance", "Maintenance")):
            r = requests.get(f"{API}/departments/labels", headers=H[key], timeout=5)
            assert r.status_code == 200, r.text
            labels = {d["slug"]: d["label"] for d in r.json()}
            assert labels.get(slug) == label, labels
            # Only slug + label: no contact emails, ids or flags.
            assert all(set(d) == {"slug", "label"} for d in r.json()), r.json()

        # Signed-out callers get nothing.
        assert requests.get(f"{API}/departments/labels", timeout=5).status_code == 401

        # Staff still cannot read the full list or change departments.
        for key in ("nurse", "tech"):
            assert requests.get(f"{API}/departments", headers=H[key], timeout=5).status_code == 403
            r = requests.post(f"{API}/departments", headers=H[key], json={"label": f"{TAG} dept"}, timeout=5)
            assert r.status_code == 403, r.text
            r = requests.patch(f"{API}/departments/anything", headers=H[key], json={"active": False}, timeout=5)
            assert r.status_code == 403, r.text
            r = requests.delete(f"{API}/departments/anything", headers=H[key], timeout=5)
            assert r.status_code == 403, r.text
        assert await db.departments.count_documents({"label": f"{TAG} dept"}) == 0

        # Front desk: its own department list is unchanged; full list still admin-only.
        r = requests.get(f"{API}/front-desk/request-categories", headers=H["desk"], timeout=5)
        assert r.status_code == 200 and any(d["slug"] == "nursing" for d in r.json()), r.text
        assert requests.get(f"{API}/departments", headers=H["desk"], timeout=5).status_code == 403

        # Admin: full list unchanged (full fields, including the seeded label).
        r = requests.get(f"{API}/departments", headers=H["admin"], timeout=5)
        assert r.status_code == 200, r.text
        nursing = next(d for d in r.json() if d["slug"] == "nursing")
        assert nursing["label"] == "Nursing / Care" and "department_id" in nursing
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})


def test_department_labels_for_staff():
    if not _backend_up():
        pytest.skip(f"backend not reachable at {BASE_URL}")
    asyncio.run(_run())
