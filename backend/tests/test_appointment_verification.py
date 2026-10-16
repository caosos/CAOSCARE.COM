"""Appointment verification and provenance (aria-appointment-verification-001,
#166 owner requirement 2026-10-16).

"I think my cardiologist is Tuesday at 10." A remembered appointment is
REPORTED, never VERIFIED; an authoritative confirmation decides the time and
the difference is said out loud; conflicting confirmations are spelled out,
never resolved by guessing; a change supersedes and a cancellation cancels;
every write has a receipt with provenance.

A-G match the acceptance list. DB-direct through deps.db with throwaway
residents; the facility timezone comes from the facility record, never a
hard-coded zone.
"""
import asyncio
import os
import re
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deps import db  # noqa: E402
from routes import appointment_truth as truth  # noqa: E402
from routes.actor_context import ActorContext, actor_system  # noqa: E402
from routes.appointments import CheckInput, ReportInput, check, report  # noqa: E402
from routes.facility_local_time import facility_clock, facility_tz  # noqa: E402
from routes.resident_appointments import record_source  # noqa: E402

run = asyncio.get_event_loop().run_until_complete
CERTAIN = re.compile(r"\b(verified by|that's verified|confirmed for)\b", re.I)
CONTACTED = re.compile(r"\b(called|contacted|spoke (with|to)|phoned|reached) (the|your) (office|doctor|clinic)\b", re.I)

STAFF = ActorContext(actor_id="user_appt_staff", actor_type="real-human", identity_basis="authenticated",
                     channel="staff_ui", name="Front Desk Test", role="front_desk")


def _day(offset: int) -> str:
    tz = run(facility_tz())
    return (date.fromisoformat(facility_clock(tz)["date"]) + timedelta(days=offset)).isoformat()


@pytest.fixture()
def resident():
    rid, room = f"res_appt_{uuid.uuid4().hex[:8]}", f"T-APPT-{uuid.uuid4().hex[:5]}"
    run(db.residents.insert_one({"resident_id": rid, "name": "Appointment Test Resident",
                                 "preferred_name": "Pat", "room": room}))
    yield rid, room
    ids = [a["appointment_id"] for a in run(db.resident_appointments.find({"resident_id": rid}).to_list(50))]
    run(db.receipts.delete_many({"related_object_id": {"$in": ids}}))
    run(db.resident_appointments.delete_many({"resident_id": rid}))
    run(db.staff_tasks.delete_many({"resident_id": rid}))
    run(db.call_sessions.delete_many({"resident_id": rid}))
    run(db.residents.delete_one({"resident_id": rid}))


def _say(rid, room, day, time=None, provider="cardiologist", **kw):
    return run(report(ReportInput(resident_id=rid, room=room, provider=provider, date=day, time=time,
                                  resident_words=f"I think my {provider} is {day} at {time}", **kw)))


def _staff(rid, kind, day=None, time=None, intent="confirm", ref="msg_test", provider="cardiologist", **kw):
    claim = {"source_type": kind, "intent": intent, "date": day, "time": time, "provider": provider,
             "evidence_ref": ref, **kw}
    return run(record_source(resident_id=rid, room=None, claim=claim, actor=STAFF))


def _ask(rid, room, **kw):
    return run(check(CheckInput(resident_id=rid, room=room, **kw)))


def _receipts(appt_id):
    return run(db.receipts.find({"related_object_id": appt_id}, {"_id": 0}).sort("created_at", 1).to_list(50))


# ---------- A. resident-reported, no confirmation ----------

def test_a_resident_report_is_reported_not_verified(resident):
    rid, room = resident
    tue = _day(5)
    r = _say(rid, room, tue, "10:00")
    assert r["recorded"] and r["status"] == truth.REPORTED and r["verified"] is False
    assert "isn't verified yet" in r["spoken"] and "10 AM" in r["spoken"]
    assert not CERTAIN.search(r["spoken"]) and not CONTACTED.search(r["spoken"])

    ans = _ask(rid, room, about="cardiologist", focus="time")
    assert ans["appointments"][0]["status"] == truth.REPORTED and ans["appointments"][0]["verified"] is False
    assert "isn't verified yet" in ans["spoken"]

    [rc] = _receipts(r["appointment_id"])
    assert rc["action_type"] == "appointment_created" and rc["receipt_id"] == r["receipt_id"]
    assert rc["identity_basis"] == "unverified_room_claim" and rc["actor_id"] == rid and rc["channel"] == "aria_voice"
    assert rc["authority"] == f"resident_claim:room:{room}" and rc["result_label"] == "unverified"
    assert rc["before_state"] is None and rc["after_state"]["status"] == truth.REPORTED
    assert rc["correlation_id"] == rc["receipt_id"] and rc["next_state"] == truth.REPORTED


def test_a_nothing_on_record_never_guesses(resident):
    rid, room = resident
    ans = _ask(rid, room, focus="time")
    assert ans["found"] is False and "don't have an appointment" in ans["spoken"]
    ans = _ask(rid, room, about="dentist", date=_day(1), focus="date")
    assert "don't have a dentist appointment on tomorrow" in ans["spoken"]


def test_a_a_time_the_resident_never_said_is_not_recorded(resident):
    rid, room = resident
    r = run(report(ReportInput(resident_id=rid, room=room, provider="dentist", date=_day(3), time="15:00",
                               time_as_said="3 PM", conversation_session_id="rt_appt_none")))
    assert r["recorded"] is False and "haven't noted one" in r["spoken"]
    assert run(db.resident_appointments.count_documents({"resident_id": rid})) == 0
    past = run(report(ReportInput(resident_id=rid, room=room, provider="dentist", date=_day(-2))))
    assert past["recorded"] is False and past["needs_clarification"] is True


# ---------- B. resident 10:00, authoritative confirmation 10:30 ----------

def test_b_confirmation_wins_and_the_discrepancy_is_said(resident):
    rid, room = resident
    tue = _day(5)
    first = _say(rid, room, tue, "10:00")
    appt = _staff(rid, "email_confirmation", tue, "10:30", ref="email_msg_123")
    assert appt["appointment_id"] == first["appointment_id"]               # same appointment, not a second
    assert appt["status"] == truth.VERIFIED and appt["time"] == "10:30" and appt["verified_by"] == "email_confirmation"
    assert appt["last_verified_at"] and appt["discrepancy_source_ids"] == [appt["sources"][0]["source_id"]]

    ans = _ask(rid, room, about="cardiologist", focus="time")["spoken"]
    assert "10:30 AM" in ans and "verified by the confirmation email" in ans
    assert "You'd told me 10 AM, but the confirmation says 10:30 AM." in ans

    # Remembering the old time again is a discrepancy, not a reason to doubt the confirmation.
    again = _say(rid, room, tue, "10:00")
    assert again["status"] == truth.VERIFIED and "10:30 AM" in again["spoken"]

    rcs = _receipts(appt["appointment_id"])
    assert [r["action_type"] for r in rcs] == ["appointment_created", "appointment_verified", "appointment_source_added"]
    created, verified = rcs[0], rcs[1]
    assert verified["parent_receipt_id"] == created["receipt_id"] and verified["correlation_id"] == created["receipt_id"]
    assert verified["identity_basis"] == "authenticated" and verified["actor_id"] == STAFF.actor_id
    assert verified["authority"] == "staff_entry:front_desk" and verified["result_label"] == "verified"
    assert "email_msg_123" in verified["provider_refs"]
    assert verified["before_state"]["time"] == "10:00" and verified["after_state"]["time"] == "10:30"


def test_b_resident_saying_it_moved_reopens_the_question(resident):
    rid, room = resident
    tue = _day(5)
    _staff(rid, "calendar_confirmation", tue, "10:30", ref="cal_evt_9")
    moved = _say(rid, room, _day(7), "14:00", says_changed=True)
    assert moved["status"] == truth.NEEDS_CONFIRMATION
    assert "needs to be confirmed again" in moved["spoken"] and "10:30 AM" in moved["spoken"]


# ---------- C. two authoritative sources conflict ----------

def test_c_conflict_is_spelled_out_then_resolved_by_staff(resident):
    rid, room = resident
    tue, wed = _day(5), _day(6)
    _staff(rid, "email_confirmation", tue, "10:30", ref="email_a")
    appt = _staff(rid, "calendar_confirmation", wed, "09:00", ref="cal_b")
    assert appt["status"] == truth.CONFLICT and appt["date"] is None and appt["time"] is None
    assert len(appt["candidate_source_ids"]) == 2 and appt["last_verified_at"] is None

    ans = _ask(rid, room, about="cardiologist", focus="date")["spoken"]
    assert "can't tell you for certain" in ans and "10:30 AM" in ans and "9 AM" in ans
    assert "confirmation email" in ans and "calendar confirmation" in ans
    assert "can't say for certain which day" in ans and "That day is confirmed" not in ans

    with pytest.raises(HTTPException) as e:                           # resolving needs a staff attestation
        _staff(rid, "staff_entry", wed, "09:00", intent="resolve", ref=None)
    assert e.value.status_code == 422
    done = _staff(rid, "staff_entry", wed, "09:00", intent="resolve", ref=None, staff_verified=True,
                  evidence_note="Called back by the office's portal message; front desk checked it")
    assert done["status"] == truth.VERIFIED and done["date"] == wed and done["time"] == "09:00"
    assert len(done["superseded_source_ids"]) == 2
    rcs = _receipts(done["appointment_id"])
    assert [r["action_type"] for r in rcs] == ["appointment_created", "appointment_conflict",
                                               "appointment_conflict_resolved"]
    assert [r["result_label"] for r in rcs] == ["verified", "unverified", "verified"]   # a conflict verifies nothing


# ---------- D. a change supersedes the older verified record ----------

def test_d_change_supersedes_and_keeps_history(resident):
    rid, room = resident
    tue, thu = _day(5), _day(7)
    _say(rid, room, tue, "10:00")
    old = _staff(rid, "email_confirmation", tue, "10:30", ref="email_1")
    new = _staff(rid, "email_confirmation", thu, "14:00", intent="change", ref="email_2")
    assert new["appointment_id"] == old["appointment_id"]
    assert new["status"] == truth.CHANGED and (new["date"], new["time"]) == (thu, "14:00")
    assert len(new["sources"]) == 3 and len(new["superseded_source_ids"]) == 2   # nothing deleted
    assert new["discrepancy_source_ids"] == []                                    # the old memory is history now

    ans = _ask(rid, room, about="cardiologist", focus="change")["spoken"]
    assert "2 PM" in ans and "It was changed - it used to be" in ans and "10:30 AM" in ans
    assert "no record of it being changed" not in ans
    rc = _receipts(new["appointment_id"])[-1]
    assert rc["action_type"] == "appointment_changed"
    assert rc["before_state"]["time"] == "10:30" and rc["after_state"]["time"] == "14:00"

    # "Did my doctor change it?" when nothing changed says so.
    _staff(rid, "email_confirmation", _day(9), "08:15", ref="email_eye", provider="eye doctor")
    eye = _ask(rid, room, about="eye doctor", focus="change")["spoken"]
    assert "I don't have any record of it being changed" in eye


# ---------- E. cancelled ----------

def test_e_cancellation(resident):
    rid, room = resident
    tue = _day(5)
    _staff(rid, "email_confirmation", tue, "10:30", ref="email_1")

    # The resident saying it was cancelled does not cancel it.
    claim = _say(rid, room, tue, None, says_changed=False)
    run(record_source(resident_id=rid, room=room, claim={"source_type": "resident_speech", "intent": "cancel",
                                                          "provider": "cardiologist"},
                      actor=ActorContext(actor_id=rid, actor_type="real-human", identity_basis="unverified_room_claim",
                                         channel="aria_voice", role="resident")))
    still = _ask(rid, room, about="cardiologist")
    assert still["appointments"][0]["status"] == truth.NEEDS_CONFIRMATION
    assert "it was cancelled" in still["spoken"]

    gone = _staff(rid, "email_confirmation", intent="cancel", ref="email_cxl")
    assert gone["appointment_id"] == claim["appointment_id"] and gone["status"] == truth.CANCELLED
    assert gone["date"] is None and gone["last_verified_at"]
    ans = _ask(rid, room, about="cardiologist")["spoken"]
    assert "was cancelled, according to the confirmation email" in ans
    assert _ask(rid, room)["found"] is False                     # "my appointment" skips cancelled ones
    assert _receipts(gone["appointment_id"])[-1]["action_type"] == "appointment_cancelled"

    with pytest.raises(HTTPException) as e:                       # cancelling something not on record
        _staff(rid, "email_confirmation", intent="cancel", ref="email_x", provider="podiatrist")
    assert e.value.status_code == 404


# ---------- F. timezone correctness ----------

def test_f_dst_instants_and_facility_relative_days():
    chi = "America/Chicago"
    assert truth.starts_at_utc("2026-10-30", "10:30", chi) == "2026-10-30T15:30:00+00:00"   # CDT
    assert truth.starts_at_utc("2026-11-02", "10:30", chi) == "2026-11-02T16:30:00+00:00"   # CST
    assert truth.starts_at_utc("2026-03-09", "10:30", chi) == "2026-03-09T15:30:00+00:00"   # after spring forward
    # 23:30 in Chicago is already the next day in UTC; "tomorrow" follows the facility clock.
    late = facility_clock(chi, datetime(2026, 10, 20, 4, 30, tzinfo=timezone.utc))
    assert late["date"] == "2026-10-19"
    assert truth.say_day("2026-10-20", late["date"]).startswith("tomorrow, Tuesday, October 20")
    assert truth.say_day("2026-10-20", "2026-10-20").startswith("today")


def test_f_same_instant_in_two_zones_is_not_a_conflict(resident):
    rid, room = resident
    day = _day(5)
    tz = run(facility_tz())
    _staff(rid, "email_confirmation", day, "10:30", ref="email_ny", timezone="America/New_York")
    from zoneinfo import ZoneInfo
    local = datetime.combine(date.fromisoformat(day), datetime.strptime("10:30", "%H:%M").time(),
                             ZoneInfo("America/New_York")).astimezone(ZoneInfo(tz))
    appt = _staff(rid, "calendar_confirmation", local.date().isoformat(), local.strftime("%H:%M"), ref="cal_local",
                  timezone=tz)
    assert appt["status"] == truth.VERIFIED                          # one instant, two clocks
    assert appt["starts_at_utc"] == truth.starts_at_utc(day, "10:30", "America/New_York")
    ny = {"date": day, "time": "10:30", "timezone": "America/New_York"}
    assert truth.say_when(ny, _day(0), "America/Chicago").endswith("at 10:30 AM (New York time)")
    assert "(" not in truth.say_when(ny, _day(0), "America/New_York")


def test_f_tomorrow_on_the_facility_calendar(resident):
    rid, room = resident
    _staff(rid, "staff_entry", _day(1), "13:00", ref=None, staff_verified=True)
    ans = _ask(rid, room, about="cardiologist", focus="date")
    assert ans["appointments"][0]["days_away"] == 1 and "tomorrow" in ans["spoken"]
    assert "That day is confirmed." in ans["spoken"]
    assert "verified by the staff-verified entry by Front Desk Test" in ans["spoken"]


# ---------- G. natural, never overstated ----------

def test_g_unverified_answers_never_sound_certain(resident):
    rid, room = resident
    _say(rid, room, _day(4), "11:00", provider="dentist")
    family = run(record_source(resident_id=rid, room=None, actor=STAFF, claim={
        "source_type": "family_entry", "intent": "confirm", "date": _day(4), "time": "11:30",
        "provider": "dentist", "reported_by_name": "Susan"}))
    assert family["status"] == truth.NEEDS_CONFIRMATION                  # family can't verify either
    ans = _ask(rid, room, about="dentist", focus="time")["spoken"]
    assert "doesn't agree" in ans and "Susan's note" in ans and "11 AM" in ans and "11:30 AM" in ans
    for spoken in (ans, _ask(rid, room, about="dentist", focus="date")["spoken"]):
        assert not CERTAIN.search(spoken) and not CONTACTED.search(spoken)
        assert len(spoken) < 400


def test_g_an_office_call_needs_a_connected_call(resident):
    rid, room = resident
    with pytest.raises(HTTPException) as e:
        _staff(rid, "provider_call", _day(5), "10:30", ref="call_never_happened")
    assert e.value.status_code == 422 and "not reached" in e.value.detail
    run(db.call_sessions.insert_one({"call_id": f"call_{rid}", "resident_id": rid, "kind": "outbound",
                                     "state": "ended", "connected_at": datetime.now(timezone.utc).isoformat()}))
    appt = _staff(rid, "provider_call", _day(5), "10:30", ref=f"call_{rid}")
    assert appt["status"] == truth.VERIFIED and appt["verified_by"] == "provider_call"
    assert "the call with the office" in _ask(rid, room, about="cardiologist")["spoken"]


def test_g_ride_answer_reports_only_the_real_request(resident):
    rid, room = resident
    day = _day(5)
    _staff(rid, "email_confirmation", day, "10:30", ref="email_r", transport_notes="needs a wheelchair van")
    ans = _ask(rid, room, about="cardiologist", focus="ride")["spoken"]
    assert "I don't see a ride request for that day" in ans and "needs a wheelchair van" in ans
    run(db.staff_tasks.insert_one({"task_id": f"task_{rid}_ride", "resident_id": rid, "room": room,
                                   "category": "transportation", "status": "pending", "requested_for_date": day,
                                   "title": "Ride to cardiologist", "created_at": datetime.now(timezone.utc).isoformat()}))
    ans = _ask(rid, room, about="cardiologist", focus="ride")["spoken"]
    assert "ride request for that day, but it isn't booked yet" in ans


def test_g_every_write_has_a_receipt_with_provenance(resident):
    rid, room = resident
    tue = _day(5)
    _say(rid, room, tue, "10:00")
    _staff(rid, "email_confirmation", tue, "10:30", ref="e1")
    _staff(rid, "calendar_confirmation", tue, "11:00", ref="c1")
    appt = _staff(rid, "staff_entry", tue, "10:30", intent="resolve", ref=None, staff_verified=True)
    sys_actor = actor_system("inbound_email")
    appt = run(record_source(resident_id=rid, room=None, actor=sys_actor, claim={
        "source_type": "email_confirmation", "intent": "cancel", "evidence_ref": "e2", "provider": "cardiologist"}))
    rcs = _receipts(appt["appointment_id"])
    assert len(rcs) == len(appt["sources"]) == len(appt["history"]) == 5
    assert [h["receipt_id"] for h in appt["history"]] == [r["receipt_id"] for r in rcs]
    for i, rc in enumerate(rcs):
        assert rc["actor_id"] and rc["actor_type"] and rc["identity_basis"] and rc["authority"]
        assert rc["correlation_id"] == rcs[0]["receipt_id"]
        assert rc["parent_receipt_id"] == (rcs[i - 1]["receipt_id"] if i else None)
        assert appt["sources"][i]["source_id"] in rc["provider_refs"]
    assert rcs[-1]["authority"] == "system:inbound_email" and rcs[-1]["action_type"] == "appointment_cancelled"


def test_g_booked_ride_says_when_it_leaves():
    line = truth.ride_line({"booked": True, "run": {"depart_time": "09:15"}}, True, {})
    assert line == "There's a ride booked that day, leaving at 9:15 AM."
    assert truth.ride_line(None, False, {}).startswith("I couldn't check for a ride")


def test_g_resident_aria_has_the_tools_and_the_rule():
    from routes.realtime_conversation_rules import CONVERSATION_RULES
    from routes.realtime_tools import _build_tools
    names = [t["name"] for t in run(_build_tools())]
    assert {"check_appointment", "note_reported_appointment"} <= set(names)
    assert "## Appointments" in CONVERSATION_RULES and "reported, not verified" in CONVERSATION_RULES
    assert "Never say an office was called" in CONVERSATION_RULES


def test_http_resident_bus_and_staff_only_sources(resident):
    import requests
    base = (os.environ.get("TEST_API_BASE") or os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
    if not base:
        pytest.skip("no backend named (TEST_API_BASE / REACT_APP_BACKEND_URL)")
    rid, room = resident
    day = _day(5)
    r = requests.post(f"{base}/api/appointments/public/report", timeout=10,
                      json={"room": room, "provider": "cardiologist", "date": day, "time": "10:00"})
    assert r.status_code == 200 and r.json()["status"] == truth.REPORTED, r.text
    c = requests.post(f"{base}/api/appointments/public/check", timeout=10, json={"room": room, "focus": "time"})
    assert c.status_code == 200 and "isn't verified yet" in c.json()["spoken"]
    anon = requests.post(f"{base}/api/appointments/sources", timeout=10, json={
        "resident_id": rid, "source_type": "email_confirmation", "date": day, "time": "10:30", "evidence_ref": "x"})
    assert anon.status_code in (401, 403)
    assert requests.get(f"{base}/api/appointments", params={"resident_id": rid}, timeout=10).status_code in (401, 403)
    assert run(db.resident_appointments.find_one({"resident_id": rid}))["status"] == truth.REPORTED
