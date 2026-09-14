"""Direct, harness-independent regression coverage for the CAOSCare rule:

    "A nurse has been paged" (or equivalent success language) may only be
    emitted when there is a real, successful dispatch record. A failed
    dispatch must never be represented to the resident or system as
    successful.

Unlike test_ai_escalation.py, these call routes.staff_dispatch's functions
directly in-process rather than over HTTP to a separately-launched server.
That matters specifically for the failed-delivery case: the simulate-fail
hook is gated behind CAOSCARE_TEST_HOOKS (routes/staff_dispatch.py::
_test_hooks()), which reads os.environ fresh on every call. A live server
launched without that variable silently takes the "accepted" branch instead
of "failed" - not a code defect, but a test-precondition trap that made a
real regression here indistinguishable from a missing env var (see
test_ai_escalation.py's own docstring, and docs/PROJECT_STATE.md's
CAOSCARE_TEST_HOOKS=1 staging-backend precedent). Setting the env var
in-process before calling request_nurse_page() removes that trap entirely
for this file.

Needs MONGO_URL / DB_NAME (same convention as the other direct-DB tests in
this suite, e.g. test_resident_events.py) - no live backend required.
"""
import asyncio
import os
import uuid

from fastapi import HTTPException


async def _run_successful_dispatch_reports_paged():
    from deps import db
    from routes.staff_dispatch import request_nurse_page

    alert_id = f"alert_test_{uuid.uuid4().hex[:8]}"
    try:
        disp = await request_nurse_page(
            alert_id=alert_id, activation_id=None, resident_id=None,
            resident_name="Test Resident", room="rtest_1", severity="emergency",
            reason="unit test - successful dispatch", department="Care/Nursing",
            source="ai_triage", session_id=None, simulate=None,
        )
        assert disp["status"] in ("accepted", "delivered")
        assert disp["wording_state"] == "paged"

        # A "paged" claim must be backed by a real, persisted record - never
        # asserted from in-memory state alone.
        persisted = await db.staff_dispatches.find_one({"dispatch_id": disp["dispatch_id"]}, {"_id": 0})
        assert persisted is not None, "wording_state=paged with no persisted dispatch record"
        assert persisted["status"] == disp["status"]
        assert persisted["failed_at"] is None
        assert persisted["failure_reason"] is None
    finally:
        await db.staff_dispatches.delete_many({"alert_id": alert_id})
        await db.receipts.delete_many({"related_object_id": alert_id})


async def _run_failed_dispatch_never_reports_paged():
    from deps import db
    from routes.staff_dispatch import request_nurse_page

    prior = os.environ.get("CAOSCARE_TEST_HOOKS")
    os.environ["CAOSCARE_TEST_HOOKS"] = "1"
    alert_id = f"alert_test_{uuid.uuid4().hex[:8]}"
    try:
        disp = await request_nurse_page(
            alert_id=alert_id, activation_id=None, resident_id=None,
            resident_name="Test Resident", room="rtest_2", severity="emergency",
            reason="unit test - failed dispatch", department="Care/Nursing",
            source="ai_triage", session_id=None, simulate="fail",
        )
        assert disp["status"] == "failed"
        assert disp["wording_state"] == "failed"
        assert disp["wording_state"] != "paged", "a failed dispatch must never be worded as paged"
        assert disp["failed_at"] is not None
        assert disp["failure_reason"]

        persisted = await db.staff_dispatches.find_one({"dispatch_id": disp["dispatch_id"]}, {"_id": 0})
        assert persisted["status"] == "failed"
        assert persisted["failure_reason"]

        # Auditability: the failure is a real, queryable event, not just a
        # field flip - matches ai_escalate()'s activation_events assertion.
        events = [e["status"] for e in persisted["events"]]
        assert "requested" in events and "failed" in events
    finally:
        if prior is None:
            os.environ.pop("CAOSCARE_TEST_HOOKS", None)
        else:
            os.environ["CAOSCARE_TEST_HOOKS"] = prior
        await db.staff_dispatches.delete_many({"alert_id": alert_id})
        await db.receipts.delete_many({"related_object_id": alert_id})


async def _run_simulate_fail_ignored_without_test_hooks():
    """The gate itself: simulate="fail" from an untrusted/production caller
    must be inert unless CAOSCARE_TEST_HOOKS is explicitly enabled - a caller
    can never talk the system into fabricating (or spoofing) a delivery
    outcome. This is what made the original report look like a "paged
    instead of failed" defect; proving it's the documented gate, not a
    silent bug, is the point of this test."""
    from deps import db
    from routes.staff_dispatch import request_nurse_page

    prior = os.environ.pop("CAOSCARE_TEST_HOOKS", None)
    alert_id = f"alert_test_{uuid.uuid4().hex[:8]}"
    try:
        disp = await request_nurse_page(
            alert_id=alert_id, activation_id=None, resident_id=None,
            resident_name="Test Resident", room="rtest_3", severity="emergency",
            reason="unit test - simulate ignored without hook", department="Care/Nursing",
            source="ai_triage", session_id=None, simulate="fail",
        )
        # Without the opt-in flag, delivery genuinely proceeds (this pilot's
        # only "provider" is the durable local dashboard write itself), so
        # accepted/paged here is correct - the invariant under test is that
        # this is real acceptance, not a caller-controlled false claim.
        assert disp["status"] == "accepted"
        assert disp["wording_state"] == "paged"
    finally:
        if prior is not None:
            os.environ["CAOSCARE_TEST_HOOKS"] = prior
        await db.staff_dispatches.delete_many({"alert_id": alert_id})
        await db.receipts.delete_many({"related_object_id": alert_id})


async def _run_no_dispatch_record_never_claims_paged():
    from deps import db
    from routes.staff_dispatch import get_dispatch, WORDING

    missing_id = f"dsp_does_not_exist_{uuid.uuid4().hex[:8]}"
    assert await db.staff_dispatches.find_one({"dispatch_id": missing_id}) is None

    raised = None
    try:
        await get_dispatch(missing_id, user=None)
    except HTTPException as e:
        raised = e
    assert raised is not None and raised.status_code == 404, (
        "a lookup for a dispatch that was never created must error, "
        "never fabricate a status that could be worded as paged"
    )

    # The wording table itself: no status short of a genuine
    # accepted/delivered record maps to "paged" - an absent/unknown status
    # falls back to "sent" (a page was requested, not confirmed), never
    # "paged" or "failed" by default.
    assert WORDING.get("some_unknown_status", "sent") == "sent"
    assert "paged" not in {v for k, v in WORDING.items() if k not in ("accepted", "delivered")}


def test_successful_dispatch_reports_paged():
    asyncio.get_event_loop().run_until_complete(_run_successful_dispatch_reports_paged())


def test_failed_dispatch_never_reports_paged():
    asyncio.get_event_loop().run_until_complete(_run_failed_dispatch_never_reports_paged())


def test_simulate_fail_ignored_without_test_hooks():
    asyncio.get_event_loop().run_until_complete(_run_simulate_fail_ignored_without_test_hooks())


def test_no_dispatch_record_never_claims_paged():
    asyncio.get_event_loop().run_until_complete(_run_no_dispatch_record_never_claims_paged())
