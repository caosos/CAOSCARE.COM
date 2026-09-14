"""Direct, harness-independent coverage of the admin-login lockout state
machine's time-dependent transitions (expiry + reset) that cannot be
exercised through iter9_test.py's live-HTTP tests, because those run
against a separately-launched backend process whose real wall clock this
test process cannot control.

Calls routes.auth's internal throttle functions directly in-process (same
pattern this suite already uses for direct-DB tests, e.g.
test_resident_events.py) rather than mocking time.time() globally, which
would risk side effects on anything else running in this pytest session.
Instead, _ADMIN_ATTEMPTS is populated directly with real timestamps placed
in the past (via the real time.time() clock, just offset) - the exact same
data shape _admin_throttle_record() would have produced, just already aged.

Needs MONGO_URL / DB_NAME / JWT_SECRET (same convention as every other
direct-import test in this suite) - no live backend required. Each test
uses its own unique synthetic email so runs never collide with each other
or with iter9_test.py's OWNER_EMAIL/ADMIN_EMAIL buckets (all keyed by
"ip:email" in the same process-global _ADMIN_ATTEMPTS dict).
"""
import asyncio
import time
import uuid

import pytest
from fastapi import HTTPException


def _make_key(ip: str, email: str) -> str:
    return f"{ip}:{email.lower()}"


async def _run_lockout_expires_and_login_succeeds():
    from routes import auth as auth_module

    ip = "127.0.0.1"
    email = f"expiry-test-{uuid.uuid4().hex[:8]}@caoscare.com"
    key = _make_key(ip, email)

    # Simulate 5 failed attempts that happened just past the lockout
    # window (real timestamps, just already aged) - the same shape
    # _admin_throttle_record() produces, without waiting real time.
    stale_ts = time.time() - (auth_module.ADMIN_LOCKOUT_WINDOW_S + 5)
    auth_module._ADMIN_ATTEMPTS[key] = [stale_ts] * auth_module.ADMIN_LOCKOUT_MAX
    try:
        # After expiry: the check itself must no longer reject - this is
        # "successful login after expiry succeeds" at the throttle layer
        # (password verification is independent and covered elsewhere;
        # this proves the lockout itself is not still a hard wall).
        raised = False
        try:
            await auth_module._admin_throttle_check(ip, email)
        except HTTPException:
            raised = True
        assert not raised, "the check must not still reject once every recorded attempt has aged past the window"

        # "...and resets failed-attempt state": the stale attempts must
        # actually be purged, not just silently ignored this one time.
        assert not auth_module._ADMIN_ATTEMPTS.get(key), (
            f"expected the expired attempts to be cleared, found {auth_module._ADMIN_ATTEMPTS.get(key)}"
        )

        # A subsequent immediate check (simulating the real request that
        # follows, e.g. after password verification succeeds) must also
        # pass cleanly - nothing was left half-reset.
        await auth_module._admin_throttle_check(ip, email)
    finally:
        auth_module._ADMIN_ATTEMPTS.pop(key, None)


async def _run_still_locked_just_before_expiry():
    """Adjacent negative case: one second BEFORE the window elapses, the
    lockout must still be fully active - proves the expiry test above is
    actually exercising the boundary, not a check that always passes."""
    from routes import auth as auth_module

    ip = "127.0.0.1"
    email = f"almost-expired-{uuid.uuid4().hex[:8]}@caoscare.com"
    key = _make_key(ip, email)

    almost_stale_ts = time.time() - (auth_module.ADMIN_LOCKOUT_WINDOW_S - 1)
    auth_module._ADMIN_ATTEMPTS[key] = [almost_stale_ts] * auth_module.ADMIN_LOCKOUT_MAX
    try:
        with pytest.raises(HTTPException) as exc_info:
            await auth_module._admin_throttle_check(ip, email)
        assert exc_info.value.status_code == 429
    finally:
        auth_module._ADMIN_ATTEMPTS.pop(key, None)


async def _run_reset_audited_only_when_something_was_cleared():
    """_admin_throttle_clear() only emits an audit event when it actually
    had pending (not-yet-expired) attempts to clear - a successful login
    against an account with zero recent failures is not itself a "reset"
    worth auditing; the natural-expiry case above needs no reset event
    either, since the lockout timed out on its own rather than being
    actively cleared by a login. This directly tests that distinction at
    the function level, in-process (real over-HTTP audit persistence is
    covered live in iter9_test.py::test_lockout_rejections_are_audited for
    the rejection side)."""
    from routes import auth as auth_module
    from deps import db

    ip = "127.0.0.1"
    pending_email = f"pending-reset-{uuid.uuid4().hex[:8]}@caoscare.com"
    clean_email = f"clean-login-{uuid.uuid4().hex[:8]}@caoscare.com"
    pending_key = _make_key(ip, pending_email)
    try:
        # 2 recent (not expired) failures, then a "successful login".
        auth_module._ADMIN_ATTEMPTS[pending_key] = [time.time(), time.time()]
        await auth_module._admin_throttle_clear(ip, pending_email)
        assert auth_module._ADMIN_ATTEMPTS.get(pending_key) is None

        # A clean login with no prior failures at all - no reset to audit.
        await auth_module._admin_throttle_clear(ip, clean_email)

        events = await db.events.find(
            {"event_type": "auth.admin_lockout_reset"},
            {"_id": 0},
        ).to_list(100)
        targets = {e["target_id"] for e in events}
        assert pending_email.lower() in targets, "expected a reset event for the account that had pending failures cleared"
        assert clean_email.lower() not in targets, "a clean login with nothing to reset must not log a reset event"
    finally:
        auth_module._ADMIN_ATTEMPTS.pop(pending_key, None)
        await db.events.delete_many({"target_id": {"$in": [pending_email.lower(), clean_email.lower()]}})


def test_lockout_expires_and_login_succeeds():
    asyncio.get_event_loop().run_until_complete(_run_lockout_expires_and_login_succeeds())


def test_still_locked_just_before_expiry():
    asyncio.get_event_loop().run_until_complete(_run_still_locked_just_before_expiry())


def test_reset_audited_only_when_something_was_cleared():
    asyncio.get_event_loop().run_until_complete(_run_reset_audited_only_when_something_was_cleared())
