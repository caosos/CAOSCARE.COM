# Test reality audit (RQ-051), 2026-10-09

Scope: what the RQ-045…RQ-049 tests, the receipt/voice-endpoint tests and the
frontend voice-path tests actually prove. Offline only: no provider called, no
credential, no running service touched, production code unchanged (every
mutation below was reverted; `git status` clean). Tip `2f0e581`.

## 1. Baselines (isolated gate, port 8115, DB `caoscare_gate_rq051`, OpenAI/HA blank)

- Backend: **432 passed, 31 skipped, 13 deselected, 0 failed.** Matches baseline.
- Frontend: **49 suites / 408 tests passed.** Matches baseline.
- The 31 skips: 14 need a real `OPENAI_API_KEY` (`conftest.py:144`), 7 are
  `test_room_device_isolation` (rooms 401/403/408 not seeded), 5 are Room 214
  real-device tests (light/AC not seeded), 5 are iter8/iter10 data
  prerequisites. 13 deselected are the `real_hardware` marker.
  **Consequence:** the iter10/iter11 `/realtime/session` mint tests (the only
  tests that call the real session-mint route end to end) are skipped in this
  gate. The mint is otherwise covered only through
  `test_realtime_aria_session_auth.py` with a fake httpx.

## 2. Classification

Classes: **A** production code, real Mongo, real FastAPI app over HTTP
(uvicorn from the gate, or `httpx.ASGITransport`) · **B** production module
called directly, provider boundary (httpx / OpenAI) mocked, real parsing
code · **C** production function called with fake inputs / pure function /
string assertion · **D** stub or fixture asserted against itself (cannot fail
on a production regression).

| Test file | Class | What it really exercises | Cannot see |
|---|---|---|---|
| `test_rq047_openai_web_search.py` | B | `research.research_topic` + `research_openai_search` parsing against a fake httpx response shaped by the author | Whether OpenAI's real Responses payload has that shape; the `tool_choice: required` and model acceptance (stated unverified in RQ-047) |
| `test_rq049_research_guard.py` | A (provider replaced) | Real app + real Mongo leases + real guard, rate limit, owner token; `oas.ask` faked | Real provider; rate-limit state across restarts (in-memory) |
| `test_rq045_research_honesty.py` | B/C | Tool-description / prompt text builders and the endpoint `live` flag with a stubbed httpx | That the model obeys the wording |
| `test_rq028_memory_turn_auth.py` | A | ASGI app, real Mongo, lease/grace logic | n/a for this path |
| `test_rq027_twilio_one_path.py` | B | `run_tick`, `notify_alert_phone` with a Twilio httpx spy, real Mongo | A real Twilio account; call status callbacks |
| `test_model_ab_harness.py` | D (by design) | The scorer, price table, guards and a dry-run against its own `stub-good`/`stub-bad` server | Any real model behaviour; it proves the harness, not Aria |
| `test_rq040_tool_descriptions.py` | C | The tool-description strings contain wording | That the model follows it (prompt behaviour is untested everywhere) |
| `test_realtime_aria_session_auth.py` | B | ASGI app, real auth, fake httpx for the OpenAI mint | The real mint response, session.update acceptance |
| `iter10_test.py`, `iter11_test.py` | A (live server) | Real HTTP; mint tests **skipped** without a key | Everything behind the 14 skips |
| `test_sim0_provenance_chain.py`, `test_shared_core_history.py`, `test_transport_ride_receipts.py`, `test_content_receipts.py`, `test_request_status_lifecycle.py`, `test_shared_core_status_truth.py` | A | Real HTTP to the gate's uvicorn, real Mongo, per-step receipt chains | n/a |
| `test_resident_events.py`, `test_level1_*`, `test_rq018_escalation.py` | A | Real HTTP / subprocess concurrency, real Mongo | A physical pendant; RF decode |
| Frontend `claimGuard.test.js`, `farewellWatch.test.js`, `endingPhrases.test.js`, `deviceAmbiguity.test.js`, `researchShape` (inside claimGuard test) | C | Pure functions with fixtures | **Their wiring** (see §4) |
| `researchDispatch.test.js` | C/B | `executeDeviceTool` research branch with mocked `fetch`, asserts the request body and 403/429 | That a non-live result is labelled (see F10) |
| `realtimeConnectionRecovery.test.js` | C | `connectRealtimeVoice` with a **fake** `RTCPeerConnection`/DataChannel and a **mocked** message handler | A real WebRTC session, provider SDP, or any server event |
| `restingRefusalSpeaks.test.js` | C | Real `createRealtimeHandlers` driven with hand-written events and mocked tools | Only one scenario of the handler |
| `realtimeSessionUpdateLanguage.test.js` | C | Two fields of `buildSessionUpdate` | The rest of the payload; acceptance by OpenAI |

Pure-D tests: only `test_model_ab_harness.py` (intentionally) and the
`stub-bad`/`stub-good` fixture. No test was found that asserts a mock
against itself by accident.

## 3. Mutation spot-checks (production behaviour broken in the worktree, test run, reverted)

Backend runs used the gate with `-k`; frontend runs the whole jest suite.

| # | Mutation | Result | Caught by |
|---|---|---|---|
| B1 | `live = True` in `research.py` | **caught** | rq047 ×2 (`..._not_live` tests) |
| B2 | rate limit removed in `research_guard._allow` | **caught** | rq049 `test_rate_limit_per_room` |
| B3 | `find_live_session` always returns a room | **caught** | rq028 ×5, rq049 ×3 |
| B4 | `live_research_enabled()` always true | **caught** | rq045 ×3, rq047 ×2 |
| B5 | `if simulation:` removed from notification delivery | **caught** | rq027, sc8, sim_provenance ×3, sim4 ×2 |
| B6 | closed-request guard removed in `task_lifecycle.check` | **caught** | `test_sim0_provenance_chain` |
| B7 | `update_receipt_status` made a no-op | **NOT caught (0 failures)** | `alerts.py` and `staff_dispatch.py` are its only callers; no test covers alert close-out or page-outcome receipts |
| B8 | press count increment removed in `resident_activation` | **caught** | `test_resident_events`, both `test_level1_*` |
| F1 | `claimGuard` action-claim check disabled | **caught** | `claimGuard.test.js` ×3 |
| F2 | `claimGuard.onResponseDone` not called in `realtimeMessageHandler` | **NOT caught** | nothing drives the wiring |
| F3 | `claimGuard.onToolResult` not called in the handler | **NOT caught** | same |
| F4 | `farewellWatch.onResponseDone` not called in the handler | **NOT caught** | same |
| F5 | `researchShape` never labels a non-live result | **caught** | `claimGuard.test.js` ×3 |
| F6 | "that'll be all" removed from `ENDING_PHRASES` | **caught** | `endingPhrases`, `restingEndCallGuard` |
| F7 | device ambiguity refusal never remembered | **caught** | `deviceAmbiguity` + `toggleLightControl`, 7 tests |
| F8 | `create_response: false` dropped in `buildSessionUpdate` | **caught** (the only test of it, a language test) | `realtimeSessionUpdateLanguage` |
| F9 | transcription model changed to a nonexistent name | **caught** | same test |
| F10 | research dispatch stops calling `shapeResearchResult` | **NOT caught** | `researchDispatch.test.js` never asserts labelling |

Result: 13 of 18 caught. The five uncaught are the integration seams
(handler wiring ×3, dispatch→shape ×1) plus the alert receipt append (B7).

## 4. Gaps, prioritised, each with an offline-testable next step

1. **Claim guards and farewell watch are unit-tested but their wiring is not (F2, F3, F4).** If someone removes the three calls in `realtimeMessageHandler.js`, the audit's protections silently vanish and all 408 tests pass. Also, the guards **only log**; no test and no code makes an unsupported sentence stop. *Next step:* a `realtimeMessageHandler` test, in the style of `restingRefusalSpeaks.test.js`, feeding real event sequences (assistant transcript, `function_call` result, `response.done`) and asserting `logRealtimeEvent` receives `unsupported_action_claim` / `unsupported_lookup_claim` / `unsupported_fresh_fact_claim`, and none after an ok tool result in the same turn. Copy the sanitized rt_dc5h0fi1 excerpts already in `claimGuard.test.js`.
2. **Research label through the real dispatch is untested (F10).** `researchDispatch.test.js` checks the request body only. *Next step:* add one case where `fetch` returns `live:false` and assert the dispatch result's `message` starts with `NOT_LIVE_PREFIX` and `live:false`; and one where `live:true` with citations passes unlabelled.
3. **Alert close-out and page-outcome receipts have no test (B7).** `update_receipt_status` (SC-1 append-only, decision 5) is used by `alerts.py:197` and `staff_dispatch.py:147` only. *Next step:* a backend test over HTTP: create an alert, close it, assert a new `alert_completed` receipt exists and the earlier receipt is unchanged; same for a failed page → `alert_failed`.
4. **No test sends the real `session.update` or the mint payload anywhere.** `buildSessionUpdate` is checked on two fields. The provider's acceptance (the historical "Unknown parameter" regressions of 2026-08-22) cannot be caught offline. *Next step (offline):* a golden-file test for `buildSessionUpdate` and for the `/realtime/session` mint body (with the fake httpx), comparing against a checked-in JSON built from the current OpenAI Realtime GA schema; it catches accidental field changes, not provider rejection. *Not offline:* real acceptance needs one owner-approved live call.
5. **The real mint route is skipped in the gate (14 skips for a missing key).** `iter10/11` mint tests never run offline. *Next step:* extend `test_realtime_aria_session_auth.py`'s fake-httpx pattern to `/realtime/session` for a resident and assert instructions contain the invariants, tool count, `turn_detection` and `create_response`.
6. **`realtimeConnection` is tested against a fake RTCPeerConnection with the message handler mocked.** Recovery logic is covered, but nothing runs connection + handler together with a recorded event stream. *Next step:* a replay test that feeds a recorded (sanitized) server-event JSONL (speech start/stop, transcript, response.done, tool call, output_audio_buffer events) through the real handler and asserts tool dispatch order, `response.create` timing and the inactivity timer.
7. **Prompt/tool-description tests assert wording, not behaviour** (`test_rq040`, `test_rq045`). Nothing can show the model obeys them. *Next step:* none offline; the A/B harness (`scripts/model_ab`) is built for this and needs the owner-approved paid test. Offline, keep these as drift detectors only and say so in their docstrings.
8. **The provider-facing tests prove parsing of the author's fixture, not of OpenAI's payload (rq047).** *Next step:* check in one captured, sanitized real Responses payload (from the owner-approved smoke call) as a fixture so the parser is tested against reality.
9. **The model A/B harness verifies itself (class D).** Its dry run proves plumbing. *Next step:* none required; just do not cite it as evidence about any model. Add the `response.done` usage field once a live run exists.
10. **Rate limit is in-memory and per-process (rq049).** Unit-tested for the limit, not for restart or multi-worker behaviour. *Next step:* document the limit; a test that two apps share nothing is pointless offline.

## 5. What this does and does not establish

- Establishes: the server-side guards (live-session lease, rate limit, simulation suppression, closed-request refusal, press coalescing, research `live` flag) are protected by tests that fail when the behaviour is broken, on 7 of 8 sampled.
- Does not establish: any behaviour of a real Realtime session or model, provider acceptance of `session.update`, or that the claim guards are wired. These are the gaps above.
