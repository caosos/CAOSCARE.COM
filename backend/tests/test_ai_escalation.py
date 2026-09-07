"""AI-triage escalation -> real, auditable nursing page (Level 1 directive,
2026-09-07). Fixes the Room 214 bleeding-test defect.

Tests A-F from the directive. Hits the running backend over HTTP + uses
deps.db for verification. Needs CAOSCARE_TEST_HOOKS=1 on the backend for the
failed-delivery simulation (test D). Skips cleanly if unreachable.

Run: pytest tests/test_ai_escalation.py -q
"""
import asyncio
import os
import sys
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FREQ = 319_500_000
PRESS_DECODED = {"subtype": "unknown", "battery_ok": 1, "switch1": "OPEN", "switch2": "OPEN",
                 "switch3": "OPEN", "switch4": "OPEN", "switch5": "CLOSED"}


def _rf_press(kiosk_id, seq, hex_):
    r = requests.post(f"{API}/rf/event", json={
        "kiosk_id": kiosk_id,
        "fingerprint": {"frequency_hz": FREQ, "modulation": "OOK", "bit_pattern_hex": hex_,
                        "bit_length": 56, "rssi": -0.11, "decoded": PRESS_DECODED},
        "sequence": seq,
    }, timeout=5)
    r.raise_for_status()
    return r.json()


def _escalate(**kw):
    r = requests.post(f"{API}/alerts/ai-escalate", json=kw, timeout=5)
    r.raise_for_status()
    return r.json()


async def _fixture(db, now_utc):
    room = f"aiesc_{uuid.uuid4().hex[:8]}"
    kiosk_id = f"kio_{uuid.uuid4().hex[:12]}"
    rf_device_id = f"rfd_{uuid.uuid4().hex[:12]}"
    resident_id = f"res_test_{uuid.uuid4().hex[:8]}"
    hex_ = uuid.uuid4().hex[:14]
    await db.residents.insert_one({"resident_id": resident_id, "name": "Helen Test", "room": room,
                                   "pendant_id": "x", "created_at": now_utc().isoformat()})
    await db.kiosks.insert_one({"kiosk_id": kiosk_id, "name": room, "room": room, "zone": "aiesc",
                               "is_central": False, "mac_address": None,
                               "created_at": now_utc().isoformat(), "rf_secret": None, "rf_seq": 0})
    await db.rf_devices.insert_one({
        "rf_device_id": rf_device_id, "label": "AI Esc Pendant", "resident_id": resident_id, "room": room,
        "fingerprint": {"frequency_hz": FREQ, "modulation": "OOK", "bit_pattern_hex": hex_,
                        "bit_length": 56, "rssi": -0.11, "decoded": None},
        "severity": "help", "match_threshold": 0.85, "enabled": True, "last_seen_at": None,
        "last_rssi": None, "press_count": 0, "created_at": now_utc().isoformat(), "created_by": None})
    return room, kiosk_id, rf_device_id, resident_id, hex_


async def _cleanup(db, room, kiosk_id, rf_device_id, resident_id, hex_):
    await db.residents.delete_one({"resident_id": resident_id})
    await db.kiosks.delete_one({"kiosk_id": kiosk_id})
    await db.rf_devices.delete_one({"rf_device_id": rf_device_id})
    ids = [a["alert_id"] async for a in db.alerts.find({"resident_id": resident_id}, {"alert_id": 1})]
    await db.alerts.delete_many({"resident_id": resident_id})
    await db.receipts.delete_many({"resident_id": resident_id})
    await db.rf_events.delete_many({"matched_device_id": rf_device_id})
    await db.staff_dispatches.delete_many({"alert_id": {"$in": ids}})
    await db.activation_events.delete_many({"room": room})
    await db.resident_aria_leases.delete_many({"room": room})


async def _run():
    from deps import db
    from models import now_utc
    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("backend not reachable")

    # ================= A: AI triage is not a human press =================
    room, kid, did, rid, hx = await _fixture(db, now_utc)
    try:
        p = _rf_press(kid, int(time.time() * 1000), hx)
        alert_id = p["alert_id"]
        a = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
        assert a["press_count"] == 1 and len(a["presses"]) == 1
        dev_before = (await db.rf_devices.find_one({"rf_device_id": did}, {"_id": 0})).get("press_count", 0)

        _escalate(reason="resident asked for a nurse", severity="assist",
                  alert_id=alert_id, activation_id=a["activation_id"], resident_id=rid, room=room)

        a2 = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
        assert a2["press_count"] == 1, "AI triage must NOT increment human press_count"
        assert len(a2["presses"]) == 1, "AI triage must NOT push a presses[] entry"
        assert len(a2.get("escalations", [])) == 1, "AI triage keeps its own history entry"
        dev_after = (await db.rf_devices.find_one({"rf_device_id": did}, {"_id": 0})).get("press_count", 0)
        assert dev_after == dev_before, "AI triage must NOT touch rf device human press_count"
    finally:
        await _cleanup(db, room, kid, did, rid, hx)

    # ========= B: assist event + emergency escalation, history kept ======
    room, kid, did, rid, hx = await _fixture(db, now_utc)
    try:
        p = _rf_press(kid, int(time.time() * 1000), hx)
        alert_id, act_id = p["alert_id"], (await db.alerts.find_one({"alert_id": p["alert_id"]}))["activation_id"]
        base = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
        assert base["severity"] == "assist"

        out = _escalate(reason="resident reports bleeding at age 84", severity="emergency",
                        alert_id=alert_id, activation_id=act_id, resident_id=rid, room=room)
        assert out["alert_id"] == alert_id, "same ResidentEvent - no duplicate"
        assert out["effective_severity"] == "emergency"
        assert out["human_press_count"] == 1

        b = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
        assert b["severity"] == "emergency", "later emergency must not be silently downgraded"
        assert b["original_severity"] == "assist", "history preserves the original severity"
        assert b["latest_escalation_reason"] == "resident reports bleeding at age 84"
        assert b["escalations"][0]["reason"] == "resident reports bleeding at age 84"
        assert b["escalations"][0]["requested_severity"] == "emergency"
        log_kinds = [e for e in b["event_log"] if e.get("field") == "ai_escalation"]
        assert log_kinds and log_kinds[-1]["from_severity"] == "assist" and log_kinds[-1]["to_severity"] == "emergency"

        # ===== C: successful local page is durable + proves accepted =====
        assert out["wording_state"] == "paged"
        assert out["dispatch"]["status"] in ("accepted", "delivered")
        sd = await db.staff_dispatches.find_one({"alert_id": alert_id}, {"_id": 0})
        for k in ("dispatch_id", "alert_id", "resident_id", "room", "department", "severity",
                  "reason", "requested_at", "delivery_mechanism", "status", "receipt_id"):
            assert sd.get(k) is not None, f"dispatch record missing {k}"
        assert sd["department"] == "Care/Nursing"
        assert sd["status"] in ("accepted", "delivered")
        assert b["dispatch_id"] == sd["dispatch_id"] and b["dispatch_status"] == sd["status"]

        # ===== F: staff view shows current emergency reason/severity =====
        assert b["severity"] == "emergency"
        assert b["latest_escalation_reason"] and b["latest_escalation_reason"] != b.get("message")

        # observability
        n_esc = await db.activation_events.count_documents(
            {"room": room, "layer": "resident_event", "event": "severity_escalated"})
        n_req = await db.activation_events.count_documents(
            {"room": room, "layer": "dispatch", "event": "page_requested"})
        n_acc = await db.activation_events.count_documents(
            {"room": room, "layer": "dispatch", "event": "page_accepted"})
        assert n_esc >= 1 and n_req >= 1 and n_acc >= 1

        # ===== E: repeat AI escalation - no dup event, no dup press ======
        _escalate(reason="still bleeding, worsening", severity="emergency",
                  alert_id=alert_id, activation_id=act_id, resident_id=rid, room=room)
        e = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
        assert e["press_count"] == 1, "repeat AI escalation must not add a human press"
        assert len(e["presses"]) == 1
        assert len(e["escalations"]) == 2, "each escalation keeps its own auditable entry"
        assert await db.alerts.count_documents(
            {"resident_id": rid, "status": {"$in": ["active", "acknowledged"]}}) == 1, "still ONE open event"
        assert await db.staff_dispatches.count_documents({"alert_id": alert_id}) == 2, "each page is durable"
    finally:
        await _cleanup(db, room, kid, did, rid, hx)

    # ================= D: failed page - no false success =================
    room, kid, did, rid, hx = await _fixture(db, now_utc)
    try:
        p = _rf_press(kid, int(time.time() * 1000), hx)
        alert_id, act_id = p["alert_id"], (await db.alerts.find_one({"alert_id": p["alert_id"]}))["activation_id"]
        out = _escalate(reason="resident reports a fall", severity="emergency",
                        alert_id=alert_id, activation_id=act_id, resident_id=rid, room=room,
                        simulate_delivery="fail")
        assert out["wording_state"] == "failed", "must not report a page when delivery failed"
        assert out["wording_state"] != "paged"
        assert out["dispatch"]["status"] == "failed"
        assert out["dispatch"]["failure_reason"]
        sd = await db.staff_dispatches.find_one({"alert_id": alert_id}, {"_id": 0})
        assert sd["status"] == "failed" and sd["failed_at"] and sd["failure_reason"]
        d = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
        assert d["dispatch_status"] == "failed"
        # the event still escalated (severity is real); only the page failed
        assert d["severity"] == "emergency"
        assert await db.activation_events.count_documents(
            {"room": room, "layer": "dispatch", "event": "page_failed"}) >= 1
    finally:
        await _cleanup(db, room, kid, did, rid, hx)


def test_ai_escalation_real_auditable_page():
    asyncio.run(_run())
