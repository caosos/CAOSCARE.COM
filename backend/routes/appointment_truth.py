"""Appointment truth model (aria-appointment-verification-001, #166 owner
requirement 2026-10-16). Pure functions only - no DB, no clock reads.

An outside appointment ("my cardiologist is Tuesday at 10") is ONE canonical
record built from every source that has said something about it. Each source
is a claim with provenance; the record's status and its date/time are DERIVED
from the claims, never typed in:

  REPORTED            only non-authoritative claims, and they agree
  NEEDS_CONFIRMATION  non-authoritative claims disagree, or a newer unverified
                      claim says the verified appointment moved or was cancelled
  VERIFIED            authoritative claims agree
  CONFLICT            authoritative claims disagree - nothing is asserted
  CHANGED             an authoritative change superseded the earlier value
  CANCELLED           an authoritative cancellation

Authoritative = a confirmation with evidence (email / calendar / uploaded
document), a staff entry the staff member marked as verified, or a provider
call that actually connected. Resident speech and family entries are always
reports. An authoritative change / cancel / conflict resolution supersedes
every earlier claim; earlier claims stay on the record as history.
"""
from datetime import date, datetime, time, timezone
from typing import Optional
from zoneinfo import ZoneInfo

REPORTED = "REPORTED"
VERIFIED = "VERIFIED"
NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
CONFLICT = "CONFLICT"
CHANGED = "CHANGED"
CANCELLED = "CANCELLED"
STATUSES = (REPORTED, VERIFIED, NEEDS_CONFIRMATION, CONFLICT, CHANGED, CANCELLED)

SOURCE_TYPES = ("resident_speech", "staff_entry", "family_entry", "email_confirmation",
                "calendar_confirmation", "uploaded_confirmation", "provider_call")
CONFIRMATION_TYPES = ("email_confirmation", "calendar_confirmation", "uploaded_confirmation")
INTENTS = ("report", "confirm", "change", "cancel", "resolve")
SUPERSEDING = ("change", "cancel", "resolve")


def is_authoritative(source: dict) -> bool:
    """Whether a claim can verify. The ingest path has already refused a
    confirmation without evidence and a provider call that never connected."""
    kind = source.get("source_type")
    if kind in CONFIRMATION_TYPES or kind == "provider_call":
        return bool(source.get("evidence_ref"))
    if kind == "staff_entry":
        return bool(source.get("staff_verified"))
    return False


def starts_at_utc(day: Optional[str], hhmm: Optional[str], tz: str) -> Optional[str]:
    """The UTC instant of a local date + wall time in `tz` (DST-correct);
    None without a time."""
    if not day or not hhmm:
        return None
    h, m = (int(x) for x in hhmm.split(":"))
    local = datetime.combine(date.fromisoformat(day), time(h, m), ZoneInfo(tz))
    return local.astimezone(timezone.utc).isoformat()


def _when(s: dict) -> tuple:
    return (s.get("date"), s.get("time"), s.get("timezone"))


def same_when(a: dict, b: dict) -> bool:
    """Two claims agree when they name the same instant (timezones may
    differ), or the same day when either has no time."""
    if a.get("date") is None or b.get("date") is None:
        return a.get("date") == b.get("date") or (a.get("intent") == "cancel" or b.get("intent") == "cancel")
    if a.get("time") and b.get("time"):
        return starts_at_utc(a["date"], a["time"], a["timezone"]) == starts_at_utc(b["date"], b["time"], b["timezone"])
    return a["date"] == b["date"]


def _distinct(claims: list) -> list:
    out = []
    for c in claims:
        if not any(same_when(c, o) for o in out):
            out.append(c)
    return out


def derive(sources: list) -> dict:
    """Status, the governing claim and the discrepancies, from the claims in
    the order they were received."""
    claims = sorted(sources, key=lambda s: s["received_at"])
    for c in claims:
        c["authoritative"] = is_authoritative(c)
    cut = max((i for i, c in enumerate(claims) if c["authoritative"] and c.get("intent") in SUPERSEDING), default=0)
    head, live = claims[:cut], claims[cut:]
    superseded = [c["source_id"] for c in head]
    pivot = live[0] if cut or (live and live[0]["authoritative"] and live[0].get("intent") in SUPERSEDING) else None
    out = {"status": None, "governing": None, "candidates": [], "discrepancies": [], "superseded": superseded,
           "previous": None, "pivot": pivot}

    if pivot and pivot.get("intent") == "cancel":
        later_reports = [c for c in live[1:] if not c["authoritative"] and c.get("intent") != "cancel"]
        out.update(status=NEEDS_CONFIRMATION if later_reports else CANCELLED, governing=pivot,
                   discrepancies=later_reports)
        return out

    auth = [c for c in live if c["authoritative"] and c.get("intent") != "cancel"]
    reports = [c for c in live if not c["authoritative"]]
    if auth:
        values = _distinct(auth)
        if len(values) > 1:
            out.update(status=CONFLICT, candidates=values)
            return out
        gov = auth[-1]
        changed = pivot is not None and pivot.get("intent") == "change"
        # After a change, what was said about the old time is history, not a discrepancy.
        pool = reports if changed else reports + [h for h in head if not h["authoritative"]]
        disagree = [r for r in pool if r.get("intent") == "cancel" or not same_when(r, gov)]
        # A newer claim that it was moved or cancelled reopens the question; someone
        # simply remembering a different time does not (that is a discrepancy).
        newer = [r for r in disagree if r["received_at"] > gov["received_at"] and r in reports
                 and r.get("intent") in ("change", "cancel")]
        if changed:
            older = [h for h in head if h.get("intent") != "cancel"]
            older_auth = [h for h in older if h["authoritative"]]
            if len(_distinct(older_auth)) > 1:
                older_auth, older = [], []          # it was in conflict before; there's no one old time
            out["previous"] = (older_auth or older or [None])[-1]
        status = NEEDS_CONFIRMATION if newer else (CHANGED if changed else VERIFIED)
        out.update(status=status, governing=gov, discrepancies=disagree)
        return out

    values = _distinct([r for r in reports if r.get("intent") != "cancel"])
    cancel_claims = [r for r in reports if r.get("intent") == "cancel"]
    if len(values) == 1 and not cancel_claims:
        out.update(status=REPORTED, governing=values[0])
    else:
        out.update(status=NEEDS_CONFIRMATION, candidates=values + cancel_claims[-1:])
    return out


# ---------- what Aria says ----------

def say_time(hhmm: Optional[str]) -> Optional[str]:
    if not hhmm:
        return None
    h, m = (int(x) for x in hhmm.split(":"))
    if (h, m) == (12, 0):
        return "noon"
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12} {suffix}" if m == 0 else f"{h12}:{m:02d} {suffix}"


def say_day(day: Optional[str], today: str) -> Optional[str]:
    if not day:
        return None
    d = date.fromisoformat(day)
    full = f"{d.strftime('%A')}, {d.strftime('%B')} {d.day}"
    delta = (d - date.fromisoformat(today)).days
    if delta == 0:
        return f"today, {full}"
    if delta == 1:
        return f"tomorrow, {full}"
    return full


def say_when(claim: dict, today: str, facility_tz: str) -> str:
    day = say_day(claim.get("date"), today) or "a day I don't have"
    t = say_time(claim.get("time"))
    when = f"{day} at {t}" if t else f"{day}, with no time on record"
    tz = claim.get("timezone")
    if t and tz and tz != facility_tz:
        when += f" ({tz.split('/')[-1].replace('_', ' ')} time)"
    return when


def _on(iso: Optional[str], facility_tz: str) -> str:
    if not iso:
        return ""
    d = datetime.fromisoformat(iso).astimezone(ZoneInfo(facility_tz))
    return f" on {d.strftime('%B')} {d.day}"


def source_label(claim: dict, facility_tz: str) -> str:
    """Where a claim came from, in words - never more than the record shows."""
    kind = claim.get("source_type")
    on = _on(claim.get("received_at"), facility_tz)
    who = claim.get("reported_by_name")
    if kind == "staff_entry":
        who = who or (claim.get("actor") or {}).get("actor_name")
    return {
        "resident_speech": f"what you told me{on}",
        "staff_entry": (f"the staff-verified entry{' by ' + who if who else ''}{on}" if claim.get("staff_verified")
                        else f"a staff note{' from ' + who if who else ''}{on}"),
        "family_entry": f"{who or 'a family member'}'s note{on}",
        "email_confirmation": f"the confirmation email received{on}",
        "calendar_confirmation": f"the calendar confirmation{on}",
        "uploaded_confirmation": f"the confirmation document added{on}",
        "provider_call": f"the call with the office{on}",
    }.get(kind, f"a note{on}")


def appointment_name(appt: dict) -> str:
    what = appt.get("provider") or appt.get("office") or appt.get("purpose")
    if not what:
        return "appointment"
    low = what.lower()
    return what if "appointment" in low else f"{what} appointment"


def spoken_answer(appt: dict, *, today: str, facility_tz: str, focus: str = "general",
                  ride: Optional[dict] = None, ride_checked: bool = False) -> str:
    """One truthful answer. Verified facts are stated with their source;
    anything unverified is called unverified; a conflict is spelled out, never
    resolved by guessing. Nothing here says an office was contacted unless the
    governing claim is a provider call that connected."""
    d = appt["derived"]
    name = appointment_name(appt)
    st = d["status"]
    gov = d.get("governing")
    lines = []
    if st in (VERIFIED, CHANGED):
        where = f" at {appt['location']}" if appt.get("location") else ""
        lines.append(f"Your {name} is {say_when(gov, today, facility_tz)}{where}. "
                     f"That's verified by {source_label(gov, facility_tz)}.")
        if st == CHANGED:
            prev = d.get("previous")
            lines.append(f"It was changed - it used to be {say_when(prev, today, facility_tz)}." if prev
                         else "It was changed by that confirmation.")
        lines += [_differs(r, gov, today, facility_tz) for r in d["discrepancies"][:2]]
    elif st == NEEDS_CONFIRMATION and gov:
        lines.append(f"Your {name} was verified for {say_when(gov, today, facility_tz)} by "
                     f"{source_label(gov, facility_tz)}, but it needs to be confirmed again:")
        for r in d["discrepancies"][-2:]:
            said = "it was cancelled" if r.get("intent") == "cancel" else say_when(r, today, facility_tz)
            lines.append(f"{source_label(r, facility_tz)} has {said}.")
    elif st == REPORTED:
        lines.append(f"I have your {name} on {say_when(gov, today, facility_tz)}, from "
                     f"{source_label(gov, facility_tz)}. It isn't verified yet - there's no confirmation on file.")
    elif st == CONFLICT:
        options = "; ".join(f"{source_label(c, facility_tz)} says {say_when(c, today, facility_tz)}"
                            for c in d["candidates"])
        lines.append(f"I can't tell you for certain when your {name} is - the confirmations disagree: {options}. "
                     "Someone needs to confirm which one is right.")
    elif st == NEEDS_CONFIRMATION:
        options = "; ".join(f"{source_label(c, facility_tz)} says "
                            f"{'it was cancelled' if c.get('intent') == 'cancel' else say_when(c, today, facility_tz)}"
                            for c in d["candidates"])
        lines.append(f"I don't have your {name} confirmed, and what I have doesn't agree: {options}. "
                     "It needs to be confirmed.")
    elif st == CANCELLED:
        lines.append(f"Your {name} was cancelled, according to {source_label(gov, facility_tz)}.")

    if focus == "change" and st not in (CHANGED, CANCELLED):
        lines.append("I don't have any record of it being changed.")
    if focus == "date" and st in (VERIFIED, CHANGED):
        lines.append("That day is confirmed.")
    elif focus == "date" and st != CANCELLED:
        lines.append("So I can't say for certain which day it is.")
    if focus == "ride" and st != CANCELLED:
        lines.append(ride_line(ride, ride_checked, appt))
    return " ".join(lines)


def _differs(r: dict, gov: dict, today: str, facility_tz: str) -> str:
    """One short sentence for a claim that disagrees with the verified one."""
    if r.get("intent") == "cancel":
        return f"{_cap(source_label(r, facility_tz))} says it was cancelled, but no confirmation says so."
    same_day = r.get("date") == gov.get("date") and r.get("time") and gov.get("time")
    said = say_time(r["time"]) if same_day else say_when(r, today, facility_tz)
    real = say_time(gov["time"]) if same_day else "the verified time"
    if r.get("source_type") == "resident_speech":
        return f"You'd told me {said}, but the confirmation says {real}."
    return f"{_cap(source_label(r, facility_tz))} had {said}, which doesn't match."


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def ride_line(ride: Optional[dict], checked: bool, appt: dict) -> str:
    note = appt.get("transport_notes")
    if not checked:
        base = "I couldn't check for a ride because the day isn't settled."
    elif not ride:
        base = "I don't see a ride request for that day."
    elif ride.get("booked"):
        leaves = say_time((ride.get("run") or {}).get("depart_time"))
        base = "There's a ride booked that day" + (f", leaving at {leaves}." if leaves else ".")
    else:
        base = "There's a ride request for that day, but it isn't booked yet."
    return base + (f" The transport note on file says: {note}." if note else "")
