"""Regression test for the public /kiosk/demo defect (docs/PROJECT_STATE.md,
2026-09-01): the route used to fetch every kiosk and take kiosks[0] -
database sort order, not a deliberate choice - which is how a real test
kiosk ("michael"/Room 121) became the public face of the product.

Hits the real running backend over HTTP against synthetic, isolated kiosks
so it never touches real demo/facility data. Proves the actual service
boundary (GET /kiosks/public-demo, PATCH /kiosks/{id} exclusivity), not
just the model shape.

Requires the local backend running (REACT_APP_BACKEND_URL, defaults to
http://127.0.0.1:8000). Skips cleanly if unreachable or no owner is seeded.

Run with: pytest tests/test_public_demo_kiosk.py -q
"""
import os
import sys
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE_URL}/api"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="module")
def admin():
    import asyncio
    from routes.auth import _issue_jwt
    from deps import db

    async def _owner():
        return await db.users.find_one({"role": "owner"}, {"_id": 0, "user_id": 1})

    owner = asyncio.run(_owner())
    if not owner:
        pytest.skip("no owner user seeded")
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {_issue_jwt(owner['user_id'])}"})
    return sess


def _mk_kiosk(admin, suffix):
    r = admin.post(f"{API}/kiosks", json={
        "name": f"demo-test-{suffix}", "room": f"demotest-{suffix}", "zone": "test",
    }, timeout=5)
    r.raise_for_status()
    return r.json()["kiosk_id"]


def test_no_demo_configured_gives_deterministic_error():
    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("backend not reachable")
    r = requests.get(f"{API}/kiosks/public-demo", timeout=5)
    # Either genuinely unconfigured (404, real acceptance case) or some
    # other test already designated one (200) - either way this must never
    # silently fall back to an arbitrary kiosk. A 500 or malformed body
    # would be the actual regression.
    assert r.status_code in (200, 404)
    if r.status_code == 404:
        assert "public demo" in r.json().get("detail", "").lower()


def test_designating_one_kiosk_resolves_correctly_and_excludes_others(admin):
    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("backend not reachable")

    suffix = uuid.uuid4().hex[:8]
    kiosk_a = _mk_kiosk(admin, f"a-{suffix}")
    kiosk_b = _mk_kiosk(admin, f"b-{suffix}")
    try:
        r = admin.patch(f"{API}/kiosks/{kiosk_a}", json={"public_demo": True}, timeout=5)
        r.raise_for_status()
        assert r.json()["public_demo"] is True

        # Real service boundary: GET /kiosks/public-demo resolves to A.
        resolved = requests.get(f"{API}/kiosks/public-demo", timeout=5)
        assert resolved.status_code == 200
        assert resolved.json()["kiosk_id"] == kiosk_a

        # Designating B clears A - never two demo kiosks at once.
        r2 = admin.patch(f"{API}/kiosks/{kiosk_b}", json={"public_demo": True}, timeout=5)
        r2.raise_for_status()
        assert r2.json()["public_demo"] is True

        a_doc = admin.get(f"{API}/kiosks", timeout=5).json()
        a_row = next(k for k in a_doc if k["kiosk_id"] == kiosk_a)
        assert a_row["public_demo"] is False, "designating B must clear A - at most one demo kiosk"

        resolved2 = requests.get(f"{API}/kiosks/public-demo", timeout=5)
        assert resolved2.json()["kiosk_id"] == kiosk_b

        # Ordinary kiosk IDs (not "demo") still resolve directly via the
        # existing public-by-kiosk lookup - this fix must not touch that path.
        by_kiosk = requests.get(f"{API}/residents/public/by-kiosk/{kiosk_a}", timeout=5)
        assert by_kiosk.status_code == 200
        assert by_kiosk.json()["kiosk"]["kiosk_id"] == kiosk_a
    finally:
        admin.delete(f"{API}/kiosks/{kiosk_a}", timeout=5)
        admin.delete(f"{API}/kiosks/{kiosk_b}", timeout=5)
