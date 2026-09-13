"""Backend test-harness fixes shared by the whole `tests/` suite.

This file exists to make failures trustworthy: a test should fail because a
behavior is wrong, never because of how the test suite happens to be wired
together. Two structural problems in this suite's own design made that
untrue before this file existed, and both are fixed here rather than in any
individual test:

1. Required test-environment variables. A number of test files (e.g.
   test_public_demo_kiosk.py, test_room_device_isolation.py) import
   `routes.auth` directly in-process to mint a JWT locally, the same way
   scripts/seed_mock_residents.py does - `routes/auth.py` reads
   `JWT_SECRET` from `os.environ` at import time. Others (any file doing
   `from deps import db`) need `MONGO_URL`/`DB_NAME` in the pytest
   process's own environment, separately from whatever the backend server
   under test was started with. When one of these is missing, the failure
   previously surfaced as a deep, confusing `KeyError` inside routes/auth.py
   or deps.py - indistinguishable at a glance from a real regression.
   `pytest_configure` below checks for them once, up front, and fails with
   one clear, actionable message instead.

2. Shared event-loop state across DB-direct test files. Many test files in
   this suite do NOT use pytest-asyncio; each defines its own `async def
   _run()` and calls it from a plain `def test_x(): asyncio.run(_run())` (or
   `asyncio.get_event_loop().run_until_complete(_run())`). `asyncio.run()`
   creates a brand-new event loop and CLOSES it when the call returns. Every
   one of these files also does `from deps import db`, which is a
   module-level `AsyncIOMotorClient` - a singleton for the whole pytest
   process, cached after the first import. Once file A's `asyncio.run()`
   closes its loop, file B's own `asyncio.run()`/`get_event_loop()` call
   either creates ANOTHER new loop (which the already-instantiated Motor
   client's internal executor scheduling wasn't built against) or retrieves
   the first, now-closed loop - producing `RuntimeError: Event loop is
   closed` or `RuntimeError: Task ... attached to a different loop`. This
   has nothing to do with the behavior under test: every affected file
   passes cleanly running alone, and the failure signature is identical
   regardless of which two DB-direct files happen to run adjacent to each
   other in one invocation.

   Fix: one persistent event loop for the entire pytest session, installed
   as the current loop before any test module runs, with `asyncio.run`
   patched to execute against it via `run_until_complete()` instead of
   creating and closing a new loop each call. This makes `asyncio.run()`
   behave like the `asyncio.get_event_loop().run_until_complete()` pattern
   some files already use (which never had this problem) - so both styles
   converge on the same safe behavior, and no individual test file needs to
   change. The loop is never closed by this fixture; the pytest process
   exiting reclaims it, same as it already reclaims the Motor client's
   sockets.

Neither change alters production code or weakens any assertion - a test
that is actually wrong still fails; a test that only failed because of the
scaffolding above now runs the way its own author intended.
"""
import asyncio
import os

import pytest

_REQUIRED_ENV = {
    "MONGO_URL": (
        "the Mongo connection string - every direct-DB test in this suite "
        "(`from deps import db`) needs this in the pytest process's own "
        "environment, not just on the backend server under test"
    ),
    "DB_NAME": (
        "the database name the tests read/write - must match the database "
        "the backend server under test is also using, or tests will see "
        "empty collections and fail with misleading assertions"
    ),
    "JWT_SECRET": (
        "several tests (test_public_demo_kiosk.py, test_room_device_isolation.py) "
        "import routes.auth directly to mint a JWT locally, the same way "
        "scripts/seed_mock_residents.py does - this MUST be the exact same "
        "value the backend server under test was started with, or the "
        "locally-minted token will be rejected as invalid by that server"
    ),
}


def pytest_configure(config):
    missing = [name for name in _REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        lines = ["\nMissing required test-environment variable(s):"]
        for name in missing:
            lines.append(f"  {name} - {_REQUIRED_ENV[name]}")
        lines.append(
            "\nSee docs/BACKEND_TEST_GATE.md for the canonical test command "
            "that sets all of these consistently."
        )
        pytest.exit("\n".join(lines), returncode=1)

    # One persistent, never-closed event loop for the whole session (see
    # module docstring). Installed here, in pytest_configure, so it exists
    # before any test module's own asyncio.run()/get_event_loop() call.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    _real_run = asyncio.run

    def _session_scoped_run(coro, *, debug=None):
        current = asyncio.get_event_loop()
        if current.is_closed():
            # Defensive only - should not happen, since we never close it.
            current = asyncio.new_event_loop()
            asyncio.set_event_loop(current)
        return current.run_until_complete(coro)

    asyncio.run = _session_scoped_run
    config._original_asyncio_run = _real_run  # kept for symmetry/debugging only


def pytest_unconfigure(config):
    original = getattr(config, "_original_asyncio_run", None)
    if original is not None:
        asyncio.run = original


@pytest.fixture
def skip_if_openai_unavailable():
    """Precise, non-blanket OPENAI_API_KEY handling (harness problem #4).

    A number of tests exercise endpoints (`/ai/chat`, `/ai/tts`,
    `/realtime/session`, `/memory/extract`, `/haiku/generate-today`, ...)
    that legitimately need a real OPENAI_API_KEY configured on the backend
    server under test. Without one, those endpoints correctly return HTTP
    503 with a specific "OPENAI_API_KEY is not configured" detail message -
    that is the application behaving correctly, not a bug, and asserting a
    hard failure on it in an environment that was never given a key
    produces a false "regression."

    This fixture returns a callable, `skip(response)`, for a test to invoke
    on the exact response it just received, before asserting on it:
    `pytest.skip()`s with a specific, documented reason ONLY when the
    response is precisely this condition (503 + that detail text) - any
    other status or error still fails the test normally. This is
    deliberately not a blanket "skip whenever something looks OpenAI-ish";
    a real 500, a wrong 401, or a changed error message all still fail
    loudly, which is the point of not hiding failures behind a broad
    xfail/skip.
    """
    def _skip(response):
        if response.status_code == 503 and "OPENAI_API_KEY" in response.text:
            pytest.skip(
                "requires a real OPENAI_API_KEY configured on the backend "
                "under test - not configured in this environment (backend "
                "correctly returned 503, not a regression)"
            )
    return _skip
