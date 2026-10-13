"""Family alert delivery derives simulation provenance from resident truth."""
import asyncio
from copy import deepcopy

from routes import notification_delivery, notifications, receipts
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE


class Cursor:
    def __init__(self, docs):
        self.docs = docs

    async def to_list(self, limit):
        return deepcopy(self.docs[:limit])


class Collection:
    def __init__(self, docs=None):
        self.docs = [deepcopy(doc) for doc in (docs or [])]

    def find(self, query, projection=None):
        return Cursor([doc for doc in self.docs if all(doc.get(k) == v for k, v in query.items())])

    async def find_one(self, query, projection=None):
        rows = [doc for doc in self.docs if all(doc.get(k) == v for k, v in query.items())]
        return deepcopy(rows[0]) if rows else None

    async def insert_one(self, doc):
        self.docs.append(deepcopy(doc))

    async def update_one(self, query, update):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                doc.update(deepcopy(update.get("$set") or {}))
                break


class Store:
    def __init__(self, resident, contact, *, persist_resident=True):
        self.residents = Collection([resident] if persist_resident else [])
        self.family_contacts = Collection([contact])
        self.notifications = Collection()


class Response:
    status_code = 200
    text = "accepted"

    def __init__(self, provider_id):
        self.provider_id = provider_id

    def json(self):
        return {"id": self.provider_id, "sid": self.provider_id}


class ProviderClient:
    calls = []

    def __init__(self, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        self.calls.append((url, deepcopy(kwargs)))
        return Response(f"provider-{len(self.calls)}")


def _run(monkeypatch, resident, *, channels=("phone", "email"), persist_resident=True):
    contact = {
        "contact_id": "contact-1", "resident_id": resident["resident_id"],
        "name": "Family", "relationship": "family", "notify_on": "emergency",
    }
    if "phone" in channels:
        contact["phone"] = "+15550001111"
    if "email" in channels:
        contact["email"] = "family@example.test"
    store = Store(resident, contact, persist_resident=persist_resident)
    receipt_calls = []

    async def create_receipt(**kwargs):
        receipt_calls.append(deepcopy(kwargs))
        return {"receipt_id": f"receipt-{len(receipt_calls)}"}

    ProviderClient.calls = []
    monkeypatch.setattr(notifications, "db", store)
    monkeypatch.setattr(notification_delivery, "db", store)
    monkeypatch.setattr(notification_delivery.httpx, "AsyncClient", ProviderClient)
    monkeypatch.setattr(receipts, "create_receipt", create_receipt)
    monkeypatch.setenv("RESEND_API_KEY", "configured")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "configured")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "configured")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15559990000")
    alert = {
        "alert_id": "alert-1", "receipt_id": "alert-origin",
        "resident_id": resident["resident_id"], "resident_name": "Resident",
        "room": resident.get("room"), "severity": "emergency",
    }
    asyncio.run(notifications.notify_family_for_alert(alert))
    return store.notifications.docs, receipt_calls, ProviderClient.calls


def test_living_community_family_sms_and_email_never_reach_providers(monkeypatch):
    resident = {
        "resident_id": "sim:resident:001", "room": "SIM-001", "synthetic": True,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    }
    notes, receipt_calls, provider_calls = _run(monkeypatch, resident)
    assert provider_calls == []
    assert {note["channel"] for note in notes} == {"sms", "email"}
    assert all(note["status"] == "simulated" for note in notes)
    assert all(note["simulation_scope"] == SIMULATION_SCOPE for note in notes)
    assert all(note["simulation_community_id"] == COMMUNITY_ID for note in notes)
    assert len(receipt_calls) == 2
    for call in receipt_calls:
        provenance = call["provenance"]
        assert provenance["simulated"] is True
        assert provenance["simulation_scope"] == SIMULATION_SCOPE
        assert provenance["simulation_community_id"] == COMMUNITY_ID
        assert provenance["result_label"] == "simulated"


def test_legacy_demo_synthetic_resident_remains_suppressed(monkeypatch):
    notes, receipt_calls, provider_calls = _run(
        monkeypatch,
        {"resident_id": "demo-resident", "room": "DEMO", "synthetic": True},
        channels=("phone",),
    )
    assert provider_calls == []
    assert notes[0]["status"] == "simulated"
    assert notes[0]["simulation_scope"] == "demo_room"
    assert notes[0].get("simulation_community_id") is None
    assert receipt_calls[0]["provenance"]["simulation_scope"] == "demo_room"


def test_real_resident_family_delivery_preserves_provider_path(monkeypatch):
    notes, receipt_calls, provider_calls = _run(
        monkeypatch,
        {"resident_id": "resident-real", "room": "101", "synthetic": False},
    )
    assert len(provider_calls) == 2
    assert all(note["status"] == "sent" and not note["simulated"] for note in notes)
    assert all(call["provenance"]["simulated"] is False for call in receipt_calls)
    assert all(call["provenance"]["result_label"] == "unverified" for call in receipt_calls)


def test_exact_community_markers_fail_closed_if_synthetic_flag_is_missing(monkeypatch):
    notes, _receipt_calls, provider_calls = _run(
        monkeypatch,
        {"resident_id": "sim:resident:002", "room": "SIM-002", "synthetic": False,
         "simulation_scope": SIMULATION_SCOPE, "simulation_community_id": COMMUNITY_ID},
        channels=("email",),
    )
    assert provider_calls == []
    assert notes[0]["status"] == "simulated"


def test_reserved_community_resident_id_stays_suppressed_if_row_is_unavailable(monkeypatch):
    notes, _receipt_calls, provider_calls = _run(
        monkeypatch,
        {"resident_id": "sim:resident:003", "room": "SIM-003"},
        channels=("email",),
        persist_resident=False,
    )
    assert provider_calls == []
    assert notes[0]["status"] == "simulated"
    assert notes[0]["simulation_scope"] == SIMULATION_SCOPE
    assert notes[0]["simulation_community_id"] == COMMUNITY_ID
