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

**Current status (2026-09-13, deterministic across repeated fresh runs):
0 failed, 0 errors.** Every skip and deselection is documented below or
in `pytest.ini`.

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

## Lockout decision (resolved)

The audit's sixth finding - `test_lockout_and_reset_on_success` running
cleanly isolated for the first time and failing deterministically on "a
correct password during an active lockout still gets 429, not 200" - was
a genuine product question, not a harness bug. Resolved (Michael,
2026-09-13): **an active lockout is a hard wall for its full duration - a
correct password during it must never authenticate and must never clear
the counter early.**

**Verified first, before any change:** a direct live-HTTP trace (5 wrong
passwords -> 429, then the *correct* password) already returned 429, not
200 - `routes/auth.py::_admin_throttle_check()` runs and can reject
*before* the password is ever verified, so a correct password during
lockout was already structurally incapable of bypassing it. **No bypass
existed; no behavior fix was needed.** What was missing was auditability:
neither a lockout being enforced nor a lockout being cleared ever produced
any record.

**The one production change** (`backend/routes/auth.py`): `_admin_throttle_check`
(on every rejection) and `_admin_throttle_clear` (on an actual reset - only
when there was pending, not-yet-expired failure state to clear, so a plain
successful login with no recent failures doesn't log noise) now each call
`routes.events.log_event()` - the same generic, already-admin-queryable
(`GET /events`) audit primitive every other observable action in this
codebase uses (`CaosEvent.event_type`'s own doc comment already lists
`"auth.login"` as an example use). `auth.admin_lockout_rejected` carries
the requesting ip and attempt count; `auth.admin_lockout_reset` carries the
ip. Both functions became `async def` for the `await log_event(...)` call;
their two call sites in `admin_login` were updated to `await` them. No
other behavior changed - confirmed identical HTTP status codes/bodies
before and after, live, for the full rejected/still-locked/reset sequence.

There is no existing admin-facing "manually reset a lockout" endpoint
anywhere in the codebase (`grep`-confirmed) - per explicit instruction,
none was invented; "explicit authorized reset" is untested since there is
nothing to test.

**Tests** (`backend/tests/iter9_test.py::TestAdminLogin` +
`backend/tests/test_admin_login_lockout.py`, new):
- `test_threshold_triggers_lockout` - 5x 401 then 429 (live HTTP).
- `test_wrong_password_during_active_lockout_rejected` - still 429, not a
  fresh 401 (live HTTP).
- `test_correct_password_during_active_lockout_rejected` - the correct
  password gets 429 with no token, and a second correct attempt right
  after is *still* 429, proving the first rejected attempt didn't clear
  anything (live HTTP - this is the regression test for the check-before-
  verify ordering; reordering `admin_login` to verify the password first
  would be caught here).
- `test_lockout_rejections_are_audited` - the rejections above are
  actually queryable via `GET /events` (live HTTP + DB-backed).
- `test_lockout_expires_and_login_succeeds` / `test_still_locked_just_before_expiry` -
  the real 15-minute window can't be waited out against a live server
  from the test process, so these call `routes.auth`'s internal throttle
  functions directly in-process with real timestamps placed just past (and
  just before) the window, rather than mocking `time.time()` globally.
- `test_reset_audited_only_when_something_was_cleared` - in-process,
  confirms the reset event fires only when there were pending failures to
  clear, not on every clean login.

## Legacy test failures (resolved)

The audit found five more failures that were not harness problems -
legacy smoke-test assertions (`backend_test.py`, `iter5/10/11_test.py`)
written before a later, deliberate, documented product/architecture
decision, and never updated. Each was audited against the current,
documented contract; in every case the current behavior is correct and
deliberate, so the stale test was updated to match it - no production
behavior was changed to satisfy any of them.

| Test | Was asserting (stale) | What actually changed, and the fix |
|---|---|---|
| `backend_test.py::TestPendants::test_list_seeded_pendants` | a hardcoded `>= 7` seeded pendants | `seed.py` assigns exactly one pendant per seeded resident, not a fixed count - the roster simply has 6 entries now, not 7. Fixed to derive the expected minimum from the actual `/residents` count instead of a new hardcoded number, so it can't go stale the same way again. |
| `iter10_test.py::TestPublicAlertStatus::test_full_lifecycle` | `POST /alerts` with `triggered_by="ai_triage"` echoes `triggered_by` back | `routes/alerts.py::create_alert` deliberately redirects `triggered_by="ai_triage"` to `routes/ai_escalation.py::ai_escalate` (2026-09-06, "AI triage is NOT a human button press") - a different response shape with no `triggered_by` field at all. Updated to assert the current response shape (`effective_severity`, `wording_state`) and the real invariant that redirect exists to guarantee - human `press_count` is unchanged by AI triage (compared before/after, not assumed to always start at 0, since the shared `seeded_resident` fixture may already have history from earlier in the same canonical run). |
| `iter11_test.py::TestWeather::test_default_facility_weather` | hardcoded `"Lancaster, PA"` label | The 2026-08-25 facility-source-of-truth fix replaced exactly this wrong hardcoded Pennsylvania fallback (the facility is actually in Conway, Arkansas) with the live `db.facilities` record, falling back to an honest generic label when none is configured. This test environment has no facility record, so `"the facility"` is the correct current result. Updated the assertion accordingly. |
| `iter5_test.py::TestPanicPress::test_two_presses_within_60s_escalate` | `auto_voice is False` on the first pendant press | `routes/pendants.py` sets `auto_voice = True` unconditionally ("default ON - we always want voice for pendant events"), per the 2026-08-29 real-pendant directive - the test's own very next assertion (`auto_voice is True` on the second press) already reflected that decision; only the first-press expectation predated it. Updated to match. |
| `iter5_test.py::TestPublicDevices::test_public_room_command_updates_state` | a bare `action=power` command with no `device_id`/`kind` succeeds in a room with more than one power-capable device | The kiosk multi-light/TV disambiguation safety fix (`routes/devices.py::public_room_command`) deliberately 400s in exactly that situation now, to stop a command silently landing on whichever device sorts first. The test already fetches the specific device it means to command - updated it to pass that device's `device_id`, the same "already disambiguated" path a real caller (e.g. a voice tool naming a specific light) uses. |

## Files

- `backend/routes/auth.py` - the one production change: audit logging for
  lockout rejection/reset via the existing `log_event` primitive (see
  Lockout decision above). No behavior change - verified live before and
  after.
- `backend/tests/conftest.py` - the event-loop fix, the required-env-var
  check, and the `skip_if_openai_unavailable` fixture.
- `backend/tests/test_admin_login_lockout.py` - new, in-process
  expiry/reset-audit tests (see Lockout decision above).
- `backend/scripts/run_backend_tests.sh` - the canonical command.
- `backend/tests/iter9_test.py` - `OWNER_EMAIL` isolation fix,
  `dorothy_id` fixture, the lockout state-machine tests above.
- `backend/tests/backend_test.py`, `iter5_test.py`, `iter6_test.py`,
  `iter8_test.py`, `iter10_test.py`, `iter11_test.py` -
  `skip_if_openai_unavailable` applied at each confirmed OpenAI-dependent
  call site, plus the five legacy-test updates above.
