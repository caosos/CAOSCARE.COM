"""SC-8: every department notification about a request carries
related_object_type="task", related_object_id=<task id> and the receipt id
of the step that triggered it - real and simulated alike - so delivery
history traces back to the exact request. SC-16 still holds: a simulated
request's notification is recorded "simulated" and never reaches a provider.

In-process, DB-direct; refuses to run against the live `caoscare` DB.

    cd backend && MONGO_URL=mongodb://localhost:27017 DB_NAME=caoscare_sc8_test \
      JWT_SECRET=x pytest tests/test_sc8_notification_links.py -q
"""
import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test records; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import notifications  # noqa: E402
from routes.demo_kiosk import ensure_demo_room  # noqa: E402
from routes.departments import seed_default_departments  # noqa: E402
from routes.resident_requests import ResidentRequestInput, create_resident_request  # noqa: E402
from routes.transportation import TransportRequestInput, cancel_request, submit_transport_request  # noqa: E402

TAG = f"sc8_{uuid.uuid4().hex[:8]}"
RES = f"{TAG}_res"
ROOM = f"{TAG}-R"
EMAIL = f"{TAG}-staff@example.test"
DEMO = {}


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class ProviderSpy:
    calls: list = []

    def __init__(self, *a, **k):
        pass

    async def post(self, url, **kw):
        ProviderSpy.calls.append(url)

        class R:
            status_code = 200
            text = '{"id":"accepted"}'
        return R()


async def _clean():
    ids = [t["task_id"] for t in await db.staff_tasks.find(
        {"resident_id": {"$in": [RES, DEMO.get("resident_id")]}}, {"_id": 0, "task_id": 1}).to_list(200)]
    await db.receipts.delete_many({"related_object_id": {"$in": ids}})
    await db.notifications.delete_many({"$or": [{"related_object_id": {"$in": ids}}, {"task_id": {"$in": ids}},
                                                {"to": EMAIL}]})
    await db.staff_tasks.delete_many({"task_id": {"$in": ids}})
    await db.residents.delete_many({"resident_id": RES})
    await db.users.delete_many({"email": EMAIL})


async def _setup():
    await seed_default_departments()
    DEMO.update(await ensure_demo_room())
    await _clean()
    await db.residents.insert_one({"resident_id": RES, "name": f"{TAG} Resident", "room": ROOM})
    for dept in ("maintenance", "transportation"):
        await db.departments.update_one({"slug": dept}, {"$unset": {"contact_email": ""}})
    await db.users.insert_many([{"user_id": f"{TAG}_{d}", "email": EMAIL, "name": d, "role": "staff",
                                 "department": d} for d in ("maintenance", "transportation")])


@pytest.fixture(autouse=True)
def env(monkeypatch):
    import httpx
    ProviderSpy.calls = []
    monkeypatch.setattr(httpx, "AsyncClient", ProviderSpy)
    monkeypatch.setattr(notifications, "RESEND_KEY", "re_live_key_for_test")
    run(_setup())
    yield
    run(_clean())


async def _notes(task_id):
    return await db.notifications.find({"related_object_id": task_id}, {"_id": 0}).sort("created_at", 1).to_list(50)


def _linked(n, task_id, receipt_id):
    return (n["related_object_type"] == "task" and n["related_object_id"] == task_id
            and n["receipt_id"] == receipt_id)


def test_real_request_and_repeat_are_linked_to_task_and_receipt():
    async def go():
        inp = ResidentRequestInput(category="maintenance", resident_id=RES, room=ROOM, source="aria_voice",
                                   resident_words="My sink is leaking", summary="My sink is leaking")
        first = await create_resident_request(inp)
        again = await create_resident_request(inp)
        assert again["duplicate"] and again["task_id"] == first["task_id"]
        notes = await _notes(first["task_id"])
        assert len(notes) == 2
        assert _linked(notes[0], first["task_id"], first["receipt_id"])
        assert _linked(notes[1], first["task_id"], again["receipt_id"])
        # Real work still reaches the provider (one call per real notification).
        assert all(n["status"] == "sent" and not n.get("simulated") for n in notes)
        assert ProviderSpy.calls == ["https://api.resend.com/emails"] * 2
    run(go())


def test_ride_request_and_cancel_are_linked():
    async def go():
        out = await submit_transport_request(TransportRequestInput(
            resident_id=RES, room=ROOM, purpose="pharmacy", requested_for_date="2026-10-09"))
        cancelled = await cancel_request(out["task_id"], source="aria_voice", reason="feeling better")
        notes = await _notes(out["task_id"])
        assert len(notes) == 2
        assert _linked(notes[0], out["task_id"], out["receipt_id"])
        assert _linked(notes[1], out["task_id"], cancelled["receipt_id"])
    run(go())


def test_simulated_request_linked_and_never_sent():
    async def go():
        words = "The bathroom sink keeps dripping."
        out = await create_resident_request(ResidentRequestInput(
            category="maintenance", resident_id=DEMO["resident_id"], room=DEMO["room"],
            resident_words=words, summary=words, source="aria_voice"))
        notes = await _notes(out["task_id"])
        assert notes and all(_linked(n, out["task_id"], out["receipt_id"]) for n in notes)
        assert all(n["status"] == "simulated" and n["task_id"] == out["task_id"] for n in notes)
        assert ProviderSpy.calls == []
    run(go())


def test_notify_department_requires_the_link():
    with pytest.raises(TypeError):
        run(notifications.notify_department("maintenance", "s", "b"))
