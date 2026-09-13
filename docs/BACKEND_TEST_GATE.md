# Backend test gate

**Canonical command:**

```bash
cd backend
./scripts/run_backend_tests.sh
```

That's it. It drops a scratch test database, starts a fresh backend
process against it (with `CAOSCARE_TEST_HOOKS=1` and demo seed on), waits
for `/api/health`, runs `pytest tests/` with the required environment set
on the pytest process itself too, and tears the backend down when done.
Any extra arguments are passed straight through to `pytest` (e.g.
`./scripts/run_backend_tests.sh -k rf_semantics`, or `-m real_hardware` to
opt into the hardware-touching tests it excludes by default).

To also exercise the OpenAI-dependent tests (chat, TTS, haiku, memory
extraction, realtime session minting), export a real key first:

```bash
OPENAI_API_KEY=sk-... ./scripts/run_backend_tests.sh
```

Without one, those tests skip individually with an explicit reason -
they do not fail, and nothing else is silently skipped alongside them.

## What "trustworthy" means here

A red result should mean the code is wrong. Before the fixes described
below, that wasn't reliably true: a missing env var, a stale in-memory
rate-limit counter, or two unrelated test files sharing a closed event
loop could each produce a failure or error that looked exactly like a
real regression. The goal of this gate is that every remaining non-green
result - fail, error, or skip - has one precise, evidenced explanation,
and that explanation is either "this is a real bug" or a documented,
specific harness/environment condition - never a vague "probably flaky."

## Harness fixes (backend/tests/conftest.py)

**1. Shared event loop across DB-direct test files.** Many test files in
this suite predate pytest-asyncio and each define their own `async def
_run(): ...` invoked via a bare `asyncio.run(_run())` (or
`asyncio.get_event_loop().run_until_complete(_run())`) from a plain `def
test_x()`. Every one of them also does `from deps import db` - a
module-level Motor client that's a singleton for the whole pytest
process. `asyncio.run()` creates a new loop and closes it on return; once
one file's loop closes, the next DB-direct file's own `asyncio.run()` (or
a `get_event_loop()` call that just gets back the now-closed one) fails
with `RuntimeError: Event loop is closed` or `... attached to a different
loop` - a pure scheduling artifact, identical regardless of which two
files happen to run adjacent to each other, and invisible when any one of
them runs alone.

`conftest.py::pytest_configure` installs one persistent event loop for
the whole session before any test module runs, and patches `asyncio.run`
to execute against it via `run_until_complete()` instead of creating and
closing a new one each call. No individual test file was changed for
this - both call styles already in use now converge on the same safe
loop.

**2. Missing test-environment variables surfaced as confusing deep
errors.** `test_public_demo_kiosk.py` and `test_room_device_isolation.py`
import `routes.auth` directly in-process to mint a JWT locally (the same
pattern `scripts/seed_mock_residents.py` uses) - `routes/auth.py` reads
`JWT_SECRET` from `os.environ` at *import* time. Any DB-direct file needs
`MONGO_URL`/`DB_NAME` in the *pytest process's own* environment,
separately from whatever the backend server under test was started with.
Previously, a missing one of these surfaced as a bare `KeyError` several
frames deep inside `routes/auth.py` or `deps.py` - indistinguishable at a
glance from a real regression. `pytest_configure` now checks for all
three up front and fails immediately with one clear message naming
exactly what's missing and why - before collecting a single test.

**3. `CAOSCARE_TEST_HOOKS`-dependent tests running against a backend
that doesn't have it set.** `routes/staff_dispatch.py::request_nurse_page`
only takes its simulated-delivery-failure branch when
`os.environ["CAOSCARE_TEST_HOOKS"]` is truthy **on the backend process**
- deliberately, so no caller can talk the system into fabricating a
delivery outcome in production. `test_ai_escalation.py`'s own docstring
already documented this requirement; the canonical script sets it. If a
backend is ever started without it, `test_ai_escalation.py`'s assertion
message now names the actual cause (see its own comment) instead of
reading like a safety violation, and `test_staff_dispatch_wording.py`
covers the same CAOSCare rule ("a failed dispatch must never be worded as
paged") independently of any server's environment - it calls
`request_nurse_page()` directly in-process and sets the flag itself.

**4. `OPENAI_API_KEY`-dependent tests, precisely, not with a blanket
skip.** A `skip_if_openai_unavailable` fixture in `conftest.py` is a
callable a test invokes on the exact HTTP response it just received: it
skips, with an explicit reason, **only** when that response is precisely
`503` with `"OPENAI_API_KEY"` in the body - the specific, documented shape
the backend returns when no key is configured. Any other status (a real
500, a wrong 401, a changed error message) still fails the test normally.
Applied at every confirmed call site across `backend_test.py`,
`iter6_test.py`, `iter8_test.py`, `iter10_test.py`, `iter11_test.py` -
including a few tests one step downstream of the actual API call (e.g.
`iter8_test.py`'s tests that read back what an earlier, skipped test in
the same class would have written), which skip with a reason naming the
specific upstream test rather than failing on now-legitimately-absent
data.

**5. Admin-login rate-limit state shared across the whole test run.**
`routes/auth.py::_ADMIN_ATTEMPTS` is a real, correct, in-memory
per-process throttle keyed by `"ip:email"` (5 failures / 15 minutes) -
production behavior, unchanged. `iter9_test.py`'s own
`test_lockout_and_reset_on_success` deliberately triggers that lockout to
prove it exists - its own docstring already said "use a unique
admin-style email so we don't pollute the real admin bucket," but the
code used the real, shared `admin@caoscare.com` anyway, poisoning that
account's throttle bucket for the rest of the file (and any later file in
the same `pytest tests/` invocation that logs in as that account) for the
next 15 real minutes. Fixed by pointing that one test at the
separately-seeded `owner@caoscare.com` account instead (also
admin-tier, accepted by `/admin-login`'s own role check) - a
test-file-only change, zero production code touched.

**6. `DOROTHY_ID` hardcoded to a value from a past seed run.**
`iter9_test.py` previously hardcoded a specific `resident_id` for "Dorothy
Walsh." `seed.py` mints every resident's `resident_id` randomly (`uid()`)
on each seed run, so that constant could only ever match the one
environment it happened to be copied from - not a real regression, a
pure test-portability defect. Replaced with a `dorothy_id` fixture that
resolves the same resident by name via the live `/residents` list; every
assertion is unchanged.

## What this gate does NOT fix, and why

The audit found five failures that are not harness problems in the sense
above - they're legacy smoke-test assertions (`backend_test.py`,
`iter5/10/11_test.py`) written before a later, deliberate, documented
product/architecture decision, and never updated:

| Test | Asserts (stale) | What actually changed, and when |
|---|---|---|
| `backend_test.py::TestPendants::test_list_seeded_pendants` | `>= 7` seeded pendants | This environment's demo seed produces 6. Seed-count drift, not a regression. |
| `iter10_test.py::TestPublicAlertStatus::test_full_lifecycle` | `POST /alerts` with `triggered_by="ai_triage"` echoes it back | The 2026-09-06 "make 'a nurse has been paged' a real, auditable action" work moved AI-triage escalation to a dedicated `POST /alerts/ai-escalate` endpoint with its own model (`routes/ai_escalation.py`); the legacy direct-`/alerts` path this test uses was never part of that redesign. |
| `iter11_test.py::TestWeather::test_default_facility_weather` | hardcoded `"Lancaster, PA"` label | Superseded by the 2026-08-25 "facility source of truth wired into Realtime voice" work - weather now reads the real `db.facilities` record; a generic fallback label is the *correct* behavior for an environment without that record configured, per that change. |
| `iter5_test.py::TestPanicPress::test_two_presses_within_60s_escalate` | `auto_voice is False` on an RF-triggered alert | The 2026-08-29 real-pendant work explicitly set `auto_voice=True` for RF-triggered alerts ("a pendant press must always reach Aria hands-free") - a deliberate, documented product decision this test predates. |
| `iter5_test.py::TestPublicDevices::test_public_room_command_updates_state` | a bare `power` command with no `kind` succeeds when a room has multiple power-capable devices | The later multi-device disambiguation safety fix (see PROJECT_STATE, "kiosk multi-light bug") deliberately requires `kind` in that situation and 400s otherwise - fixing the exact silent-misrouting risk that change was for. |

These are real, but they are legacy-test-vs-product-drift, not one of the
four named harness problems, and not something this pass changed - doing
so would mean either reverting a deliberate, documented product decision
(wrong) or rewriting old assertions to match current behavior (a genuine
legacy-test-modernization task, better done deliberately with its own
review than folded into a harness pass). They fail the same way, every
run, for a documented reason - which is itself the point of this gate.

**One more finding, not a harness problem or stale-test drift - a
genuine, newly-legible product question:** with the rate-limit isolation
fix above, `test_lockout_and_reset_on_success` now runs cleanly isolated
for the first time, and its final assertion fails deterministically:
after 5 wrong passwords trip the 429 lockout, a 6th attempt with the
*correct* password still gets 429, not 200. Tracing `routes/auth.py`:
`_admin_throttle_check()` runs and can raise 429 *before* the password is
ever checked, so `_admin_throttle_clear()` (which exists specifically to
reset the counter on a successful login) is unreachable once already
locked out - the account is genuinely locked for the full 15-minute
window regardless of whether the very next attempt is correct. Whether an
admin/owner should be able to immediately recover with their correct
password mid-lockout, or whether a fixed-duration lockout regardless of
subsequent correct attempts is the intended security posture, is a
product decision, not a harness one - left as a failing test (not
weakened, not skipped) pending that decision, per "do not change
production behavior unless you find a real production defect" - this is
real, but not yet decided to be a *defect*.

## Files

- `backend/tests/conftest.py` - the event-loop fix, the required-env-var
  check, and the `skip_if_openai_unavailable` fixture.
- `backend/scripts/run_backend_tests.sh` - the canonical command.
- `backend/tests/iter9_test.py` - `OWNER_EMAIL` isolation fix, `dorothy_id`
  fixture.
- `backend/tests/backend_test.py`, `iter6_test.py`, `iter8_test.py`,
  `iter10_test.py`, `iter11_test.py` - `skip_if_openai_unavailable` applied
  at each confirmed OpenAI-dependent call site.
- No production code changed.
