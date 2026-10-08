"""RQ-027: one Twilio path. Escalation SMS (level 2/3) and the live-line
on-call call go through routes/notification_delivery (httpx, no twilio
package): a notification record linked to the alert, an appended receipt with
provenance, "logged" without a provider, nothing sent for simulated work.
The provider is a spy; no real SMS or call is ever made.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes alert records; point DB_NAME at a scratch database",
                allow_module_level=True)

from deps import db  # noqa: E402
from routes.escalation_tick import run_tick  # noqa: E402
from routes.notification_delivery import provider_config  # noqa: E402
from routes.resident_activation import try_call_on_call_phone  # noqa: E402

TAG = f"rq027_{uuid.uuid4().hex[:8]}"
FAC = f"{TAG}_fac"
NOW = datetime.now(timezone.utc)
CALLS: list = []


class _Resp:
    def __init__(self, code, body):
        self.status_code, self._b, self.text = code, body, str(body)

    def json(self):
        return self._b


class Spy:
    status = 201

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, **kw):
        CALLS.append({"url": url, **kw})
        return _Resp(self.status, {"sid": f"SM{len(CALLS)}"})


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    CALLS.clear()
    Spy.status = 201
    monkeypatch.setattr(httpx, "AsyncClient", Spy)
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15550000000")
    monkeypatch.delenv("TWILIO_FROM_PHONE", raising=False)
    yield
    run(_clean())


async def _clean():
    await db.alerts.delete_many({"alert_id": {"$regex": f"^{TAG}"}})
    await db.escalation_rules.delete_many({"facility_id": FAC})
    await db.notifications.delete_many({"alert_id": {"$regex": f"^{TAG}"}})
    await db.receipts.delete_many({"related_object_id": {"$regex": f"^{TAG}"}})
    await db.residents.delete_many({"resident_id": {"$regex": f"^{TAG}"}})
    await db.facilities.delete_many({"facility_id": FAC})


async def _alert(name, age_s, **extra):
    a = {"alert_id": f"{TAG}_{name}", "room": f"{TAG}-R", "severity": "assist", "status": "active",
         "escalation_level": 0, "facility_id": FAC, "resident_name": "Test Resident",
         "created_at": (NOW - timedelta(seconds=age_s)).isoformat(), **extra}
    await db.alerts.insert_one(dict(a))
    return a


async def _rule():
    await db.escalation_rules.insert_one({
        "facility_id": FAC, "enabled": True, "level_2_seconds": 90, "level_3_seconds": 150,
        "notify_supervisor_phone": "+15551110001", "notify_oncall_phone": "+15551110002"})


async def _notes(name):
    return await db.notifications.find({"alert_id": f"{TAG}_{name}"}, {"_id": 0}).to_list(20)


def test_level2_and_level3_sms_use_one_path():
    async def go():
        await _rule()
        await _alert("a", 100)
        await run_tick(NOW)
        n2 = await _notes("a")
        await db.alerts.update_one({"alert_id": f"{TAG}_a"}, {"$set": {"created_at": (NOW - timedelta(seconds=200)).isoformat()}})
        await run_tick(NOW)
        return n2, await _notes("a")
    n2, n3 = run(go())
    assert [n["to"] for n in n2] == ["+15551110001"]            # supervisor at level 2
    assert sorted(n["to"] for n in n3) == ["+15551110001", "+15551110001", "+15551110002"]  # level 3 repeats supervisor, adds on-call
    assert all(n["channel"] == "sms" and n["status"] == "sent" and n["provider_message_id"] for n in n3)
    assert all(n["related_object_type"] == "alert" and n["related_object_id"] == f"{TAG}_a" for n in n3)
    assert len(CALLS) == 3  # level 2 sent 1, level 3 sent 2
    assert CALLS[0]["url"].endswith("/Accounts/AC_test/Messages.json")
    assert CALLS[0]["data"]["From"] == "+15550000000"
    rcpts = run(db.receipts.find({"related_object_id": f"{TAG}_a", "action_type": "alert_sms_attempt"}, {"_id": 0}).to_list(20))
    assert len(rcpts) == 3 and all(r["actor_id"] == "system:escalation" and r["authority"].startswith("escalation_rule:")
                                   and r["result_label"] == "unverified" and r["provider_refs"] for r in rcpts)
    assert {n["receipt_id"] for n in n3} <= {r["receipt_id"] for r in rcpts}


def test_on_call_call_and_from_phone_alias(monkeypatch):
    monkeypatch.delenv("TWILIO_FROM_NUMBER")
    monkeypatch.setenv("TWILIO_FROM_PHONE", "+15559990000")
    assert provider_config()["twilio_from"] == "+15559990000"

    async def go():
        await db.facilities.insert_one({"facility_id": FAC, "on_call_phone": "+15552220000"})
        a = await _alert("c", 5)
        return await try_call_on_call_phone(a)
    note = run(go())
    assert note["channel"] == "voice" and note["status"] == "sent"
    assert CALLS[0]["url"].endswith("/Calls.json")
    assert CALLS[0]["data"]["From"] == "+15559990000" and "<Say>" in CALLS[0]["data"]["Twiml"]
    r = run(db.receipts.find_one({"related_object_id": f"{TAG}_c", "action_type": "alert_call_attempt"}, {"_id": 0}))
    assert r["actor_id"] == "system:live_line" and r["result_label"] == "unverified"
    assert note["receipt_id"] == r["receipt_id"]


def test_no_provider_is_logged_never_sent(monkeypatch):
    monkeypatch.delenv("TWILIO_AUTH_TOKEN")

    async def go():
        await _rule()
        await _alert("n", 200)
        await run_tick(NOW)
        return await _notes("n")
    notes = run(go())
    assert len(notes) == 2 and all(n["status"] == "logged" for n in notes)
    assert CALLS == []
    rc = run(db.receipts.find({"related_object_id": f"{TAG}_n", "action_type": "alert_sms_attempt"}, {"_id": 0}).to_list(5))
    assert len(rc) == 2 and all(r["status"] == "completed" and r["result_label"] == "unverified" and not r["provider_refs"] for r in rc)


def test_provider_failure_is_failed(monkeypatch):
    Spy.status = 400

    async def go():
        await _rule()
        await _alert("f", 100)
        await run_tick(NOW)
        return await _notes("f")
    notes = run(go())
    assert [n["status"] for n in notes] == ["failed"]
    r = run(db.receipts.find_one({"related_object_id": f"{TAG}_f", "action_type": "alert_sms_attempt"}, {"_id": 0}))
    assert r["status"] == "failed" and r["result_label"] == "failed"


def test_simulated_work_never_reaches_provider():
    async def go():
        await _rule()
        await db.residents.insert_one({"resident_id": f"{TAG}_res", "name": "Synthetic", "room": "DEMO", "synthetic": True})
        await db.facilities.insert_one({"facility_id": FAC, "on_call_phone": "+15552220000"})
        a = await _alert("s", 200, resident_id=f"{TAG}_res")
        await run_tick(NOW)
        await try_call_on_call_phone(a)
        return await _notes("s")
    notes = run(go())
    assert CALLS == []
    assert len(notes) == 3 and all(n["status"] == "simulated" and n["simulated"] for n in notes)
    rc = run(db.receipts.find({"related_object_id": f"{TAG}_s", "action_type": {"$regex": "^alert_(sms|call)_attempt"}}, {"_id": 0}).to_list(9))
    assert len(rc) == 3 and all(r["result_label"] == "simulated" and r["simulated"] for r in rc)


def test_no_twilio_package_import():
    for f in ("escalation_tick.py", "resident_activation.py", "notification_delivery.py"):
        src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "routes", f)).read()
        assert "from twilio" not in src and "import twilio" not in src
