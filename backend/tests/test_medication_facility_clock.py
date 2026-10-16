"""Medication reminders run on the facility's clock, not the server's
(aria-room-followup-truth-001).

/medications/due/by-room compared reminder times and weekdays against server
UTC, and med_ack.day was the UTC date: a Chicago 18:00 reminder fired at
13:00 (CDT) / 12:00 (CST), on the wrong weekday in the evening, and an
evening acknowledgement counted against the next local day. The facility
timezone comes from the canonical source (db.facilities.timezone ->
FACILITY_TZ, routes/facility_local_time.facility_tz); nothing here assumes
America/Chicago.

Pure clock tests run anywhere; DB tests use a throwaway room via deps.db.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deps import db  # noqa: E402
from routes.facility_local_time import facility_clock  # noqa: E402
import routes.medications as meds  # noqa: E402

run = asyncio.get_event_loop().run_until_complete
CHI = "America/Chicago"


def at(iso):
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


@pytest.mark.parametrize("tz,utc,hhmm,weekday,date", [
    (CHI, "2026-10-17T00:30", "19:30", "fri", "2026-10-16"),            # CDT evening: UTC is already Saturday
    (CHI, "2026-01-10T00:30", "18:30", "fri", "2026-01-09"),            # CST, one hour further from UTC
    (CHI, "2026-03-08T07:59", "01:59", "sun", "2026-03-08"),            # last CST minute before spring-forward
    (CHI, "2026-03-08T08:00", "03:00", "sun", "2026-03-08"),            # 02:00-02:59 does not exist that day
    (CHI, "2026-11-01T06:30", "01:30", "sun", "2026-11-01"),            # first 01:30 (CDT)
    (CHI, "2026-11-01T07:30", "01:30", "sun", "2026-11-01"),            # repeated 01:30 (CST)
    ("Asia/Kolkata", "2026-10-16T20:00", "01:30", "sat", "2026-10-17"), # ahead of UTC, half-hour offset
    ("America/Los_Angeles", "2026-10-16T06:59", "23:59", "thu", "2026-10-15"),
    ("UTC", "2026-10-16T18:00", "18:00", "fri", "2026-10-16"),
])
def test_facility_clock_is_the_local_wall_clock(tz, utc, hhmm, weekday, date):
    c = facility_clock(tz, at(utc))
    assert (c["hhmm"], c["weekday"], c["date"], c["tz"]) == (hhmm, weekday, date, tz)


def test_local_day_bounds_follow_dst():
    hours = lambda c: (datetime.fromisoformat(c["day_end_utc"]) - datetime.fromisoformat(c["day_start_utc"])).total_seconds() / 3600
    spring = facility_clock(CHI, at("2026-03-08T12:00"))
    assert spring["day_start_utc"] == "2026-03-08T06:00:00+00:00" and hours(spring) == 23
    fall = facility_clock(CHI, at("2026-11-01T12:00"))
    assert fall["day_start_utc"] == "2026-11-01T05:00:00+00:00" and hours(fall) == 25
    assert hours(facility_clock(CHI, at("2026-10-16T12:00"))) == 24


@pytest.fixture()
def room():
    name = f"T-MEDCLK-{uuid.uuid4().hex[:6]}"
    made = []

    def remind(hhmm, days):
        rid = f"med_{name}_{len(made)}"
        run(db.med_reminders.insert_one({"reminder_id": rid, "resident_id": f"res_{name}", "room": name,
                                         "title": "Evening pills", "time_hhmm": hhmm, "days": days, "active": True}))
        made.append(rid)
        return rid
    yield name, remind
    run(db.med_ack.delete_many({"reminder_id": {"$in": made}}))
    run(db.med_reminders.delete_many({"room": name}))


def _due(room_name, tz, utc):
    return [r["reminder_id"] for r in run(meds.due_reminders(room_name, facility_clock(tz, at(utc))))]


def test_reminder_fires_at_facility_time_not_utc(room):
    name, remind = room
    rid = remind("18:00", ["fri"])
    assert _due(name, CHI, "2026-10-16T23:00") == [rid]     # 18:00 CDT Friday
    assert _due(name, CHI, "2026-10-16T18:00") == []        # 18:00 UTC = 13:00 CDT: the old bug fired here
    assert _due(name, CHI, "2026-12-12T00:00") == [rid]     # 18:00 CST Friday (UTC already Saturday)
    assert _due(name, "Asia/Kolkata", "2026-10-16T12:30") == [rid]   # the same row under another facility tz


def test_evening_ack_counts_for_the_local_day_including_legacy_utc_keys(room):
    name, remind = room
    rid = remind("20:00", ["fri", "sat"])
    # A pre-fix ack: spoken Friday 20:00 CDT, stored under the UTC date (Saturday).
    run(db.med_ack.insert_one({"ack_id": "ack_legacy", "reminder_id": rid, "day": "2026-10-17",
                               "at": "2026-10-17T01:00:00.123456+00:00"}))
    assert _due(name, CHI, "2026-10-17T01:00") == []         # Friday's reminder already spoken
    assert _due(name, CHI, "2026-10-18T01:00") == [rid]      # Saturday 20:00 local still fires


def test_fall_back_repeated_hour_announces_once(room):
    name, remind = room
    rid = remind("01:30", ["sun"])
    assert _due(name, CHI, "2026-11-01T06:30") == [rid]      # 01:30 CDT
    run(db.med_ack.insert_one({"ack_id": f"ack_{name}", "reminder_id": rid, "day": "2026-11-01",
                               "at": "2026-11-01T06:30:05+00:00"}))
    assert _due(name, CHI, "2026-11-01T07:30") == []         # 01:30 again (CST), same local day


def test_routes_use_the_configured_facility_timezone(room, monkeypatch):
    name, remind = room
    tz = "Pacific/Kiritimati"                                # UTC+14: never the server's UTC minute
    async def facility_tz():
        return tz
    monkeypatch.setattr(meds, "facility_tz", facility_tz)
    for _ in range(2):                                       # a minute boundary between the two reads
        c = facility_clock(tz)
        rid = remind(c["hhmm"], [c["weekday"]])
        due = [r["reminder_id"] for r in run(meds.due_for_room(name))]
        if rid in due:
            break
    assert rid in due
    ack = run(meds.ack_reminder(rid))
    assert ack["day"] == facility_clock(tz)["date"] and ack["tz"] == tz
    assert run(meds.ack_reminder(rid)) == {"ok": True, "already": True}
    assert rid not in [r["reminder_id"] for r in run(meds.due_for_room(name))]
